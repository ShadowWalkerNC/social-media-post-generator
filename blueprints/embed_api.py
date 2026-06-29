"""
blueprints/embed_api.py
Public (no auth required) embed API endpoint.

GET /api/embed/<slug>
    Returns JSON with the business's public data:
    name, tagline, logo_url, hours, services, recent_posts.
    Used by static/embed.js to populate widgets on external sites.
"""

import json
import logging

from flask import Blueprint, jsonify

embed_bp = Blueprint('embed', __name__)
logger   = logging.getLogger(__name__)


@embed_bp.route('/api/embed/<slug>', methods=['GET'])
def public_embed(slug):
    """
    Public endpoint — no login required.
    Slug is matched against users.embed_slug (falls back to username).
    """
    from app import get_db
    db = get_db()

    # ── Look up the user by embed_slug or username ────────────────────
    user_row = None
    try:
        user_row = db.execute(
            'SELECT id FROM users WHERE embed_slug = ? OR username = ? LIMIT 1',
            (slug, slug)
        ).fetchone()
    except Exception:
        # Column embed_slug may not exist yet on older schemas — fall back
        try:
            user_row = db.execute(
                'SELECT id FROM users WHERE username = ? LIMIT 1', (slug,)
            ).fetchone()
        except Exception:
            logger.exception('embed lookup failed for slug %s', slug)

    if not user_row:
        return jsonify({'success': False, 'error': 'Business not found'}), 404

    uid = user_row['id']

    # ── Load business profile ─────────────────────────────────────────
    profile = {}
    try:
        row = db.execute(
            'SELECT business_profile FROM users WHERE id = ?', (uid,)
        ).fetchone()
        if row and row['business_profile']:
            raw = row['business_profile']
            profile = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        logger.exception('embed profile load failed for uid %s', uid)

    # ── Load recent published posts ───────────────────────────────────
    recent_posts = []
    try:
        rows = db.execute(
            '''
            SELECT caption, image_url, created_at
            FROM   post_history
            WHERE  user_id = ?
              AND  status  IN ("published", "success")
            ORDER  BY created_at DESC
            LIMIT  6
            ''',
            (uid,)
        ).fetchall()
        recent_posts = [
            {
                'caption':    row['caption'] or '',
                'image_url':  row['image_url'],
                'created_at': str(row['created_at'] or ''),
            }
            for row in rows
        ]
    except Exception:
        logger.exception('embed posts load failed for uid %s', uid)

    # ── Parse hours (stored as string or dict) ────────────────────────
    hours = profile.get('hours', {})
    if isinstance(hours, str):
        # e.g. "Mon-Fri 9am-5pm" stored as a plain string
        hours = {'Hours': hours}

    # ── Assemble response ─────────────────────────────────────────────
    return jsonify({
        'success':      True,
        'name':         profile.get('name', ''),
        'tagline':      profile.get('tagline', ''),
        'logo_url':     profile.get('logo_url', ''),
        'about':        profile.get('about', ''),
        'hours':        hours,
        'services':     profile.get('services', []),
        'recent_posts': recent_posts,
    })
