"""
modules/auth_manager.py

╭────────────────────────────────────────────────────────────────────────╮
│  AUTHORITATIVE TOKEN STORE                                               │
│  All OAuth tokens live in pp.platform_tokens (Supabase Postgres).       │
│  The table was created by the post_pilot_schema migration.              │
│                                                                          │
│  Write:   save_token(platform, access_token, ..., user_id=uid)          │
│  Read:    load_token(platform, user_id)  -> dict | None                 │
│  Delete:  delete_token(platform, user_id)                               │
│  Refresh: get_valid_google_token(uid) / refresh_tiktok_token(uid)       │
╰────────────────────────────────────────────────────────────────────────╯

pp.platform_tokens columns:
  id, user_id, platform, token_data (Fernet JSON blob),
  page_id, page_name, expires_at, created_at, updated_at

All token fields (access_token, refresh_token, meta) are packed into a
single Fernet-encrypted JSON blob stored in `token_data`.
Tokens are Fernet-encrypted at rest using TOKEN_ENCRYPTION_KEY.
"""

import json
import logging
import os
from datetime import datetime, timedelta

import requests
from cryptography.fernet import Fernet

from modules.database import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------
ENCRYPTION_KEY = os.environ.get('TOKEN_ENCRYPTION_KEY', '').strip()
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning('TOKEN_ENCRYPTION_KEY not set -- generated ephemeral key (dev only)')

# Ensure it is bytes for Fernet
_key_bytes = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY

# Validate before constructing so the error message is clear
try:
    fernet = Fernet(_key_bytes)
except Exception as exc:
    logger.error('Invalid TOKEN_ENCRYPTION_KEY (%s) -- generating ephemeral key', exc)
    fernet = Fernet(Fernet.generate_key())


def _encrypt(payload: dict) -> str:
    """Encrypt a dict as a Fernet token string."""
    return fernet.encrypt(json.dumps(payload).encode()).decode()


def _decrypt(blob: str) -> dict:
    """Decrypt a Fernet blob back to a dict."""
    return json.loads(fernet.decrypt(blob.encode()).decode())


# ---------------------------------------------------------------------------
# Save token
# ---------------------------------------------------------------------------
def save_token(
    platform: str,
    access_token: str,
    refresh_token: str = None,
    expires_at: datetime = None,
    meta: dict = None,
    user_id: str = 'default',
):
    """
    Upsert an OAuth token for (user_id, platform).
    All fields are packed into a single encrypted JSON blob in token_data.
    page_id / page_name are extracted from meta for quick queries.
    """
    payload = {
        'access_token':  access_token,
        'refresh_token': refresh_token,
        'expires_at':    expires_at.isoformat() if expires_at else None,
        'meta':          meta or {},
    }
    token_data = _encrypt(payload)
    page_id    = (meta or {}).get('page_id')
    page_name  = (meta or {}).get('page_name')
    expires_str = expires_at.isoformat() if expires_at else None

    conn = get_db()
    try:
        conn.execute(
            '''
            INSERT INTO platform_tokens
                (user_id, platform, token_data, page_id, page_name, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, platform) DO UPDATE SET
                token_data = EXCLUDED.token_data,
                page_id    = COALESCE(EXCLUDED.page_id,   platform_tokens.page_id),
                page_name  = COALESCE(EXCLUDED.page_name, platform_tokens.page_name),
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            ''',
            (user_id, platform, token_data, page_id, page_name, expires_str),
        )
        conn.commit()
        logger.info('Token saved: platform=%s user=%s', platform, user_id)
    except Exception as exc:
        logger.error('save_token failed: %s', exc)
        conn.rollback()


# ---------------------------------------------------------------------------
# Load token
# ---------------------------------------------------------------------------
def load_token(platform: str, user_id: str = 'default') -> dict | None:
    """
    Return decrypted token dict for (user_id, platform), or None if not found.
    Keys: access_token, refresh_token, expires_at (datetime|None), meta (dict).
    """
    conn = get_db()
    cur  = conn.execute(
        'SELECT token_data, expires_at FROM platform_tokens WHERE user_id = %s AND platform = %s',
        (user_id, platform),
    )
    row = cur.fetchone()
    if not row:
        return None

    payload = _decrypt(row['token_data'])
    raw_exp = payload.get('expires_at')
    if not raw_exp and row.get('expires_at'):
        raw_exp = str(row['expires_at'])
    return {
        'access_token':  payload['access_token'],
        'refresh_token': payload.get('refresh_token'),
        'expires_at':    datetime.fromisoformat(raw_exp) if raw_exp else None,
        'meta':          payload.get('meta', {}),
    }


# ---------------------------------------------------------------------------
# Expiry helpers
# ---------------------------------------------------------------------------
def is_token_expired(platform: str, user_id: str = 'default', warn_days: int = 7) -> str:
    """Returns 'ok' | 'warning' | 'expired' | 'missing'."""
    token = load_token(platform, user_id)
    if not token:
        return 'missing'
    if not token['expires_at']:
        return 'ok'
    now     = datetime.utcnow()
    expires = token['expires_at'].replace(tzinfo=None)
    if now >= expires:
        return 'expired'
    if now >= expires - timedelta(days=warn_days):
        return 'warning'
    return 'ok'


def get_all_token_statuses(user_id: str = 'default') -> dict:
    platforms = ['facebook', 'instagram', 'google', 'tiktok', 'youtube', 'twitter']
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
    conn = get_db()
    try:
        conn.execute(
            'DELETE FROM platform_tokens WHERE user_id = %s AND platform = %s',
            (user_id, platform),
        )
        conn.commit()
        logger.info('Token deleted: platform=%s user=%s', platform, user_id)
    except Exception as exc:
        logger.error('delete_token failed: %s', exc)
