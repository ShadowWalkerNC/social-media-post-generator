"""
auth_manager.py — Token Persistence, Refresh & Expiry (Phase 4 Session 1)

Handles encrypted token storage in SQLite (dev) / PostgreSQL (prod).
Auto-refreshes Google tokens. Detects expiry. Signals dashboard alerts.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption key — load from env or generate (dev only)
# ---------------------------------------------------------------------------
ENCRYPTION_KEY = os.environ.get('TOKEN_ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning('TOKEN_ENCRYPTION_KEY not set — generated ephemeral key (dev only)')

fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

DB_PATH = os.environ.get('DATABASE_URL', 'postpilot.db')


# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------
def init_db():
    """Create tokens table if it doesn't exist."""
    conn = _get_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS platform_tokens (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT    NOT NULL DEFAULT 'default',
            platform      TEXT    NOT NULL,
            access_token  TEXT    NOT NULL,
            refresh_token TEXT,
            expires_at    TEXT,
            token_meta    TEXT,
            updated_at    TEXT    NOT NULL
        )
    ''')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_user_platform ON platform_tokens(user_id, platform)')
    conn.commit()
    conn.close()


def _get_conn():
    return sqlite3.connect(DB_PATH)


# ---------------------------------------------------------------------------
# Encrypt / decrypt helpers
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
    Persist an encrypted token for a platform.

    Args:
        platform:      'facebook' | 'instagram' | 'google' | 'tiktok' | 'youtube'
        access_token:  The bearer token
        refresh_token: Long-lived refresh token (Google, TikTok)
        expires_at:    datetime when access_token expires
        meta:          Any extra platform-specific data (page_id, etc.)
        user_id:       User identifier (default for single-user mode)
    """
    conn = _get_conn()
    enc_access = _encrypt(access_token)
    enc_refresh = _encrypt(refresh_token) if refresh_token else None
    expires_str = expires_at.isoformat() if expires_at else None
    meta_str = json.dumps(meta) if meta else None
    now = datetime.utcnow().isoformat()

    conn.execute('''
        INSERT INTO platform_tokens
            (user_id, platform, access_token, refresh_token, expires_at, token_meta, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, platform) DO UPDATE SET
            access_token  = excluded.access_token,
            refresh_token = COALESCE(excluded.refresh_token, platform_tokens.refresh_token),
            expires_at    = excluded.expires_at,
            token_meta    = COALESCE(excluded.token_meta, platform_tokens.token_meta),
            updated_at    = excluded.updated_at
    ''', (user_id, platform, enc_access, enc_refresh, expires_str, meta_str, now))
    conn.commit()
    conn.close()
    logger.info('Token saved for platform=%s user=%s', platform, user_id)


# ---------------------------------------------------------------------------
# Load token
# ---------------------------------------------------------------------------
def load_token(platform: str, user_id: str = 'default') -> dict | None:
    """
    Retrieve and decrypt a stored token.

    Returns dict with keys: access_token, refresh_token, expires_at, meta
    Returns None if not found.
    """
    conn = _get_conn()
    row = conn.execute(
        'SELECT access_token, refresh_token, expires_at, token_meta FROM platform_tokens '
        'WHERE user_id=? AND platform=?',
        (user_id, platform)
    ).fetchone()
    conn.close()

    if not row:
        return None

    access_token  = _decrypt(row[0])
    refresh_token = _decrypt(row[1]) if row[1] else None
    expires_at    = datetime.fromisoformat(row[2]) if row[2] else None
    meta          = json.loads(row[3]) if row[3] else {}

    return {
        'access_token':  access_token,
        'refresh_token': refresh_token,
        'expires_at':    expires_at,
        'meta':          meta,
    }


# ---------------------------------------------------------------------------
# Expiry checks
# ---------------------------------------------------------------------------
def is_token_expired(platform: str, user_id: str = 'default', warn_days: int = 7) -> str:
    """
    Check token expiry status.

    Returns:
        'ok'      — valid, not expiring soon
        'warning' — expires within warn_days
        'expired' — already expired
        'missing' — no token stored
    """
    token = load_token(platform, user_id)
    if not token:
        return 'missing'
    if not token['expires_at']:
        return 'ok'  # No expiry set (e.g. long-lived FB token without explicit expiry tracking)

    now = datetime.utcnow()
    expires = token['expires_at']

    if now >= expires:
        return 'expired'
    if now >= expires - timedelta(days=warn_days):
        return 'warning'
    return 'ok'


def get_all_token_statuses(user_id: str = 'default') -> dict:
    """
    Returns expiry status for all platforms.
    Used by dashboard to show red/yellow/green indicators.
    """
    platforms = ['facebook', 'instagram', 'google', 'tiktok', 'youtube']
    return {p: is_token_expired(p, user_id) for p in platforms}


# ---------------------------------------------------------------------------
# Google OAuth auto-refresh
# ---------------------------------------------------------------------------
def refresh_google_token(user_id: str = 'default') -> str | None:
    """
    Use stored refresh_token to get a new Google access token.
    Silently updates DB. Returns new access_token or None on failure.
    """
    token = load_token('google', user_id)
    if not token or not token['refresh_token']:
        logger.error('Cannot refresh Google token — no refresh_token stored')
        return None

    client_id     = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    resp = requests.post('https://oauth2.googleapis.com/token', data={
        'grant_type':    'refresh_token',
        'refresh_token': token['refresh_token'],
        'client_id':     client_id,
        'client_secret': client_secret,
    })

    if resp.status_code != 200:
        logger.error('Google token refresh failed: %s', resp.text)
        return None

    data = resp.json()
    new_access  = data['access_token']
    expires_at  = datetime.utcnow() + timedelta(seconds=data.get('expires_in', 3600))

    save_token('google', new_access,
               refresh_token=token['refresh_token'],
               expires_at=expires_at,
               meta=token['meta'],
               user_id=user_id)

    logger.info('Google token refreshed for user=%s', user_id)
    return new_access


def get_valid_google_token(user_id: str = 'default') -> str | None:
    """
    Returns a valid Google access token, auto-refreshing if needed.
    Call this before every Google API request.
    """
    status = is_token_expired('google', user_id, warn_days=0)
    if status == 'expired':
        return refresh_google_token(user_id)
    if status == 'missing':
        return None
    token = load_token('google', user_id)
    return token['access_token'] if token else None


# ---------------------------------------------------------------------------
# TikTok daily refresh
# ---------------------------------------------------------------------------
def refresh_tiktok_token(user_id: str = 'default') -> str | None:
    """
    Refresh TikTok access token using stored refresh_token.
    TikTok tokens expire every 24 hours.
    """
    token = load_token('tiktok', user_id)
    if not token or not token['refresh_token']:
        logger.error('Cannot refresh TikTok token — no refresh_token stored')
        return None

    client_key    = os.environ.get('TIKTOK_CLIENT_KEY')
    client_secret = os.environ.get('TIKTOK_CLIENT_SECRET')

    resp = requests.post('https://open.tiktokapis.com/v2/oauth/token/', json={
        'client_key':    client_key,
        'client_secret': client_secret,
        'grant_type':    'refresh_token',
        'refresh_token': token['refresh_token'],
    })

    if resp.status_code != 200:
        logger.error('TikTok token refresh failed: %s', resp.text)
        return None

    data = resp.json().get('data', {})
    new_access    = data.get('access_token')
    new_refresh   = data.get('refresh_token', token['refresh_token'])
    expires_in    = data.get('expires_in', 86400)
    expires_at    = datetime.utcnow() + timedelta(seconds=expires_in)

    save_token('tiktok', new_access,
               refresh_token=new_refresh,
               expires_at=expires_at,
               meta=token['meta'],
               user_id=user_id)

    logger.info('TikTok token refreshed for user=%s', user_id)
    return new_access


# ---------------------------------------------------------------------------
# Delete token (on reauth or account disconnect)
# ---------------------------------------------------------------------------
def delete_token(platform: str, user_id: str = 'default'):
    conn = _get_conn()
    conn.execute('DELETE FROM platform_tokens WHERE user_id=? AND platform=?', (user_id, platform))
    conn.commit()
    conn.close()
    logger.info('Token deleted for platform=%s user=%s', platform, user_id)


# ---------------------------------------------------------------------------
# Bootstrap on import
# ---------------------------------------------------------------------------
try:
    init_db()
except Exception as e:
    logger.error('auth_manager init_db failed: %s', e)
