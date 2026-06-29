"""
blueprintsspecials.py
Specials schedule CRUD endpoints + /schedule page route.

Now serves the unified /schedule page (tabbed: Specials / Events / Hours).
The schedule.html template also handles Events and Hours via their own
blueprints (/api/events, /api/hours), but the page route lives here.

Routes:
  GET  /schedule                     -- schedule management page
  GET  /api/specials                 -- list
  POST /api/specials                 -- create
  PUT  /api/specials/<id>            -- update (pending only)
  DELETE /api/specials/<id>          -- delete
  POST /api/specials/<id>/cancel     -- cancel
"""

import json
import logging
import time
from datetime import datetime

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required

from blueprints.utils import _uid

specials_bp = Blueprint('specials', __name__)
logger      = logging.getLogger(__name__)

UI_PLATFORMS = [
    {'key': 'fb',  'label': 'Facebook'},
    {'key': 'ig',  'label': 'Instagram'},
    {'key': 'tt',  'label': 'TikTok'},
    {'key': 'yt',  'label': 'YouTube'},
    {'key': 'yts', 'label': 'YouTube Shorts'},
    {'key': 'tw',  'label': 'Twitter / X'},
    {'key': 'gb',  'label': 'Google Business'},
    {'key': 'web', 'label': 'Website Banner'},
]

CONTENT_TYPES = ['daily_special', 'location', 'general']
TONES         = ['friendly', 'hype', 'urgent', 'funny', 'community']


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@specials_bp.route('/schedule')
@login_required
def schedule_page():
    return render_template(
        'schedule.html',
        ui_platforms  = UI_PLATFORMS,
        content_types = CONTENT_TYPES,
        tones         = TONES,
    )


# ---------------------------------------------------------------------------
# API: List
# ---------------------------------------------------------------------------

@specials_bp.route('/api/specials', methods=['GET'])
@login_required
def api_list_specials():
    uid = _uid()
    try:
        from app import get_db
        db   = get_db()
        rows = db.execute(
            'SELECT id, item_name, description, post_date, post_time, '
            'platforms, content_type, tone, image_url, status, post_history_id, created_at '
            'FROM specials WHERE user_id = ? '
            'ORDER BY post_date ASC, post_time ASC',
            (uid,)
        ).fetchall()
        specials = []
        for r in rows:
            specials.append({
                'id':              r['id'],
                'item_name':       r['item_name'],
                'description':     r['description'],
                'post_date':       r['post_date'],
                'post_time':       r['post_time'],
                'platforms':       json.loads(r['platforms'] or '[]'),
                'content_type':    r['content_type'],
                'tone':            r['tone'],
                'image_url':       r['image_url'],
                'status':          r['status'],
                'post_history_id': r['post_history_id'],
                'created_at':      r['created_at'],
            })
        return jsonify({'success': True, 'specials': specials})
    except Exception:
        logger.exception('api_list_specials failed for user %s', uid)
        return jsonify({'success': False, 'error': 'Could not load specials'}), 500


# ---------------------------------------------------------------------------
# API: Create
# ---------------------------------------------------------------------------

@specials_bp.route('/api/specials', methods=['POST'])
@login_required
def api_create_special():
    uid  = _uid()
    data = request.json or {}

    item_name    = (data.get('item_name') or '').strip()
    post_date    = (data.get('post_date') or '').strip()
    post_time    = (data.get('post_time') or '11:00').strip()
    description  = (data.get('description') or '').strip()
    content_type = data.get('content_type', 'daily_special')
    tone         = data.get('tone', 'friendly')
    image_url    = (data.get('image_url') or '').strip() or None
    platforms    = data.get('platforms') or ['fb', 'ig', 'tt', 'gb', 'web']

    errors = []
    if not item_name: errors.append('item_name is required')
    if not post_date: errors.append('post_date is required (YYYY-MM-DD)')
    else:
        try: datetime.strptime(post_date, '%Y-%m-%d')
        except ValueError: errors.append('post_date must be YYYY-MM-DD')
    try: datetime.strptime(post_time, '%H:%M')
    except ValueError: errors.append('post_time must be HH:MM (24h)')
    if content_type not in CONTENT_TYPES: content_type = 'daily_special'
    if tone not in TONES: tone = 'friendly'
    if not isinstance(platforms, list) or not platforms:
        errors.append('platforms must be a non-empty list')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    now_ts = int(time.time())
    try:
        from app import get_db
        db  = get_db()
        cur = db.execute(
            'INSERT INTO specials '
            '(user_id, item_name, description, post_date, post_time, platforms, '
            ' content_type, tone, image_url, status, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (uid, item_name, description or None, post_date, post_time,
             json.dumps(platforms), content_type, tone,
             image_url, 'pending', now_ts, now_ts)
        )
        db.commit()
        return jsonify({'success': True, 'id': cur.lastrowid}), 201
    except Exception:
        logger.exception('api_create_special failed for user %s', uid)
        return jsonify({'success': False, 'error': 'Could not create special'}), 500


# ---------------------------------------------------------------------------
# API: Update
# ---------------------------------------------------------------------------

@specials_bp.route('/api/specials/<int:special_id>', methods=['PUT'])
@login_required
def api_update_special(special_id):
    uid  = _uid()
    data = request.json or {}
    try:
        from app import get_db
        db  = get_db()
        row = db.execute(
            'SELECT status FROM specials WHERE id = ? AND user_id = ?', (special_id, uid)
        ).fetchone()
    except Exception:
        return jsonify({'success': False, 'error': 'Special not found'}), 404
    if not row: return jsonify({'success': False, 'error': 'Special not found'}), 404
    if row['status'] != 'pending':
        return jsonify({'success': False, 'error': f'Cannot edit a {row["status"]} special'}), 409

    fields, values = [], []
    if 'item_name' in data and data['item_name'].strip():
        fields.append('item_name = ?'); values.append(data['item_name'].strip())
    if 'description' in data:
        fields.append('description = ?'); values.append(data['description'] or None)
    if 'post_date' in data:
        try: datetime.strptime(data['post_date'], '%Y-%m-%d')
        except ValueError: return jsonify({'success': False, 'error': 'post_date must be YYYY-MM-DD'}), 400
        fields.append('post_date = ?'); values.append(data['post_date'])
    if 'post_time' in data:
        try: datetime.strptime(data['post_time'], '%H:%M')
        except ValueError: return jsonify({'success': False, 'error': 'post_time must be HH:MM'}), 400
        fields.append('post_time = ?'); values.append(data['post_time'])
    if 'platforms' in data and isinstance(data['platforms'], list):
        fields.append('platforms = ?'); values.append(json.dumps(data['platforms']))
    if 'content_type' in data and data['content_type'] in CONTENT_TYPES:
        fields.append('content_type = ?'); values.append(data['content_type'])
    if 'tone' in data and data['tone'] in TONES:
        fields.append('tone = ?'); values.append(data['tone'])
    if 'image_url' in data:
        fields.append('image_url = ?'); values.append(data['image_url'] or None)
    if not fields: return jsonify({'success': True, 'message': 'Nothing to update'})
    fields.append('updated_at = ?'); values.append(int(time.time()))
    values.extend([special_id, uid])
    try:
        db.execute(f'UPDATE specials SET {", ".join(fields)} WHERE id = ? AND user_id = ?', values)
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_update_special failed for special %s user %s', special_id, uid)
        return jsonify({'success': False, 'error': 'Update failed'}), 500


# ---------------------------------------------------------------------------
# API: Delete
# ---------------------------------------------------------------------------

@specials_bp.route('/api/specials/<int:special_id>', methods=['DELETE'])
@login_required
def api_delete_special(special_id):
    uid = _uid()
    try:
        from app import get_db
        db = get_db()
        db.execute('DELETE FROM specials WHERE id = ? AND user_id = ?', (special_id, uid))
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_delete_special failed for special %s user %s', special_id, uid)
        return jsonify({'success': False, 'error': 'Delete failed'}), 500


# ---------------------------------------------------------------------------
# API: Cancel
# ---------------------------------------------------------------------------

@specials_bp.route('/api/specials/<int:special_id>/cancel', methods=['POST'])
@login_required
def api_cancel_special(special_id):
    uid = _uid()
    try:
        from app import get_db
        db = get_db()
        db.execute(
            'UPDATE specials SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?',
            ('cancelled', int(time.time()), special_id, uid)
        )
        db.commit()
        return jsonify({'success': True})
    except Exception:
        logger.exception('api_cancel_special failed for special %s user %s', special_id, uid)
        return jsonify({'success': False, 'error': 'Cancel failed'}), 500
