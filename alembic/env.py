"""
alembic/env.py
Wired to modules.db so Alembic uses the same SQLite/Postgres detection
logic as the rest of the app.

Offline mode  (alembic upgrade --sql): generates raw SQL without a live DB.
Online  mode  (alembic upgrade head):  connects and runs migrations.

Usage:
    alembic upgrade head        # apply all pending migrations
    alembic downgrade -1        # roll back one migration
    alembic revision --autogenerate -m "add foo column"
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from alembic import context

# Make sure project root is on sys.path so `from modules.db import ...` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Alembic Config object -- provides access to values in alembic.ini
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Resolve DB URL from environment (mirrors modules/db.py logic)
# ---------------------------------------------------------------------------
def _get_url() -> str:
    url = os.environ.get('DATABASE_URL', '')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('postgresql://'):
        return url
    # SQLite fallback
    db_path = os.environ.get('DATABASE_PATH', 'postpilot.db')
    return f'sqlite:///{db_path}'


# We do not use SQLAlchemy ORM models -- metadata is managed manually
target_metadata = None


# ---------------------------------------------------------------------------
# Offline mode
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    url = _get_url()
    context.configure(
        url             = url,
        target_metadata = target_metadata,
        literal_binds   = True,
        dialect_opts    = {'paramstyle': 'named'},
        compare_type    = True,
        render_as_batch = True,  # required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    url       = _get_url()
    is_sqlite = url.startswith('sqlite')

    connectable = create_engine(
        url,
        poolclass    = pool.NullPool,
        connect_args = {'check_same_thread': False} if is_sqlite else {},
    )

    with connectable.connect() as connection:
        context.configure(
            connection      = connection,
            target_metadata = target_metadata,
            compare_type    = True,
            render_as_batch = True,  # required for SQLite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
