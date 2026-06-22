"""
modules/auth_manager.py

╔══════════════════════════════════════════════════════════════════════════╗
║  AUTHORITATIVE TOKEN STORE                                               ║
║  All OAuth access/refresh tokens are stored in the `platform_tokens`    ║
║  table managed by this module.  There is NO second copy anywhere else.  ║
║                                                                          ║
║  Write tokens:  save_token(platform, access_token, ..., user_id=uid)    ║
║  Read tokens:   load_token(platform, user_id)  -> dict | None           ║
║  Delete tokens: delete_token(platform, user_id)                         ║
║  Token refresh: get_valid_google_token(uid) / refresh_tiktok_token(uid) ║
╚══════════════════════════════════════════════════════════════════════════╝

Tokens are Fernet-encrypted at rest using TOKEN_ENCRYPTION_KEY.
Storage backend: SQLite (dev) or PostgreSQL (prod) via modules/db.py.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import requests

from modules.db import get_connection, placeholder, adapt_schema, USE_POSTGRES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption key
# ---------------------------------------------------------------------------
ENCRYPTION_KEY = os.environ.get('TOKEN_ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning('TOKEN_ENCRYPTION_KEY not set -- generated ephemeral key (dev only)')

fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
CREATE_TOKENS_TABLE = adapt_schema('''
    CREATE TABLE IF NOT EXISTS platform_tokens (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       TEXT    NOT NULL DEFAULT 'default',
        platform      TEXT    NOT NULL,
        access_token  TEXT    NOT NULL,
        refresh_token TEXT,
        expires_at    TEXT,
        token_meta    TEXT,
        updated_at    TEXT    NOT NULL,
        UNIQUE (user_id, platform)
    )
''')


def init_db():
    """Create platform_tokens table if it does not exist."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(CREATE_TOKENS_TABLE)
        conn.commit()
        logger.info('auth_manager: platform_tokens table ready')
    except Exception as e:
        logger.error('auth_manager init_db failed: %s', e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Encrypt / decrypt
# ---------------------------------------------------------------------------
def _encrypt(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    return fernet.decrypt(value.encode()).decode()


# ---------------------------------------------------------------------------
# Save token
# ---------------------------------------------------------------------------
def save_token(platform: str, access_token: str, refresh_token: str = None,
               expires_at: datetime = None, meta: dict = None, user_id: str = 'default'):
    """
    Upsert an OAuth token for (user_id, platform).
    Tokens are Fernet-encrypted before storage.
    """
    enc_access  = _encrypt(access_token)
    enc_refresh = _encrypt(refresh_token) if refresh_token else None
    expires_str = expires_at.isoformat() if expires_at else None
    meta_str    = json.dumps(meta) if meta else None
    now         = datetime.utcnow().isoformat()
    p           = placeholder

    if USE_POSTGRES:
        sql = f'''
            INSERT INTO platform_tokens
                (user_id, platform, access_token, refresh_token, expires_at, token_meta, updated_at)
            VALUES ({p},{p},{p},{p},{p},{p},{p})
            ON CONFLICT (user_id, platform) DO UPDATE SET
                access_token  = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, platform_tokens.refresh_token),
                expires_at    = EXCLUDED.expires_at,
                token_meta    = COALESCE(EXCLUDED.token_meta, platform_tokens.token_meta),
                updated_at    = EXCLUDED.updated_at
        '''
    else:
        sql = f'''
            INSERT INTO platform_tokens
                (user_id, platform, access_token, refresh_token, expires_at, token_meta, updated_at)
            VALUES ({p},{p},{p},{p},{p},{p},{p})
            ON CONFLICT(user_id, platform) DO UPDATE SET
                access_token  = excluded.access_token,
                refresh_token = COALESCE(excluded.refresh_token, platform_tokens.refresh_token),
                expires_at    = excluded.expires_at,
                token_meta    = COALESCE(excluded.token_meta, platform_tokens.token_meta),
                updated_at    = excluded.updated_at
        '''

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (user_id, platform, enc_access, enc_refresh, expires_str, meta_str, now))
        conn.commit()
        logger.info('Token saved: platform=%s user=%s', platform, user_id)
    except Exception as e:
        logger.error('save_token failed: %s', e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Load token
# ---------------------------------------------------------------------------
def load_token(platform: str, user_id: str = 'default') -> dict | None:
    """
    Return decrypted token dict for (user_id, platform), or None if not found.
    Dict keys: access_token, refresh_token, expires_at, meta.
    """
    p   = placeholder
    sql = (
        f'SELECT access_token, refresh_token, expires_at, token_meta '
        f'FROM platform_tokens WHERE user_id={p} AND platform={p}'
    )
    conn = get_connection()
    try:
        if USE_POSTGRES:
            import psycopg2.extras
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql, (user_id, platform))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    if isinstance(row, dict):
        a, r, e, m = row['access_token'], row['refresh_token'], row['expires_at'], row['token_meta']
    else:
        a, r, e, m = row[0], row[1], row[2], row[3]

    return {
        'access_token':  _decrypt(a),
        'refresh_token': _decrypt(r) if r else None,
        'expires_at':    datetime.fromisoformat(e) if e else None,
        'meta':          json.loads(m) if m else {},
    }


# ---------------------------------------------------------------------------
# Expiry checks
# ---------------------------------------------------------------------------
def is_token_expired(platform: str, user_id: str = 'default', warn_days: int = 7) -> str:
    """Returns 'ok' | 'warning' | 'expired' | 'missing'."""
    token = load_token(platform, user_id)
    if not token:
        return 'missing'
    if not token['expires_at']:
        return 'ok'
    now     = datetime.utcnow()
    expires = token['expires_at']
    if now >= expires:
        return 'expired'
    if now >= expires - timedelta(days=warn_days):
        return 'warning'
    return 'ok'


def get_all_token_statuses(user_id: str = 'default') -> dict:
    platforms = ['facebook', 'instagram', 'google', 'tiktok', 'youtube']
    return {p: is_token_expired(p, user_id) for p in platforms}


# ---------------------------------------------------------------------------
# Google token refresh
# ---------------------------------------------------------------------------
def refresh_google_token(user_id: str = 'default') -> str | None:
    token = load_token('google', user_id)
    if not token or not token['refresh_token']:
        logger.error('Cannot refresh Google token -- no refresh_token stored')
        return None
    resp = requests.post('https://oauth2.googleapis.com/token', data={
        'grant_type':    'refresh_token',
        'refresh_token': token['refresh_token'],
        'client_id':     os.environ.get('GOOGLE_CLIENT_ID'),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
    }, timeout=10)
    if resp.status_code != 200:
        logger.error('Google token refresh failed: %s', resp.text)
        return None
    data       = resp.json()
    new_access = data['access_token']
    expires_at = datetime.utcnow() + timedelta(seconds=data.get('expires_in', 3600))
    save_token('google', new_access, refresh_token=token['refresh_token'],
               expires_at=expires_at, meta=token['meta'], user_id=user_id)
    logger.info('Google token refreshed for user=%s', user_id)
    return new_access


def get_valid_google_token(user_id: str = 'default') -> str | None:
    """Return a valid (auto-refreshed if needed) Google token, or None."""
    status = is_token_expired('google', user_id, warn_days=0)
    if status == 'expired':
        return refresh_google_token(user_id)
    if status == 'missing':
        return None
    token = load_token('google', user_id)
    return token['access_token'] if token else None


# ---------------------------------------------------------------------------
# TikTok token refresh
# ---------------------------------------------------------------------------
def refresh_tiktok_token(user_id: str = 'default') -> str | None:
    token = load_token('tiktok', user_id)
    if not token or not token['refresh_token']:
        logger.error('Cannot refresh TikTok token -- no refresh_token stored')
        return None
    resp = requests.post('https://open.tiktokapis.com/v2/oauth/token/', json={
        'client_key':    os.environ.get('TIKTOK_CLIENT_KEY'),
        'client_secret': os.environ.get('TIKTOK_CLIENT_SECRET'),
        'grant_type':    'refresh_token',
        'refresh_token': token['refresh_token'],
    }, timeout=10)
    if resp.status_code != 200:
        logger.error('TikTok token refresh failed: %s', resp.text)
        return None
    data        = resp.json().get('data', {})
    new_access  = data.get('access_token')
    new_refresh = data.get('refresh_token', token['refresh_token'])
    expires_at  = datetime.utcnow() + timedelta(seconds=data.get('expires_in', 86400))
    save_token('tiktok', new_access, refresh_token=new_refresh,
               expires_at=expires_at, meta=token['meta'], user_id=user_id)
    logger.info('TikTok token refreshed for user=%s', user_id)
    return new_access


# ---------------------------------------------------------------------------
# Delete token
# ---------------------------------------------------------------------------
def delete_token(platform: str, user_id: str = 'default'):
    p    = placeholder
    sql  = f'DELETE FROM platform_tokens WHERE user_id={p} AND platform={p}'
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (user_id, platform))
        conn.commit()
        logger.info('Token deleted: platform=%s user=%s', platform, user_id)
    except Exception as e:
        logger.error('delete_token failed: %s', e)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bootstrap on import
# ---------------------------------------------------------------------------
try:
    init_db()
except Exception as e:
    logger.error('auth_manager bootstrap failed: %s', e)
