"""
db.py — Unified database abstraction for Post-Pilot.

Supports SQLite (local dev) and PostgreSQL (production).
Detects DATABASE_URL: if it starts with 'postgres', uses psycopg2.
Otherwise falls back to sqlite3.

Usage:
    from modules.db import get_connection, placeholder, adapt_schema

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f'SELECT * FROM users WHERE id = {placeholder}', (uid,))
    rows = cur.fetchall()
    conn.commit()
    conn.close()

Notes:
    - Always call conn.close() or use a context manager.
    - Use `placeholder` (? for SQLite, %s for Postgres) in all queries.
    - Use row_to_dict() for portable row access across both backends.

To migrate from SQLite to Postgres on Railway:
    1. Add the Railway PostgreSQL plugin to your project.
    2. Railway auto-sets DATABASE_URL in your environment.
    3. Redeploy — db.py detects it and switches automatically.
    4. Run: python -c "from modules.db import init_core_tables; init_core_tables()"
       to create all tables in the new database.
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Railway/Heroku serve postgres:// URLs; psycopg2 needs postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USE_POSTGRES = DATABASE_URL.startswith('postgresql://')

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
        logger.info('db.py: PostgreSQL mode (%s...)', DATABASE_URL[:40])
    except ImportError as exc:
        raise RuntimeError(
            'DATABASE_URL points to Postgres but psycopg2 is not installed. '
            'Run: pip install psycopg2-binary'
        ) from exc
else:
    SQLITE_PATH = os.environ.get('DATABASE_PATH', 'postpilot.db')
    logger.info('db.py: SQLite mode (%s)', SQLITE_PATH)

# Query placeholder differs between backends
placeholder = '%s' if USE_POSTGRES else '?'


def get_connection():
    """Return a new DB connection. Caller is responsible for closing it."""
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row) -> dict:
    """Convert a sqlite3.Row or psycopg2 RealDictRow to a plain dict."""
    if row is None:
        return {}
    if isinstance(row, sqlite3.Row):
        return dict(row)
    if isinstance(row, dict):
        return row
    # psycopg2 tuple row — caller should use RealDictCursor instead
    return dict(enumerate(row))


def adapt_schema(sql: str) -> str:
    """
    Translate SQLite-flavoured DDL to PostgreSQL-compatible DDL.
    Called at table creation time in each module's init_db().
    """
    if not USE_POSTGRES:
        return sql
    sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    sql = sql.replace("DEFAULT (strftime('%s','now'))",
                      'DEFAULT (EXTRACT(EPOCH FROM NOW())::BIGINT)')
    # Postgres uses EXCLUDED (uppercase) and requires ON CONFLICT (...) with space
    sql = sql.replace('ON CONFLICT(user_id, platform) DO UPDATE SET',
                      'ON CONFLICT (user_id, platform) DO UPDATE SET')
    return sql


def execute_one(sql: str, params: tuple = (), commit: bool = False):
    """Run a single statement, optionally commit. Returns cursor.fetchone()."""
    conn = get_connection()
    try:
        if USE_POSTGRES:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql, params)
        if commit:
            conn.commit()
        try:
            return cur.fetchone()
        except Exception:
            return None
    finally:
        conn.close()


def execute_all(sql: str, params: tuple = ()) -> list:
    """Run a SELECT and return all rows as a list."""
    conn = get_connection()
    try:
        if USE_POSTGRES:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()
