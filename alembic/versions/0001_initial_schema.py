"""
Initial schema -- all six Post-Pilot tables.

Revision ID: 0001
Revises:     (none -- this is the base migration)
Create Date: 2026-06-22

Resolves the conflicting DDLs that existed across app.py, user_manager.py,
and api_manager.py. Canonical decisions:

  post_history.scheduled_at  -> INTEGER (Unix timestamp)
      Rationale: scheduler_worker polls WHERE scheduled_at <= int(time.time())

  api_keys.key_value         -> TEXT (plain token, not hash)
      Rationale: live /v1/keys/* routes in api_manager.py use key_value;
      user_manager's key_hash variant is unreachable dead code.

  users                      -> authoritative column set from user_manager.py
      (stripe, trial, is_admin, sub_status, etc.) plus INTEGER timestamps
      for created_at / last_login_at to match app.py.

Applying to an EXISTING database created by the old ad-hoc init_db() calls:

    alembic stamp head

This marks the DB as already at revision 0001 without re-running the DDL.
Only run `alembic upgrade head` on a fresh database.
"""

from alembic import op
import sqlalchemy as sa

revision      = '0001'
down_revision = None
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        'users',
        sa.Column('id',                     sa.Text(),    primary_key=True,  nullable=False),
        sa.Column('email',                  sa.Text(),    nullable=False,    unique=True),
        sa.Column('password_hash',          sa.Text(),    nullable=False),
        sa.Column('display_name',           sa.Text(),    nullable=True),
        sa.Column('subscription_tier',      sa.Text(),    nullable=False,    server_default='free'),
        sa.Column('stripe_customer_id',     sa.Text(),    nullable=True),
        sa.Column('stripe_sub_id',          sa.Text(),    nullable=True),
        sa.Column('sub_status',             sa.Text(),    nullable=True,     server_default='active'),
        sa.Column('sub_current_period_end', sa.Text(),    nullable=True),
        sa.Column('trial_ends_at',          sa.Text(),    nullable=True),
        sa.Column('is_admin',               sa.Integer(), nullable=False,    server_default='0'),
        sa.Column('created_at',             sa.Integer(), nullable=True),
        sa.Column('last_login_at',          sa.Integer(), nullable=True),
    )

    # ------------------------------------------------------------------
    # business_profiles
    # ------------------------------------------------------------------
    op.create_table(
        'business_profiles',
        sa.Column('id',            sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',       sa.Text(),    sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('name',          sa.Text(),    nullable=True,  server_default=''),
        sa.Column('business_type', sa.Text(),    nullable=True,  server_default='food_truck'),
        sa.Column('location',      sa.Text(),    nullable=True,  server_default=''),
        sa.Column('address',       sa.Text(),    nullable=True,  server_default=''),
        sa.Column('lat',           sa.Float(),   nullable=True),
        sa.Column('lng',           sa.Float(),   nullable=True),
        sa.Column('hours',         sa.Text(),    nullable=True,  server_default=''),
        sa.Column('phone',         sa.Text(),    nullable=True,  server_default=''),
        sa.Column('website_url',   sa.Text(),    nullable=True,  server_default=''),
        sa.Column('logo_url',      sa.Text(),    nullable=True,  server_default=''),
        sa.Column('prompt_time',   sa.Text(),    nullable=True,  server_default='07:00'),
        sa.Column('timezone',      sa.Text(),    nullable=True,  server_default='US/Eastern'),
        sa.Column('ai_tone',       sa.Text(),    nullable=True,  server_default='friendly'),
        sa.Column('ai_keywords',   sa.Text(),    nullable=True,  server_default=''),
        sa.Column('subdomain',     sa.Text(),    nullable=True,  unique=True),
        sa.Column('custom_domain', sa.Text(),    nullable=True),
        sa.Column('updated_at',    sa.Text(),    nullable=False),
    )
    op.create_index('idx_biz_user', 'business_profiles', ['user_id'])

    # ------------------------------------------------------------------
    # platform_tokens  (auth_manager -- Fernet-encrypted)
    # ------------------------------------------------------------------
    op.create_table(
        'platform_tokens',
        sa.Column('id',            sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',       sa.Text(),    nullable=False,   server_default='default'),
        sa.Column('platform',      sa.Text(),    nullable=False),
        sa.Column('access_token',  sa.Text(),    nullable=False),
        sa.Column('refresh_token', sa.Text(),    nullable=True),
        sa.Column('expires_at',    sa.Text(),    nullable=True),
        sa.Column('token_meta',    sa.Text(),    nullable=True),
        sa.Column('updated_at',    sa.Text(),    nullable=False),
        sa.UniqueConstraint('user_id', 'platform', name='uq_platform_tokens_user_platform'),
    )

    # ------------------------------------------------------------------
    # api_keys  (api_manager -- live /v1/keys/* routes)
    # ------------------------------------------------------------------
    op.create_table(
        'api_keys',
        sa.Column('id',           sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',      sa.Text(),    nullable=False),
        sa.Column('label',        sa.Text(),    nullable=False,   server_default='My Key'),
        sa.Column('key_value',    sa.Text(),    nullable=False,   unique=True),
        sa.Column('active',       sa.Integer(), nullable=False,   server_default='1'),
        sa.Column('created_at',   sa.Integer(), nullable=True),
        sa.Column('expires_at',   sa.Integer(), nullable=True),
        sa.Column('last_used_at', sa.Integer(), nullable=True),
        sa.Column('call_count',   sa.Integer(), nullable=False,   server_default='0'),
    )
    op.create_index('idx_api_user', 'api_keys', ['user_id'])

    # ------------------------------------------------------------------
    # post_history
    # scheduled_at is INTEGER (Unix timestamp) -- scheduler_worker uses
    # WHERE scheduled_at <= int(time.time())
    # ------------------------------------------------------------------
    op.create_table(
        'post_history',
        sa.Column('id',           sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',      sa.Text(),    nullable=False),
        sa.Column('caption',      sa.Text(),    nullable=True),
        sa.Column('content_type', sa.Text(),    nullable=True,    server_default='text'),
        sa.Column('image_url',    sa.Text(),    nullable=True),
        sa.Column('video_url',    sa.Text(),    nullable=True),
        sa.Column('platforms',    sa.Text(),    nullable=True),
        sa.Column('results',      sa.Text(),    nullable=True),
        sa.Column('status',       sa.Text(),    nullable=True,    server_default='published'),
        sa.Column('post_url',     sa.Text(),    nullable=True),
        sa.Column('scheduled_at', sa.Integer(), nullable=True),
        sa.Column('created_at',   sa.Integer(), nullable=True,
                  server_default=sa.text("(strftime('%s','now'))")),
    )
    op.create_index('idx_history_user', 'post_history', ['user_id'])
    op.create_index('idx_history_date', 'post_history', ['created_at'])

    # ------------------------------------------------------------------
    # websites  (website_manager)
    # ------------------------------------------------------------------
    op.create_table(
        'websites',
        sa.Column('id',         sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',    sa.Text(),    nullable=False,   unique=True),
        sa.Column('config',     sa.Text(),    nullable=True),
        sa.Column('published',  sa.Integer(), nullable=False,   server_default='0'),
        sa.Column('subdomain',  sa.Text(),    nullable=True,    unique=True),
        sa.Column('updated_at', sa.Text(),    nullable=True),
    )
    op.create_index('idx_websites_user', 'websites', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_websites_user',  table_name='websites')
    op.drop_table('websites')
    op.drop_index('idx_history_date',   table_name='post_history')
    op.drop_index('idx_history_user',   table_name='post_history')
    op.drop_table('post_history')
    op.drop_index('idx_api_user',       table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_table('platform_tokens')
    op.drop_index('idx_biz_user',       table_name='business_profiles')
    op.drop_table('business_profiles')
    op.drop_table('users')
