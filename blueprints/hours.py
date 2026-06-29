"""
blueprintshours.py
Hours override CRUD endpoints.

Routes:
  GET  /api/hours                   list all overrides for current user
  POST /api/hours                   create
  PUT  /api/hours/<id>              update (pending only)
  DELETE /api/hours/<id>            delete
  POST /api/hours/<id>/cancel       cancel

Override types: closure | hours_change | holiday | general
Examples:
  - "Closed Monday July 4th"  (closure)
  - "New hours starting next week: Mon-Sat 10am-9pm" (hours_change)
  - "Extended holiday hours — open Christmas Eve till 6pm" (holiday)
"""

import json
import logging
import time
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_login import login_required

from blueprints.utils import _uid

hours_bp = Blueprint('hours', __name__)
logger   = logging.getLogger(__name__)

OVERRIDE_TYPES    = ['closure', 'hours_change', 'holiday', 'general']
TONES             = ['friendly', 'hype', 'urgent', 'funny', 'community']
DEFAULT_PLATFORMS = ['fb', 'ig', 'gb', 'web']


def _db():
    from app import get_db
    return get_db()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@hours_bp.route('/api/hours', methods=['GET'])
@login_required
def api_list_hours():
    uid = _uid()
    try:
        rows = _db().execute(
            'SELECT id, title, message, override_type, post_date, post_time, '
            'platforms, tone, status, post_history_id, created_at '
            'FROM hours_overrides WHERE user_id=? ORDER BY post_date ASC, post_time ASC',
            (uid,)
        ).fetchall()
        return jsonify({'success': True, 'hours': [
            {
                'id':              r['id'],
                'title':          r['title'],
                'message':        r['message'],
                'override_type':  r['override_type'],
                'post_date':      r['post_date'],
                'post_time':      r['post_time'],
                'platforms':      json.loads(r['platforms'] or '[]'),
                'tone':           r['tone'],
                'status':         r['status'],
                'post_history_id':r['post_history_id'],
                'created_at':     r['created_at'],
            } for r in rows
        ]})
    except Exception:
        logger.exception('api_list_hours failed for user %s', uid)
        return jsonify({'success': False, 'error': 'Could not load hours overrides'}), 500


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@hours_bp.route('/api/hours', methods=['POST'])
@login_required
def api_create_hours():
    uid  = _uid()
    data = request.json or {}

    title         = (data.get('title') or '').strip()
    post_date     = (data.get('post_date') or '').strip()
    post_time     = (data.get('post_time') or '09:00').strip()
    message       = (data.get('message') or '').strip() or None
    override_type = data.get('override_type', 'closure')
    tone          = data.get('tone', 'friendly')
    platforms     = data.get('platforms') or DEFAULT_PLATFORMS

    errors = []
    if not title:     errors.append('title is required')
    if not post_date: errors.append('post_date is required (YYYY-MM-DD)')
    else:
        try: datetime.strptime(post_date, '%Y-%m-%d')
        except ValueError: errors.append('post_date must be YYYY-MM-DD')
    try: datetime.strptime(post_time, '%H:%M')
    except ValueError: errors.append('post_time must be HH:MM (24h)')
    if override_type not in OVERRIDE_TYPES: override_type = 'general'
    if tone not in TONES: tone = 'friendly'
    if not isinstance(platforms, list) or not platforms:
        errors.append('platforms must be a non-empty list')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    now_ts = int(time.time())
    try:
        db  = _db()
        cur = db.execute(
            'INSERT INTO hours_overrides '
            '(user_id, title, message, override_type, post_date, post_time, '
            ' platforms, tone, status, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (uid, title, message, override_type, post_date, post_time,
             json.dumps(platforms), tone, 'pending', now_ts, now_ts)
        )
        db.commit()
        return jsonify({'success': True, 'id': cur.lastrowid}), 201
    except Exception:
        logger.exception('api_create_hours failed for user %s', uid)
        return jsonify({'success': False, 'error': 'Could not create hours override'}), 500


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@hours_bp.route('/api/hours/<int:hours_id>', methods=['PUT'])
@login_required
def api_update_hours(hours_id):
    uid  = _uid()
    data = request.json or {}
    db   = _db()
    row  = db.execute('SELECT status FROM hours_overrides WHERE id=? AND user_id=?', (hours_id, uid)).fetchone()
    if not row:                    return jsonify({'success': False, 'error': 'Not found'}), 404
    if row['status'] != 'pending': return jsonify({'success': False, 'error': f'Cannot edit a {row["status"]} override'}), 409

    fields, values = [], []
    for col in ('title', 'message', 'override_type', 'post_date', 'post_time', 'tone'):
        if col in data:
            if col == 'post_date' and data[col]:
                try: datetime.strptime(data[col], '%Y-%m-%d')
                except ValueError: return jsonify({'success': False, 'error': 'post_date must be YYYY-MM-DD'}), 400
            if col == 'post_time' and data[col]:
                try: datetime.strptime(data[col], '%H:%M')
                except ValueError: return jsonify({'success': False, 'error': 'post_time must be HH:MM'}), 400
            fields.append(f'{col} = ?'); values.append(data[col] or None)
    if 'platforms' in data and isinstance(data['platforms'], list):
        fields.append('platforms = ?'); values.append(json.dumps(data['platforms']))
    if not fields: return jsonify({'success': True, 'message': 'Nothing to update'})
    fields.append('updated_at = ?'); values.append(int(time.time()))
    values.extend([hours_id, uid])
    try:
        db.execute(f'UPDATE hours_overrides SET {", ".join(fields)} WHERE id=? AND user_id=?', values)
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_update_hours failed %s', hours_id)
        return jsonify({'success': False, 'error': 'Update failed'}), 500


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@hours_bp.route('/api/hours/<int:hours_id>', methods=['DELETE'])
@login_required
def api_delete_hours(hours_id):
    uid = _uid()
    try:
        db = _db()
        db.execute('DELETE FROM hours_overrides WHERE id=? AND user_id=?', (hours_id, uid))
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_delete_hours failed %s', hours_id)
        return jsonify({'success': False, 'error': 'Delete failed'}), 500


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@hours_bp.route('/api/hours/<int:hours_id>/cancel', methods=['POST'])
@login_required
def api_cancel_hours(hours_id):
    uid = _uid()
    try:
        db = _db()
        db.execute('UPDATE hours_overrides SET status=?, updated_at=? WHERE id=? AND user_id=?',
                   ('cancelled', int(time.time()), hours_id, uid))
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_cancel_hours failed %s', hours_id)
        return jsonify({'success': False, 'error': 'Cancel failed'}), 500
