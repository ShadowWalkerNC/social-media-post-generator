"""
user_manager.py — User accounts for Post-Pilot (pp schema on Supabase).

Auth is now handled entirely by Supabase Auth (magic links).
This module only syncs/reads the pp.users mirror table.

All queries use `?` placeholders; db.py's DBConnectionWrapper auto-converts
them to %s for PostgreSQL. ::uuid casts are applied wherever a uuid column
is compared to a text parameter.

Live pp schema columns:
  users:        id, email, password_hash, full_name, business_name, plan,
                stripe_customer_id, stripe_sub_id, is_active, is_verified,
                reset_token, reset_token_expiry, created_at, updated_at
  post_queue:   id, user_id, platform, content, media_urls, status,
                scheduled_at, published_at, platform_post_id, created_at
  api_keys:     id, user_id, key_hash, label, last_used, is_active, created_at
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from flask_login import UserMixin

from modules.database import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Flask-Login User model
# ---------------------------------------------------------------------------
class User(UserMixin):
    """Lightweight user object that maps to pp.users columns."""

    def __init__(self, row: dict):
        self.id                 = str(row['id'])
        self.email              = row['email']
        self.password_hash      = row.get('password_hash') or ''
        self.full_name          = row.get('full_name') or ''
        self.business_name      = row.get('business_name') or ''
        self.plan               = row.get('plan', 'free')
        self.stripe_customer_id = row.get('stripe_customer_id')
        self.stripe_sub_id      = row.get('stripe_sub_id')
        self.is_active          = bool(row.get('is_active', True))
        self.is_verified        = bool(row.get('is_verified', True))  # magic link = verified
        self.created_at         = row.get('created_at', '')
        self.updated_at         = row.get('updated_at', '')

    def get_id(self) -> str:
        return self.id

    @property
    def display_name(self) -> str:
        return self.full_name or self.business_name or self.email.split('@')[0]

    @property
    def subscription_tier(self) -> str:
        return self.plan

    @property
    def is_free(self) -> bool:
        return self.plan == 'free'

    @property
    def is_paid(self) -> bool:
        return self.plan in ('starter', 'growth', 'pro', 'agency')

    def can_use_platform(self, platform: str) -> bool:
        if self.is_paid:
            return True
        return platform in {'fb', 'web'}

    def ai_captions_limit(self) -> int:
        limits = {'free': 5, 'starter': 30, 'growth': 150, 'pro': 999999, 'agency': 999999}
        return limits.get(self.plan, 5)

    def __repr__(self):
        return f'<User {self.email} [{self.plan}]>'


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _get_conn():
    return get_db()


# ---------------------------------------------------------------------------
# UserManager
# ---------------------------------------------------------------------------
class UserManager:

    # -- Upsert (called after successful magic link confirm) -----------------
    @staticmethod
    def upsert_user(
        user_id: str,
        email: str,
        full_name: str = '',
        business_name: str = '',
        plan: str = 'free',
    ) -> Optional[User]:
        """
        Insert a new user row or return existing. Called after Supabase OTP verify.
        The id comes directly from supabase auth.users so it is already a valid UUID.
        """
        try:
            conn = _get_conn()
            conn.execute(
                '''
                INSERT INTO users (id, email, full_name, business_name, plan, is_verified)
                VALUES (?::uuid, ?, ?, ?, ?, TRUE)
                ON CONFLICT (id) DO UPDATE SET
                    email         = EXCLUDED.email,
                    updated_at    = NOW()
                ''',
                (str(user_id), email.strip().lower(), full_name, business_name, plan),
            )
            conn.commit()
            logger.info('User upserted: %s [%s]', email, user_id)
            return UserManager.get_user(user_id)
        except Exception as exc:
            logger.error('upsert_user failed for %s: %s', email, exc)
            return None

    # -- Read ---------------------------------------------------------------
    @staticmethod
    def get_user(user_id: str) -> Optional[User]:
        """Load a user by UUID. Called by Flask-Login on every request."""
        try:
            conn = _get_conn()
            cur  = conn.execute(
                'SELECT * FROM users WHERE id = ?::uuid',
                (str(user_id),),
            )
            row = cur.fetchone()
            return User(dict(row)) if row else None
        except Exception as exc:
            logger.error('get_user(%s) failed: %s', user_id, exc)
            return None

    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """Load a user by email (case-insensitive)."""
        try:
            conn = _get_conn()
            cur  = conn.execute(
                'SELECT * FROM users WHERE LOWER(email) = ?',
                (email.strip().lower(),),
            )
            row = cur.fetchone()
            return User(dict(row)) if row else None
        except Exception as exc:
            logger.error('get_user_by_email(%s) failed: %s', email, exc)
            return None

    @staticmethod
    def touch_login(user_id: str):
        """Bump updated_at on successful login. Non-fatal."""
        try:
            conn = _get_conn()
            conn.execute(
                'UPDATE users SET updated_at = NOW() WHERE id = ?::uuid',
                (str(user_id),),
            )
            conn.commit()
        except Exception as exc:
            logger.warning('touch_login(%s) failed (non-fatal): %s', user_id, exc)

    # -- Update -------------------------------------------------------------
    @staticmethod
    def update_profile(user_id: str, full_name: str = None, business_name: str = None):
        fields, values = [], []
        if full_name is not None:
            fields.append('full_name = ?')
            values.append(full_name)
        if business_name is not None:
            fields.append('business_name = ?')
            values.append(business_name)
        if not fields:
            return
        values.append(str(user_id))
        conn = _get_conn()
        conn.execute(
            f"UPDATE users SET {', '.join(fields)}, updated_at = NOW() WHERE id = ?::uuid",
            values,
        )
        conn.commit()

    @staticmethod
    def update_subscription(
        user_id: str,
        plan: str,
        stripe_customer_id: str = None,
        stripe_sub_id: str = None,
    ):
        conn = _get_conn()
        conn.execute(
            '''
            UPDATE users SET
                plan               = ?,
                stripe_customer_id = COALESCE(?, stripe_customer_id),
                stripe_sub_id      = COALESCE(?, stripe_sub_id),
                updated_at         = NOW()
            WHERE id = ?::uuid
            ''',
            (plan, stripe_customer_id, stripe_sub_id, str(user_id)),
        )
        conn.commit()
        logger.info('Subscription updated: user=%s plan=%s', user_id, plan)

    # -- Post history -------------------------------------------------------
    @staticmethod
    def log_post(
        user_id: str, content: str, platform: str,
        status: str = 'published', scheduled_at=None,
        media_urls: list = None, platform_post_id: str = None,
    ) -> str:
        import json
        conn   = _get_conn()
        row_id = str(uuid.uuid4())
        conn.execute(
            '''
            INSERT INTO post_queue
                (id, user_id, platform, content, media_urls, status,
                 scheduled_at, platform_post_id)
            VALUES (?::uuid, ?::uuid, ?, ?, ?, ?, ?, ?)
            ''',
            (row_id, str(user_id), platform, content,
             json.dumps(media_urls or []), status, scheduled_at, platform_post_id),
        )
        conn.commit()
        return row_id

    @staticmethod
    def get_post_history(
        user_id: str, limit: int = 50, offset: int = 0, status: str = None,
    ) -> list:
        import json
        conn   = _get_conn()
        where  = 'WHERE user_id = ?::uuid'
        params = [str(user_id)]
        if status:
            where += ' AND status = ?'
            params.append(status)
        cur  = conn.execute(
            f'SELECT * FROM post_queue {where} ORDER BY created_at DESC LIMIT ? OFFSET ?',
            params + [limit, offset],
        )
        result = []
        for row in cur.fetchall():
            d = dict(row)
            if d.get('media_urls') and isinstance(d['media_urls'], str):
                try:
                    d['media_urls'] = json.loads(d['media_urls'])
                except Exception:
                    pass
            result.append(d)
        return result

    # -- API Keys -----------------------------------------------------------
    @staticmethod
    def create_api_key(user_id: str, label: str = 'Default key') -> str:
        raw_key  = 'pp_live_' + secrets.token_hex(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        conn     = _get_conn()
        conn.execute(
            'INSERT INTO api_keys (id, user_id, key_hash, label) VALUES (?::uuid, ?::uuid, ?, ?)',
            (str(uuid.uuid4()), str(user_id), key_hash, label),
        )
        conn.commit()
        logger.info('API key created for user=%s', user_id)
        return raw_key

    @staticmethod
    def lookup_api_key(raw_key: str) -> Optional[User]:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        conn     = _get_conn()
        cur      = conn.execute(
            'SELECT user_id FROM api_keys WHERE key_hash = ? AND is_active = TRUE',
            (key_hash,),
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                'UPDATE api_keys SET last_used = NOW() WHERE key_hash = ?',
                (key_hash,),
            )
            conn.commit()
        return UserManager.get_user(str(dict(row)['user_id'])) if row else None
