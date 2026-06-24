"""
user_manager.py — User accounts for Post-Pilot (Postgres / pp schema).

All tables live in the 'pp' schema on Supabase.
The db connection sets search_path=pp automatically, so bare table
names like `users`, `post_history`, etc. resolve correctly.

Column mapping (pp.users):
  id, email, password_hash, full_name, business_name,
  plan, stripe_customer_id, stripe_sub_id,
  is_active, is_verified, verification_token,
  reset_token, reset_token_expiry,
  created_at, updated_at

Usage:
    from modules.user_manager import UserManager, User
    user = UserManager.create_user('hi@example.com', 'password123')
    user = UserManager.get_user_by_email('hi@example.com')
    UserManager.verify_password(user, 'password123')  # -> True
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import UserMixin

from modules.database import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Flask-Login User model
# ---------------------------------------------------------------------------
class User(UserMixin):
    """Lightweight user object that maps directly to pp.users columns."""

    def __init__(self, row: dict):
        self.id                 = str(row['id'])
        self.email              = row['email']
        self.password_hash      = row['password_hash']
        self.full_name          = row.get('full_name') or ''
        self.business_name      = row.get('business_name') or ''
        self.plan               = row.get('plan', 'free')
        self.stripe_customer_id = row.get('stripe_customer_id')
        self.stripe_sub_id      = row.get('stripe_sub_id')
        self.is_active          = bool(row.get('is_active', True))
        self.is_verified        = bool(row.get('is_verified', False))
        self.created_at         = row.get('created_at', '')
        self.updated_at         = row.get('updated_at', '')

    # Flask-Login requires string ID
    def get_id(self) -> str:
        return self.id

    # Convenience aliases so templates/blueprints don't break
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

    # -- Create -------------------------------------------------------------
    @staticmethod
    def create_user(
        email: str,
        password: str,
        full_name: str = '',
        business_name: str = '',
        plan: str = 'free',
    ) -> Optional[User]:
        """
        Register a new user. Returns User on success, None if email taken.
        """
        email = email.strip().lower()
        try:
            conn  = _get_conn()
            uid   = str(uuid.uuid4())
            phash = generate_password_hash(password)
            conn.execute(
                '''
                INSERT INTO users
                    (id, email, password_hash, full_name, business_name, plan)
                VALUES (%s, %s, %s, %s, %s, %s)
                ''',
                (uid, email, phash, full_name, business_name, plan),
            )
            conn.commit()
            logger.info('User created: %s [%s]', email, uid)
            return UserManager.get_user(uid)
        except Exception as exc:
            logger.warning('create_user failed for %s: %s', email, exc)
            return None

    # -- Read ---------------------------------------------------------------
    @staticmethod
    def get_user(user_id: str) -> Optional[User]:
        """Load a user by UUID. Returns None if not found."""
        conn = _get_conn()
        cur  = conn.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        row  = cur.fetchone()
        return User(row) if row else None

    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """Load a user by email (case-insensitive)."""
        conn = _get_conn()
        cur  = conn.execute(
            'SELECT * FROM users WHERE LOWER(email) = %s',
            (email.strip().lower(),),
        )
        row = cur.fetchone()
        return User(row) if row else None

    @staticmethod
    def verify_password(user: User, password: str) -> bool:
        """Returns True if password matches the stored hash."""
        return check_password_hash(user.password_hash, password)

    @staticmethod
    def touch_login(user_id: str):
        """Update updated_at on successful login."""
        conn = _get_conn()
        conn.execute(
            'UPDATE users SET updated_at = NOW() WHERE id = %s',
            (user_id,),
        )
        conn.commit()

    # -- Update -------------------------------------------------------------
    @staticmethod
    def update_profile(user_id: str, full_name: str = None, business_name: str = None):
        """Update display name / business name."""
        fields, values = [], []
        if full_name is not None:
            fields.append('full_name = %s');      values.append(full_name)
        if business_name is not None:
            fields.append('business_name = %s'); values.append(business_name)
        if not fields:
            return
        values.append(user_id)
        conn = _get_conn()
        conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = %s",
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
        """
        Update plan and Stripe metadata. Called by billing_manager on webhooks.
        """
        conn = _get_conn()
        conn.execute(
            '''
            UPDATE users SET
                plan                = %s,
                stripe_customer_id  = COALESCE(%s, stripe_customer_id),
                stripe_sub_id       = COALESCE(%s, stripe_sub_id)
            WHERE id = %s
            ''',
            (plan, stripe_customer_id, stripe_sub_id, user_id),
        )
        conn.commit()
        logger.info('Subscription updated: user=%s plan=%s', user_id, plan)

    # -- Password reset -----------------------------------------------------
    @staticmethod
    def set_reset_token(email: str) -> Optional[str]:
        """
        Generate and store a password-reset token. Returns the raw token,
        or None if the email is not found.
        """
        from datetime import timedelta
        user = UserManager.get_user_by_email(email)
        if not user:
            return None
        token  = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(hours=2)
        conn   = _get_conn()
        conn.execute(
            'UPDATE users SET reset_token = %s, reset_token_expiry = %s WHERE id = %s',
            (token, expiry, user.id),
        )
        conn.commit()
        return token

    @staticmethod
    def reset_password(token: str, new_password: str) -> bool:
        """
        Consume a reset token and update password.
        Returns True on success, False if token is invalid/expired.
        """
        conn = _get_conn()
        cur  = conn.execute(
            'SELECT id, reset_token_expiry FROM users WHERE reset_token = %s',
            (token,),
        )
        row = cur.fetchone()
        if not row:
            return False
        expiry = row['reset_token_expiry']
        if expiry and datetime.utcnow() > expiry.replace(tzinfo=None):
            return False
        phash = generate_password_hash(new_password)
        conn.execute(
            'UPDATE users SET password_hash = %s, reset_token = NULL, reset_token_expiry = NULL WHERE id = %s',
            (phash, row['id']),
        )
        conn.commit()
        return True

    # -- Post history -------------------------------------------------------
    @staticmethod
    def log_post(
        user_id:          str,
        content:          str,
        platform:         str,
        status:           str = 'published',
        scheduled_at      = None,
        media_urls:       list = None,
        platform_post_id: str = None,
    ) -> str:
        """
        Save a post to pp.post_queue. Returns the new row id.
        """
        import json
        conn   = _get_conn()
        row_id = str(uuid.uuid4())
        conn.execute(
            '''
            INSERT INTO post_queue
                (id, user_id, platform, content, media_urls, status,
                 scheduled_at, platform_post_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                row_id, user_id, platform, content,
                json.dumps(media_urls or []),
                status, scheduled_at, platform_post_id,
            ),
        )
        conn.commit()
        return row_id

    @staticmethod
    def get_post_history(
        user_id: str,
        limit:   int = 50,
        offset:  int = 0,
        status:  str = None,
    ) -> list:
        import json
        conn   = _get_conn()
        where  = 'WHERE user_id = %s'
        params = [user_id]
        if status:
            where  += ' AND status = %s'
            params.append(status)
        cur  = conn.execute(
            f'SELECT * FROM post_queue {where} ORDER BY created_at DESC LIMIT %s OFFSET %s',
            params + [limit, offset],
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get('media_urls'):
                try:
                    d['media_urls'] = json.loads(d['media_urls'])
                except Exception:
                    pass
            result.append(d)
        return result

    # -- API Keys -----------------------------------------------------------
    @staticmethod
    def create_api_key(user_id: str, label: str = 'Default key') -> str:
        """
        Generate a new API key. Returns the raw key (shown once, never stored).
        """
        raw_key  = 'pp_live_' + secrets.token_hex(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        conn     = _get_conn()
        conn.execute(
            'INSERT INTO api_keys (user_id, key_hash, label) VALUES (%s, %s, %s)',
            (user_id, key_hash, label),
        )
        conn.commit()
        logger.info('API key created for user=%s', user_id)
        return raw_key

    @staticmethod
    def lookup_api_key(raw_key: str) -> Optional[User]:
        """Verify a raw API key and return the owning User."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        conn     = _get_conn()
        cur      = conn.execute(
            'SELECT user_id FROM api_keys WHERE key_hash = %s AND is_active = TRUE',
            (key_hash,),
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                'UPDATE api_keys SET last_used = NOW() WHERE key_hash = %s',
                (key_hash,),
            )
            conn.commit()
        return UserManager.get_user(row['user_id']) if row else None
