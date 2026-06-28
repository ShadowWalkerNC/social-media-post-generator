"""
modules/automation_agent.py
Post-Pilot Autonomous Content Agent  (v2 -- specials-driven)

The agent runs every hour via Vercel Cron -> POST /api/cron/generate.
Instead of inventing content, it reads the user's specials table and
generates posts for any items scheduled for today that are still pending.

Flow:
  1. For each user with a completed business profile:
  2. Query specials WHERE post_date = today AND status = 'pending'
  3. For each due special:
       a. Generate per-platform captions via OpenAI (master + adapt)
       b. Parse post_time -> Unix timestamp for scheduled_at
       c. Write post_history row (status='scheduled')
       d. Update special.status = 'queued', special.post_history_id = <id>
       e. Write automation_log audit row

The cron job at /api/cron/publish (every minute) picks up the scheduled
post_history rows and pushes them live via UniversalPublisher.

Active platforms: fb, ig, tt, yt, yts, tw, gb, web
(LinkedIn and Pinterest excluded until publishers are implemented)
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from modules.db import get_connection, placeholder

logger = logging.getLogger(__name__)

# Platforms the agent will generate content for.
ACTIVE_PLATFORMS: List[str] = ['fb', 'ig', 'tt', 'yt', 'yts', 'tw', 'gb', 'web']


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_for_all_users() -> Dict:
    """
    Entry point called by POST /api/cron/generate.
    Iterates all users with complete business profiles and queues any
    specials due today that are still pending.

    Returns a summary dict for the cron endpoint to log/return.
    """
    conn    = get_connection()
    today   = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    summary = {'processed': 0, 'queued': 0, 'skipped': 0, 'errors': 0}

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, name, business_type, location, hours, ai_tone "
            "FROM business_profiles "
            "WHERE name IS NOT NULL AND name != ''"
        )
        users = cur.fetchall()
    except Exception as e:
        logger.error('automation_agent: failed to load business profiles: %s', e)
        conn.close()
        return {**summary, 'error': str(e)}

    for row in users:
        profile = _row_to_dict(row, ['user_id', 'name', 'business_type', 'location', 'hours', 'ai_tone'])
        summary['processed'] += 1
        try:
            queued = _process_user(conn, profile, today)
            summary['queued']  += queued
            summary['skipped'] += 1 if queued == 0 else 0
        except Exception as e:
            logger.error('automation_agent: error for user %s: %s', profile.get('user_id'), e)
            summary['errors'] += 1

    conn.close()
    logger.info('automation_agent: run complete %s', summary)
    return summary


# ---------------------------------------------------------------------------
# Per-user processing
# ---------------------------------------------------------------------------

def _process_user(conn, profile: Dict, today: str) -> int:
    """
    Queue all pending specials for today for a single user.
    Returns the number of posts queued.
    """
    user_id = profile['user_id']
    p       = placeholder
    queued  = 0

    # Load all pending specials due today
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, item_name, description, post_date, post_time, "
            f"platforms, content_type, tone, image_url "
            f"FROM specials "
            f"WHERE user_id = {p} AND post_date = {p} AND status = 'pending'",
            (user_id, today)
        )
        specials = cur.fetchall()
    except Exception as e:
        logger.error('automation_agent: failed to load specials for user %s: %s', user_id, e)
        return 0

    if not specials:
        logger.info('automation_agent: no pending specials today for user %s', user_id)
        return 0

    for row in specials:
        special = _row_to_dict(row, [
            'id', 'item_name', 'description', 'post_date', 'post_time',
            'platforms', 'content_type', 'tone', 'image_url',
        ])
        try:
            ok = _queue_special(conn, profile, special)
            if ok:
                queued += 1
        except Exception as e:
            logger.error(
                'automation_agent: failed to queue special %s for user %s: %s',
                special.get('id'), user_id, e
            )

    return queued


def _queue_special(conn, profile: Dict, special: Dict) -> bool:
    """
    Generate captions for one special and write a post_history row.
    Marks the special as 'queued' on success.
    Returns True on success.
    """
    user_id      = profile['user_id']
    special_id   = special['id']
    content_type = special.get('content_type') or 'daily_special'
    tone         = special.get('tone') or profile.get('ai_tone') or 'friendly'
    image_url    = special.get('image_url')

    # Resolve platforms: use special-level override or fall back to ACTIVE_PLATFORMS
    platforms_raw = special.get('platforms')
    try:
        platforms = json.loads(platforms_raw) if platforms_raw else ACTIVE_PLATFORMS
    except (TypeError, ValueError):
        platforms = ACTIVE_PLATFORMS

    # Build business_info for AI generator
    business_info = {
        'name':     profile.get('name', 'Our Business'),
        'type':     profile.get('business_type', 'restaurant'),
        'location': profile.get('location', ''),
        'hours':    profile.get('hours', ''),
        'special':  special.get('item_name', 'Today\'s Special'),
    }

    # Keywords from special description
    description = special.get('description') or ''
    keywords    = [k.strip() for k in description.split(',') if k.strip()] if description else []

    # 1. Generate captions via OpenAI
    try:
        from modules.ai_generator import generate_with_adaptations
        result   = generate_with_adaptations(
            business_info = business_info,
            content_type  = content_type,
            tone          = tone,
            keywords      = keywords,
            platforms     = platforms,
        )
        master   = result['master']
        captions = result['adapted']
    except Exception as e:
        logger.error('automation_agent: generation failed for special %s: %s', special_id, e)
        return False

    # 2. Calculate scheduled_at from post_date + post_time
    scheduled_at = _parse_scheduled_at(special['post_date'], special['post_time'])
    now_ts       = int(time.time())
    p            = placeholder

    # 3. Write post_history row
    try:
        cur = conn.cursor()
        cur.execute(
            f'INSERT INTO post_history '
            f'(user_id, caption, content_type, image_url, platforms, status, scheduled_at, results, created_at) '
            f'VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})',
            (
                user_id,
                master,
                content_type,
                image_url,
                json.dumps(platforms),
                'scheduled',
                scheduled_at,
                json.dumps({'captions': captions, 'special_id': special_id}),
                now_ts,
            )
        )
        post_id = cur.lastrowid
        conn.commit()
        logger.info(
            'automation_agent: queued post %s for user %s special "%s" at %s',
            post_id, user_id, special.get('item_name'), scheduled_at
        )
    except Exception as e:
        logger.error('automation_agent: failed to write post_history for special %s: %s', special_id, e)
        return False

    # 4. Mark special as queued
    try:
        cur.execute(
            f"UPDATE specials SET status = 'queued', post_history_id = {p}, updated_at = {p} "
            f"WHERE id = {p}",
            (post_id, now_ts, special_id)
        )
        conn.commit()
    except Exception as e:
        logger.warning('automation_agent: failed to update special status %s: %s', special_id, e)
        # Non-fatal: post is queued, just the status flag didn't update

    # 5. Write automation_log audit row
    _write_log(conn, user_id, post_id, special_id, content_type, tone, keywords, master, scheduled_at)

    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_scheduled_at(post_date: str, post_time: str) -> int:
    """
    Parse 'YYYY-MM-DD' + 'HH:MM' -> Unix timestamp (UTC).
    Falls back to midnight UTC if parsing fails.
    """
    try:
        dt = datetime.strptime(f'{post_date} {post_time}', '%Y-%m-%d %H:%M')
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        try:
            dt = datetime.strptime(post_date, '%Y-%m-%d')
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            return int(time.time())


def _row_to_dict(row, keys: List[str]) -> Dict:
    """Normalise a DB row (sqlite3.Row or psycopg2 RealDictRow or tuple) to a plain dict."""
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)          # sqlite3.Row supports dict()
    except Exception:
        return dict(zip(keys, row))


def _write_log(
    conn,
    user_id:      str,
    post_id:      int,
    special_id:   int,
    content_type: str,
    tone:         str,
    keywords:     List[str],
    master:       str,
    scheduled_at: int,
) -> None:
    """Write an audit row to automation_log. Failure is non-fatal."""
    p = placeholder
    try:
        cur = conn.cursor()
        cur.execute(
            f'INSERT INTO automation_log '
            f'(user_id, post_id, content_type, tone, keywords, master_caption, scheduled_at, created_at) '
            f'VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})',
            (
                user_id,
                post_id,
                content_type,
                tone,
                json.dumps(keywords),
                master,
                scheduled_at,
                int(time.time()),
            )
        )
        conn.commit()
    except Exception as e:
        logger.warning('automation_agent: failed to write automation_log for special %s: %s', special_id, e)
