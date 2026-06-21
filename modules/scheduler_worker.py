"""
scheduler_worker.py — Background job runner for Post-Pilot.

Polls post_history for rows with:
    status = 'scheduled' AND scheduled_at <= now()

For each due post, publishes via UniversalPublisher then marks:
    status = 'published'  (if at least one platform succeeded)
    status = 'failed'     (if all platforms failed)

Started via init_scheduler() called from app.py at module load time.
Idempotent — safe to call multiple times (second call is a no-op).

Dependency: APScheduler>=3.10.4 (in requirements.txt)
"""

import json
import time
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from modules.db import get_connection, placeholder, USE_POSTGRES
from modules.auth_manager import load_token

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


# ---------------------------------------------------------------------------
# Token builder (mirrors app.py _get_tokens, standalone for the worker)
# ---------------------------------------------------------------------------
def _build_tokens(uid: str) -> dict:
    tokens = {}
    platform_map = {
        'facebook': ['facebook_token', 'facebook_page_id'],
        'google':   ['google_token',   'google_location_id'],
        'tiktok':   ['tiktok_token'],
        'youtube':  ['youtube_token'],
    }
    for platform, keys in platform_map.items():
        rec = load_token(platform, uid)
        if not rec:
            continue
        tokens[keys[0]] = rec['access_token']
        if len(keys) > 1 and rec.get('meta'):
            meta = rec['meta']
            if platform == 'facebook':
                tokens['facebook_page_id'] = meta.get('page_id', '')
                tokens['instagram_token']  = rec['access_token']
                tokens['instagram_id']     = meta.get('ig_id', '')
            elif platform == 'google':
                tokens['google_location_id'] = meta.get('location_id', '')
                tokens['youtube_token']      = rec['access_token']
    return tokens


# ---------------------------------------------------------------------------
# Core job
# ---------------------------------------------------------------------------
def _publish_due_posts():
    """Find all due scheduled posts and publish them. Runs every 60 seconds."""
    # Deferred import to avoid circular dependency at module load
    from modules.publisher import UniversalPublisher

    now_ts = int(time.time())
    p      = placeholder
    conn   = get_connection()

    try:
        if USE_POSTGRES:
            import psycopg2.extras
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()

        cur.execute(
            f'SELECT id, user_id, caption, content_type, image_url, video_url, platforms '
            f'FROM post_history '
            f'WHERE status={p} AND scheduled_at<={p} AND scheduled_at IS NOT NULL',
            ('scheduled', now_ts),
        )
        rows = cur.fetchall()
    except Exception as exc:
        logger.error('scheduler_worker: DB query failed: %s', exc)
        conn.close()
        return

    if not rows:
        conn.close()
        return

    logger.info('scheduler_worker: %d post(s) due for publishing', len(rows))

    for row in rows:
        # Portable row access
        if isinstance(row, dict):
            post_id      = row['id']
            user_id      = row['user_id']
            caption      = row['caption']
            content_type = row['content_type']
            image_url    = row['image_url']
            video_url    = row['video_url']
            platforms    = row['platforms']
        else:
            post_id, user_id, caption, content_type, image_url, video_url, platforms = (
                row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            )

        try:
            platform_list = json.loads(platforms or '[]')
            tokens        = _build_tokens(user_id)
            publisher     = UniversalPublisher(tokens, user_id=user_id)
            results       = publisher.push_all(
                caption      = caption or '',
                content_type = content_type or 'text',
                image_url    = image_url,
                video_url    = video_url,
                platforms    = platform_list,
            )

            # At least one success -> published; all failed -> failed
            if isinstance(results, dict):
                any_ok = any(
                    (v.get('success') if isinstance(v, dict) else bool(v))
                    for v in results.values()
                )
            else:
                any_ok = bool(results)

            new_status = 'published' if any_ok else 'failed'
            cur.execute(
                f'UPDATE post_history SET status={p}, results={p} WHERE id={p}',
                (new_status, json.dumps(results), post_id),
            )
            conn.commit()
            logger.info('scheduler_worker: post id=%s -> %s', post_id, new_status)

        except Exception as exc:
            logger.error('scheduler_worker: failed to publish post id=%s: %s', post_id, exc)
            try:
                cur.execute(
                    f'UPDATE post_history SET status={p} WHERE id={p}',
                    ('failed', post_id),
                )
                conn.commit()
            except Exception:
                pass

    conn.close()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def init_scheduler():
    """
    Start the APScheduler background thread.
    Call once from app.py at module level. Idempotent.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.debug('scheduler_worker: already running, skipping init')
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _publish_due_posts,
        trigger=IntervalTrigger(seconds=60),
        id='publish_due_posts',
        replace_existing=True,
        misfire_grace_time=30,
        max_instances=1,          # never overlap runs
    )
    _scheduler.start()
    logger.info('scheduler_worker: started (60s poll interval)')


def shutdown_scheduler():
    """Gracefully stop APScheduler. Called on app teardown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info('scheduler_worker: stopped')
