# modules/database.py
# Thin proxy so modules (website_manager, api_manager, etc.) can call
# `from modules.database import get_db` without importing app.py directly.
# The real connection lives in Flask's `g` object, created per-request by app.py.

import sqlite3
import os
from flask import g


def get_db():
    """
    Return the SQLite connection for the current request context.
    If called outside a request (e.g. CLI / init), opens a direct connection.
    """
    # Inside a Flask request — use the cached connection on g
    try:
        if 'db' not in g:
            db_path = os.environ.get('DATABASE_PATH', 'postpilot.db')
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA journal_mode=WAL')
        return g.db
    except RuntimeError:
        # Outside request context (init_db, tests, CLI)
        db_path = os.environ.get('DATABASE_PATH', 'postpilot.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        return conn
