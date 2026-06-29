"""
modules/automation_agent.py
Post-Pilot Autonomous Content Agent  (v3 -- specials + events + hours)

The agent runs every hour via Vercel Cron -> POST /api/cron/generate.
It reads all three schedule tables and queues posts for anything due today
that is still pending.

Queue order (all run for today):
  1. specials       -- daily specials (food/drink/product)
  2. events         -- event promos (concerts, happy hours, pop-ups)
  3. hours_overrides-- hours/closure announcements

For each item:
  a. Generate per-platform captions via OpenAI
  b. Parse post_time -> Unix timestamp
  c. Write post_history row (status='scheduled')
  d. Mark source row status='queued'
  e. Write automation_log audit row

Content-type mapping:
  specials       -> content_type from row (default 'daily_special')
  events         -> event_type from row   (default 'event')
  hours_overrides-> override_type from row (default 'hours_update')
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from modules.db import get_connection, placeholder

logger = logging.getLogger(__name__)

ACTIVE_PLATFORMS: List[str] = ['fb', 'ig', 'tt', 'yt', 'yts', 'tw', 'gb', 'web']


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_for_all_users() -> Dict:
    conn    = get_connection()
    today   = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    summary = {'processed': 0, 'queued': 0, 'skipped': 0, 'errors': 0}

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, name, business_type, location, hours, ai_tone "
            "FROM business_profiles WHERE name IS NOT NULL AND name != ''"
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
    user_id = profile['user_id']
    queued  = 0
    queued += _process_specials(conn, profile, today)
    queued += _process_events(conn, profile, today)
    queued += _process_hours(conn, profile, today)
    return queued


# ---------------------------------------------------------------------------
# Specials
# ---------------------------------------------------------------------------

def _process_specials(conn, profile: Dict, today: str) -> int:
    user_id = profile['user_id']
    p       = placeholder
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, item_name, description, post_date, post_time, "
            f"platforms, content_type, tone, image_url "
            f"FROM specials WHERE user_id={p} AND post_date={p} AND status='pending'",
            (user_id, today)
        )
        rows = cur.fetchall()
    except Exception as e:
        logger.error('agent specials query failed user %s: %s', user_id, e)
        return 0

    queued = 0
    for row in rows:
        s = _row_to_dict(row, ['id','item_name','description','post_date','post_time',
                               'platforms','content_type','tone','image_url'])
        business_info = _build_business_info(profile, extra={'special': s.get('item_name','')})
        keywords      = _keywords_from(s.get('description'))
        platforms     = _parse_platforms(s.get('platforms'))
        content_type  = s.get('content_type') or 'daily_special'
        tone          = s.get('tone') or profile.get('ai_tone') or 'friendly'
        ok = _queue_item(
            conn, profile, s['id'], 'specials',
            title        = s.get('item_name', 'Today\'s Special'),
            business_info= business_info,
            content_type = content_type,
            tone         = tone,
            keywords     = keywords,
            platforms    = platforms,
            post_date    = s['post_date'],
            post_time    = s['post_time'],
            image_url    = s.get('image_url'),
        )
        if ok: queued += 1
    return queued


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def _process_events(conn, profile: Dict, today: str) -> int:
    user_id = profile['user_id']
    p       = placeholder
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, title, description, event_date, post_date, post_time, "
            f"event_type, platforms, tone, image_url, ticket_url "
            f"FROM events WHERE user_id={p} AND post_date={p} AND status='pending'",
            (user_id, today)
        )
        rows = cur.fetchall()
    except Exception as e:
        logger.error('agent events query failed user %s: %s', user_id, e)
        return 0

    queued = 0
    for row in rows:
        ev = _row_to_dict(row, ['id','title','description','event_date','post_date','post_time',
                                'event_type','platforms','tone','image_url','ticket_url'])
        desc = ev.get('description') or ''
        if ev.get('ticket_url'):
            desc = (desc + f' Tickets: {ev["ticket_url"]}').strip()
        business_info = _build_business_info(
            profile,
            extra={'event': ev.get('title',''), 'event_date': ev.get('event_date','')}
        )
        keywords     = _keywords_from(desc)
        platforms    = _parse_platforms(ev.get('platforms'))
        content_type = ev.get('event_type') or 'event'
        tone         = ev.get('tone') or profile.get('ai_tone') or 'hype'
        ok = _queue_item(
            conn, profile, ev['id'], 'events',
            title        = ev.get('title', 'Upcoming Event'),
            business_info= business_info,
            content_type = content_type,
            tone         = tone,
            keywords     = keywords,
            platforms    = platforms,
            post_date    = ev['post_date'],
            post_time    = ev['post_time'],
            image_url    = ev.get('image_url'),
        )
        if ok: queued += 1
    return queued


# ---------------------------------------------------------------------------
# Hours overrides
# ---------------------------------------------------------------------------

def _process_hours(conn, profile: Dict, today: str) -> int:
    user_id = profile['user_id']
    p       = placeholder
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, title, message, override_type, post_date, post_time, platforms, tone "
            f"FROM hours_overrides WHERE user_id={p} AND post_date={p} AND status='pending'",
            (user_id, today)
        )
        rows = cur.fetchall()
    except Exception as e:
        logger.error('agent hours query failed user %s: %s', user_id, e)
        return 0

    queued = 0
    for row in rows:
        h = _row_to_dict(row, ['id','title','message','override_type','post_date','post_time','platforms','tone'])
        business_info = _build_business_info(
            profile,
            extra={'hours_update': h.get('title',''), 'detail': h.get('message','')}
        )
        keywords     = _keywords_from(h.get('message'))
        platforms    = _parse_platforms(h.get('platforms'))
        content_type = h.get('override_type') or 'hours_update'
        tone         = h.get('tone') or profile.get('ai_tone') or 'friendly'
        ok = _queue_item(
            conn, profile, h['id'], 'hours_overrides',
            title        = h.get('title', 'Hours Update'),
            business_info= business_info,
            content_type = content_type,
            tone         = tone,
            keywords     = keywords,
            platforms    = platforms,
            post_date    = h['post_date'],
            post_time    = h['post_time'],
            image_url    = None,
        )
        if ok: queued += 1
    return queued


# ---------------------------------------------------------------------------
# Shared queue writer
# ---------------------------------------------------------------------------

def _queue_item(
    conn,
    profile:      Dict,
    source_id:    int,
    source_table: str,
    title:        str,
    business_info:Dict,
    content_type: str,
    tone:         str,
    keywords:     List[str],
    platforms:    List[str],
    post_date:    str,
    post_time:    str,
    image_url:    Optional[str],
) -> bool:
    user_id = profile['user_id']
    p       = placeholder

    # 1. Generate captions
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
        logger.error('agent generation failed for %s#%s: %s', source_table, source_id, e)
        return False

    # 2. scheduled_at
    scheduled_at = _parse_scheduled_at(post_date, post_time)
    now_ts       = int(time.time())

    # 3. Write post_history
    try:
        cur = conn.cursor()
        cur.execute(
            f'INSERT INTO post_history '
            f'(user_id, caption, content_type, image_url, platforms, status, scheduled_at, results, created_at) '
            f'VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p})',
            (
                user_id, master, content_type, image_url,
                json.dumps(platforms), 'scheduled', scheduled_at,
                json.dumps({'captions': captions, 'source': source_table, 'source_id': source_id}),
                now_ts,
            )
        )
        post_id = cur.lastrowid
        conn.commit()
    except Exception as e:
        logger.error('agent post_history insert failed %s#%s: %s', source_table, source_id, e)
        return False

    # 4. Mark source row queued
    try:
        cur.execute(
            f"UPDATE {source_table} SET status='queued', post_history_id={p}, updated_at={p} WHERE id={p}",
            (post_id, now_ts, source_id)
        )
        conn.commit()
    except Exception as e:
        logger.warning('agent status update failed %s#%s: %s', source_table, source_id, e)

    # 5. Audit log
    _write_log(conn, user_id, post_id, source_id, source_table, content_type, tone, keywords, master, scheduled_at)
    logger.info('agent queued post %s for user %s [%s#%s] at %s', post_id, user_id, source_table, source_id, scheduled_at)
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_business_info(profile: Dict, extra: Dict = None) -> Dict:
    info = {
        'name':     profile.get('name', 'Our Business'),
        'type':     profile.get('business_type', 'restaurant'),
        'location': profile.get('location', ''),
        'hours':    profile.get('hours', ''),
    }
    if extra:
        info.update(extra)
    return info


def _parse_platforms(raw) -> List[str]:
    if not raw:
        return ACTIVE_PLATFORMS
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) and result else ACTIVE_PLATFORMS
    except (TypeError, ValueError):
        return ACTIVE_PLATFORMS


def _keywords_from(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [k.strip() for k in text.split(',') if k.strip()]


def _parse_scheduled_at(post_date: str, post_time: str) -> int:
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
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return dict(zip(keys, row))


def _write_log(conn, user_id, post_id, source_id, source_table, content_type, tone, keywords, master, scheduled_at):
    p = placeholder
    try:
        cur = conn.cursor()
        cur.execute(
            f'INSERT INTO automation_log '
            f'(user_id, post_id, content_type, tone, keywords, master_caption, scheduled_at, created_at) '
            f'VALUES ({p},{p},{p},{p},{p},{p},{p},{p})',
            (user_id, post_id, content_type, tone, json.dumps(keywords), master, scheduled_at, int(time.time()))
        )
        conn.commit()
    except Exception as e:
        logger.warning('agent audit log failed source %s#%s: %s', source_table, source_id, e)
