# api_manager.py — Post-Pilot Session 12
# ShadowRealm Network (SRN) compliant /v1/ API layer.
# Handles API key management, SRN auth, and exposes all Post-Pilot tools
# to external callers (Sigil, ShadowRealm, third-party integrations).

import os
import time
import hmac
import hashlib
import secrets
import json
from functools import wraps
from flask import Blueprint, request, jsonify, g
from modules.database import get_db

v1 = Blueprint('v1', __name__, url_prefix='/v1')

APP_NAME    = 'post-pilot'
APP_VERSION = '1.0.0'

# ------------------------------------------------------------------ Auth

def _get_api_key_row(token: str):
    """Look up an API key row by its token value."""
    db = get_db()
    return db.execute(
        'SELECT * FROM api_keys WHERE key_value = ? AND active = 1',
        (token,)
    ).fetchone()

def _get_srn_key():
    """Accept the shared SRN_SECRET as a valid caller key."""
    return os.environ.get('SRN_SECRET', '')

def require_api_key(f):
    """
    Decorator: validates Bearer token from Authorization header.
    Accepts either:
      - A user-issued pp_live_xxx API key  (logs to api_keys table)
      - The shared SRN_SECRET              (for ShadowRealm / Sigil calls)
    Sets g.api_user_id and g.api_caller on success.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth   = request.headers.get('Authorization', '')
        token  = auth.replace('Bearer ', '').replace('bearer ', '').strip()
        caller = request.headers.get('X-SRN-App', 'unknown')

        if not token:
            return _err('Missing Authorization header', 'MISSING_AUTH', 401)

        # --- SRN shared secret ---
        srn_secret = _get_srn_key()
        if srn_secret and token == srn_secret:
            g.api_user_id = None          # SRN calls are not user-scoped
            g.api_caller  = caller
            g.api_key_row = None
            return f(*args, **kwargs)

        # --- User API key ---
        row = _get_api_key_row(token)
        if not row:
            return _err('Invalid or revoked API key', 'INVALID_KEY', 401)

        # Check expiry
        if row['expires_at'] and row['expires_at'] < int(time.time()):
            return _err('API key has expired', 'KEY_EXPIRED', 401)

        # Update last_used
        db = get_db()
        db.execute(
            'UPDATE api_keys SET last_used_at = ?, call_count = call_count + 1 WHERE id = ?',
            (int(time.time()), row['id'])
        )
        db.commit()

        g.api_user_id = row['user_id']
        g.api_caller  = caller
        g.api_key_row = dict(row)
        return f(*args, **kwargs)
    return decorated


def _ok(data=None, **kwargs):
    payload = {'success': True}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return jsonify(payload), 200


def _err(message: str, code: str = 'ERROR', status: int = 400):
    return jsonify({'success': False, 'error': message, 'code': code}), status


# ------------------------------------------------------------------ /v1/health  (public)

@v1.get('/health')
def health():
    return jsonify({
        'status':  'ok',
        'app':     APP_NAME,
        'version': APP_VERSION,
        'uptime':  int(time.time()),   # replace with process start delta in prod
    }), 200


# ------------------------------------------------------------------ /v1/manifest

@v1.get('/manifest')
@require_api_key
def manifest():
    """
    SRN manifest — machine-readable list of all tools Post-Pilot exposes.
    ShadowRealm fetches this on boot to discover what Post-Pilot can do.
    """
    tools = [
        {
            'name':        'generate_post',
            'description': 'Generate an AI social media caption for a topic/platform',
            'method':      'POST',
            'path':        '/v1/generate_post',
            'input': {
                'topic':    {'type': 'string',  'required': True},
                'platform': {'type': 'string',  'required': False,
                             'enum': ['facebook','instagram','tiktok','youtube','google','website']},
                'tone':     {'type': 'string',  'required': False},
                'user_id':  {'type': 'string',  'required': False},
            },
            'output': {'success': 'boolean', 'data': {'caption': 'string', 'hashtags': 'array'}},
        },
        {
            'name':        'publish_post',
            'description': 'Publish a caption to one or more social platforms',
            'method':      'POST',
            'path':        '/v1/publish_post',
            'input': {
                'caption':      {'type': 'string', 'required': True},
                'platforms':    {'type': 'array',  'required': False},
                'user_id':      {'type': 'string', 'required': False},
                'image_url':    {'type': 'string', 'required': False},
                'scheduled_at': {'type': 'integer','required': False,
                                 'description': 'Unix timestamp — omit to publish now'},
            },
            'output': {
                'success': 'boolean',
                'data': {
                    'post_id': 'string',
                    'results': 'object',   # per-platform { success, url }
                },
            },
        },
        {
            'name':        'generate_and_publish',
            'description': 'Generate a caption then immediately publish it — one-shot convenience tool',
            'method':      'POST',
            'path':        '/v1/generate_and_publish',
            'input': {
                'topic':     {'type': 'string', 'required': True},
                'platforms': {'type': 'array',  'required': False},
                'tone':      {'type': 'string',  'required': False},
                'user_id':   {'type': 'string',  'required': False},
                'image_url': {'type': 'string',  'required': False},
            },
            'output': {'success': 'boolean', 'data': {'caption': 'string', 'post_id': 'string', 'results': 'object'}},
        },
        {
            'name':        'get_history',
            'description': 'Get recent post history for a user',
            'method':      'GET',
            'path':        '/v1/get_history',
            'input': {
                'user_id': {'type': 'string',  'required': False},
                'limit':   {'type': 'integer', 'required': False},
            },
            'output': {'success': 'boolean', 'data': {'posts': 'array'}},
        },
        {
            'name':        'get_site_config',
            'description': 'Get the website hub config for a user',
            'method':      'GET',
            'path':        '/v1/get_site_config',
            'input': {'user_id': {'type': 'string', 'required': False}},
            'output': {'success': 'boolean', 'data': 'object'},
        },
        {
            'name':        'set_published',
            'description': 'Publish or unpublish a user website',
            'method':      'POST',
            'path':        '/v1/set_published',
            'input': {
                'published': {'type': 'boolean', 'required': True},
                'user_id':   {'type': 'string',  'required': False},
            },
            'output': {'success': 'boolean'},
        },
    ]
    return _ok({'app': APP_NAME, 'version': APP_VERSION, 'tools': tools})


# ------------------------------------------------------------------ /v1/generate_post

@v1.post('/generate_post')
@require_api_key
def generate_post():
    body      = request.get_json(silent=True) or {}
    topic     = body.get('topic', '').strip()
    platform  = body.get('platform', 'instagram')
    tone      = body.get('tone', 'engaging')
    user_id   = body.get('user_id') or g.api_user_id

    if not topic:
        return _err('topic is required', 'MISSING_TOPIC')

    try:
        from modules.post_generator import PostGenerator
        gen     = PostGenerator(user_id=user_id)
        result  = gen.generate(topic=topic, platform=platform, tone=tone)
        return _ok(result)
    except Exception as e:
        return _err(str(e), 'GENERATION_ERROR', 500)


# ------------------------------------------------------------------ /v1/publish_post

@v1.post('/publish_post')
@require_api_key
def publish_post():
    body         = request.get_json(silent=True) or {}
    caption      = body.get('caption', '').strip()
    platforms    = body.get('platforms') or ['facebook', 'instagram']
    user_id      = body.get('user_id') or g.api_user_id
    image_url    = body.get('image_url')
    scheduled_at = body.get('scheduled_at')

    if not caption:
        return _err('caption is required', 'MISSING_CAPTION')
    if not user_id:
        return _err('user_id is required when using SRN secret auth', 'MISSING_USER_ID')

    try:
        from modules.publisher import Publisher
        pub    = Publisher(user_id=user_id)
        result = pub.publish(
            caption=caption,
            platforms=platforms,
            image_url=image_url,
            scheduled_at=scheduled_at,
        )
        return _ok(result)
    except Exception as e:
        return _err(str(e), 'PUBLISH_ERROR', 500)


# ------------------------------------------------------------------ /v1/generate_and_publish

@v1.post('/generate_and_publish')
@require_api_key
def generate_and_publish():
    """One-shot: generate caption then publish. Used by Sigil's /post command."""
    body      = request.get_json(silent=True) or {}
    topic     = body.get('topic', '').strip()
    platforms = body.get('platforms') or ['facebook', 'instagram']
    tone      = body.get('tone', 'engaging')
    user_id   = body.get('user_id') or g.api_user_id
    image_url = body.get('image_url')

    if not topic:
        return _err('topic is required', 'MISSING_TOPIC')
    if not user_id:
        return _err('user_id required for SRN secret auth', 'MISSING_USER_ID')

    try:
        from modules.post_generator import PostGenerator
        from modules.publisher import Publisher

        gen    = PostGenerator(user_id=user_id)
        gen_result = gen.generate(topic=topic, platform=platforms[0] if platforms else 'instagram', tone=tone)
        caption = gen_result.get('caption', topic)

        pub    = Publisher(user_id=user_id)
        pub_result = pub.publish(
            caption=caption,
            platforms=platforms,
            image_url=image_url,
        )
        return _ok({
            'caption': caption,
            'hashtags': gen_result.get('hashtags', []),
            **pub_result,
        })
    except Exception as e:
        return _err(str(e), 'GENERATE_AND_PUBLISH_ERROR', 500)


# ------------------------------------------------------------------ /v1/get_history

@v1.get('/get_history')
@require_api_key
def get_history():
    user_id = request.args.get('user_id') or g.api_user_id
    limit   = min(int(request.args.get('limit', 20)), 100)

    if not user_id:
        return _err('user_id required', 'MISSING_USER_ID')

    db   = get_db()
    rows = db.execute(
        '''
        SELECT id, caption, platforms, status, created_at, post_url
        FROM   post_history
        WHERE  user_id = ?
        ORDER  BY created_at DESC
        LIMIT  ?
        ''',
        (user_id, limit)
    ).fetchall()

    posts = []
    for r in rows:
        p = dict(r)
        if p.get('platforms'):
            try:
                p['platforms'] = json.loads(p['platforms'])
            except Exception:
                pass
        posts.append(p)

    return _ok({'posts': posts, 'count': len(posts)})


# ------------------------------------------------------------------ /v1/get_site_config

@v1.get('/get_site_config')
@require_api_key
def get_site_config():
    user_id = request.args.get('user_id') or g.api_user_id
    if not user_id:
        return _err('user_id required', 'MISSING_USER_ID')
    try:
        from modules.website_manager import WebsiteManager
        wm   = WebsiteManager(user_id=user_id)
        site = wm.get_site()
        return _ok(site)
    except Exception as e:
        return _err(str(e), 'SITE_CONFIG_ERROR', 500)


# ------------------------------------------------------------------ /v1/set_published

@v1.post('/set_published')
@require_api_key
def set_published():
    body      = request.get_json(silent=True) or {}
    user_id   = body.get('user_id') or g.api_user_id
    published = body.get('published')

    if not user_id:
        return _err('user_id required', 'MISSING_USER_ID')
    if published is None:
        return _err('published (boolean) required', 'MISSING_PUBLISHED')

    try:
        from modules.website_manager import WebsiteManager
        wm     = WebsiteManager(user_id=user_id)
        result = wm.set_published(bool(published))
        return _ok(result)
    except Exception as e:
        return _err(str(e), 'SET_PUBLISHED_ERROR', 500)


# ------------------------------------------------------------------ API Key Management
# These routes are for the Post-Pilot dashboard — users manage their own keys.
# Auth here uses Flask-Login session (not API key), so no @require_api_key.

@v1.post('/keys/create')
def create_api_key():
    """Create a new API key for the logged-in user."""
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return _err('Login required', 'UNAUTHENTICATED', 401)

        body  = request.get_json(silent=True) or {}
        label = body.get('label', 'My Key')[:64]
        ttl   = body.get('ttl_days')   # None = no expiry

        token      = 'pp_live_' + secrets.token_urlsafe(32)
        expires_at = int(time.time()) + ttl * 86400 if ttl else None

        db = get_db()
        db.execute(
            '''
            INSERT INTO api_keys
              (user_id, label, key_value, active, created_at, expires_at, call_count)
            VALUES (?, ?, ?, 1, ?, ?, 0)
            ''',
            (current_user.id, label, token, int(time.time()), expires_at)
        )
        db.commit()
        return _ok({'key': token, 'label': label, 'expires_at': expires_at})
    except Exception as e:
        return _err(str(e), 'KEY_CREATE_ERROR', 500)


@v1.get('/keys')
def list_api_keys():
    """List API keys for the logged-in user (values redacted)."""
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return _err('Login required', 'UNAUTHENTICATED', 401)

        db   = get_db()
        rows = db.execute(
            '''
            SELECT id, label, active, created_at, expires_at, last_used_at, call_count,
                   substr(key_value,1,12) || '...' AS key_preview
            FROM   api_keys
            WHERE  user_id = ?
            ORDER  BY created_at DESC
            ''',
            (current_user.id,)
        ).fetchall()
        return _ok({'keys': [dict(r) for r in rows]})
    except Exception as e:
        return _err(str(e), 'KEY_LIST_ERROR', 500)


@v1.post('/keys/revoke')
def revoke_api_key():
    """Revoke an API key by id."""
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return _err('Login required', 'UNAUTHENTICATED', 401)

        body   = request.get_json(silent=True) or {}
        key_id = body.get('key_id')
        if not key_id:
            return _err('key_id required', 'MISSING_KEY_ID')

        db = get_db()
        db.execute(
            'UPDATE api_keys SET active = 0 WHERE id = ? AND user_id = ?',
            (key_id, current_user.id)
        )
        db.commit()
        return _ok({'revoked': True})
    except Exception as e:
        return _err(str(e), 'KEY_REVOKE_ERROR', 500)


# ------------------------------------------------------------------ DB schema helper

CREATE_API_KEYS_TABLE = '''
CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT    NOT NULL,
    label        TEXT    NOT NULL DEFAULT 'My Key',
    key_value    TEXT    NOT NULL UNIQUE,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   INTEGER,
    expires_at   INTEGER,
    last_used_at INTEGER,
    call_count   INTEGER NOT NULL DEFAULT 0
);
'''
