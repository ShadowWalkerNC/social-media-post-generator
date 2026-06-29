"""
blueprintsevents.py
Events CRUD endpoints + /events page.

Routes:
  GET  /api/events                  list all events for current user
  POST /api/events                  create
  PUT  /api/events/<id>             update (pending only)
  DELETE /api/events/<id>           delete
  POST /api/events/<id>/cancel      cancel (sets status=cancelled)

Event types: event | happy_hour | pop_up | concert | market | general
"""

import json
import logging
import time
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_login import login_required

from blueprints.utils import _uid

events_bp = Blueprint('events', __name__)
logger    = logging.getLogger(__name__)

EVENT_TYPES = ['event', 'happy_hour', 'pop_up', 'concert', 'market', 'general']
TONES       = ['friendly', 'hype', 'urgent', 'funny', 'community']
DEFAULT_PLATFORMS = ['fb', 'ig', 'tt', 'gb', 'web']


def _db():
    from app import get_db
    return get_db()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@events_bp.route('/api/events', methods=['GET'])
@login_required
def api_list_events():
    uid = _uid()
    try:
        rows = _db().execute(
            'SELECT id, title, description, event_date, event_end_date, post_date, post_time, '
            'event_type, platforms, tone, image_url, ticket_url, status, post_history_id, created_at '
            'FROM events WHERE user_id = ? ORDER BY post_date ASC, post_time ASC',
            (uid,)
        ).fetchall()
        return jsonify({'success': True, 'events': [
            {
                'id':              r['id'],
                'title':          r['title'],
                'description':    r['description'],
                'event_date':     r['event_date'],
                'event_end_date': r['event_end_date'],
                'post_date':      r['post_date'],
                'post_time':      r['post_time'],
                'event_type':     r['event_type'],
                'platforms':      json.loads(r['platforms'] or '[]'),
                'tone':           r['tone'],
                'image_url':      r['image_url'],
                'ticket_url':     r['ticket_url'],
                'status':         r['status'],
                'post_history_id':r['post_history_id'],
                'created_at':     r['created_at'],
            } for r in rows
        ]})
    except Exception:
        logger.exception('api_list_events failed for user %s', uid)
        return jsonify({'success': False, 'error': 'Could not load events'}), 500


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@events_bp.route('/api/events', methods=['POST'])
@login_required
def api_create_event():
    uid  = _uid()
    data = request.json or {}

    title        = (data.get('title') or '').strip()
    post_date    = (data.get('post_date') or '').strip()
    post_time    = (data.get('post_time') or '11:00').strip()
    event_date   = (data.get('event_date') or post_date).strip()
    event_end    = (data.get('event_end_date') or '').strip() or None
    description  = (data.get('description') or '').strip() or None
    event_type   = data.get('event_type', 'event')
    tone         = data.get('tone', 'hype')
    image_url    = (data.get('image_url') or '').strip() or None
    ticket_url   = (data.get('ticket_url') or '').strip() or None
    platforms    = data.get('platforms') or DEFAULT_PLATFORMS

    errors = []
    if not title:     errors.append('title is required')
    if not post_date: errors.append('post_date is required (YYYY-MM-DD)')
    else:
        try: datetime.strptime(post_date, '%Y-%m-%d')
        except ValueError: errors.append('post_date must be YYYY-MM-DD')
    if not event_date: errors.append('event_date is required (YYYY-MM-DD)')
    else:
        try: datetime.strptime(event_date, '%Y-%m-%d')
        except ValueError: errors.append('event_date must be YYYY-MM-DD')
    try: datetime.strptime(post_time, '%H:%M')
    except ValueError: errors.append('post_time must be HH:MM (24h)')
    if event_type not in EVENT_TYPES: event_type = 'event'
    if tone not in TONES: tone = 'hype'
    if not isinstance(platforms, list) or not platforms:
        errors.append('platforms must be a non-empty list')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    now_ts = int(time.time())
    try:
        db  = _db()
        cur = db.execute(
            'INSERT INTO events '
            '(user_id, title, description, event_date, event_end_date, post_date, post_time, '
            ' event_type, platforms, tone, image_url, ticket_url, status, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (uid, title, description, event_date, event_end, post_date, post_time,
             event_type, json.dumps(platforms), tone, image_url, ticket_url,
             'pending', now_ts, now_ts)
        )
        db.commit()
        return jsonify({'success': True, 'id': cur.lastrowid}), 201
    except Exception:
        logger.exception('api_create_event failed for user %s', uid)
        return jsonify({'success': False, 'error': 'Could not create event'}), 500


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@events_bp.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def api_update_event(event_id):
    uid  = _uid()
    data = request.json or {}
    db   = _db()
    row  = db.execute('SELECT status FROM events WHERE id=? AND user_id=?', (event_id, uid)).fetchone()
    if not row:                      return jsonify({'success': False, 'error': 'Event not found'}), 404
    if row['status'] != 'pending':   return jsonify({'success': False, 'error': f'Cannot edit a {row["status"]} event'}), 409

    fields, values = [], []
    for col in ('title', 'description', 'event_date', 'event_end_date', 'post_date',
                'post_time', 'event_type', 'tone', 'image_url', 'ticket_url'):
        if col in data:
            if col in ('event_date', 'post_date') and data[col]:
                try: datetime.strptime(data[col], '%Y-%m-%d')
                except ValueError: return jsonify({'success': False, 'error': f'{col} must be YYYY-MM-DD'}), 400
            if col == 'post_time' and data[col]:
                try: datetime.strptime(data[col], '%H:%M')
                except ValueError: return jsonify({'success': False, 'error': 'post_time must be HH:MM'}), 400
            fields.append(f'{col} = ?'); values.append(data[col] or None)
    if 'platforms' in data and isinstance(data['platforms'], list):
        fields.append('platforms = ?'); values.append(json.dumps(data['platforms']))
    if not fields: return jsonify({'success': True, 'message': 'Nothing to update'})
    fields.append('updated_at = ?'); values.append(int(time.time()))
    values.extend([event_id, uid])
    try:
        db.execute(f'UPDATE events SET {", ".join(fields)} WHERE id=? AND user_id=?', values)
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_update_event failed %s', event_id)
        return jsonify({'success': False, 'error': 'Update failed'}), 500


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@events_bp.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def api_delete_event(event_id):
    uid = _uid()
    try:
        db = _db()
        db.execute('DELETE FROM events WHERE id=? AND user_id=?', (event_id, uid))
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_delete_event failed %s', event_id)
        return jsonify({'success': False, 'error': 'Delete failed'}), 500


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@events_bp.route('/api/events/<int:event_id>/cancel', methods=['POST'])
@login_required
def api_cancel_event(event_id):
    uid = _uid()
    try:
        db = _db()
        db.execute('UPDATE events SET status=?, updated_at=? WHERE id=? AND user_id=?',
                   ('cancelled', int(time.time()), event_id, uid))
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_cancel_event failed %s', event_id)
        return jsonify({'success': False, 'error': 'Cancel failed'}), 500
