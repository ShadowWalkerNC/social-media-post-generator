#!/usr/bin/env python3
"""
Post-Pilot -- Smart Social Media Hub
app.py: application factory, extensions, DB init, error handlers, entrypoint.

All routes live in blueprints/:
  auth.py     -- login, register, logout, OAuth (FB / Google / TikTok)
  billing.py  -- Stripe checkout, portal, cancel, webhook
  api.py      -- /api/* endpoints
  website.py  -- website hub + public site renderer
  pages.py    -- dashboard, setup, calendar, onboarding, legal

Shared helpers (uid, token loading, business name) live in blueprints/utils.py.

Token storage note:
  OAuth tokens are stored EXCLUSIVELY in the `platform_tokens` table owned
  by modules/auth_manager.py (Fernet-encrypted).  There is NO second copy
  anywhere in the `users` table.  See auth_manager.save_token() /
  auth_manager.load_token() for the API.
"""

import os
import sqlite3
import multiprocessing
from flask import Flask, g, jsonify, redirect, url_for, flash, request
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from modules.user_manager    import UserManager
from modules.auth_manager    import init_db as auth_init_db
from modules.api_manager     import CREATE_API_KEYS_TABLE
from modules.website_manager import WebsiteManager
from modules.scheduler_worker import init_scheduler

load_dotenv()

# ---------------------------------------------------------------------------
# Secret key -- hard-fail if missing in production
# ---------------------------------------------------------------------------
_secret = os.getenv('FLASK_SECRET_KEY')
if not _secret:
    import sys
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('RAILWAY_ENVIRONMENT'):
        sys.exit('FATAL: FLASK_SECRET_KEY is not set. Refusing to start in production.')
    _secret = 'dev-only-insecure-key'

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY']          = _secret
app.config['WTF_CSRF_TIME_LIMIT'] = 7200

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------
csrf = CSRFProtect(app)

# NOTE: Set REDIS_URL in production so rate limits are shared across workers.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.getenv('REDIS_URL', 'memory://'),
)

# ---------------------------------------------------------------------------
# Flask-Login
# ---------------------------------------------------------------------------
login_manager = LoginManager(app)
login_manager.login_view    = 'auth.login'
login_manager.login_message = 'Please sign in to access Post-Pilot.'

@login_manager.user_loader
def load_user(user_id: str):
    return UserManager.get_user(user_id)

# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------
from blueprints import register_blueprints  # noqa: E402 (must come after app creation)
register_blueprints(app, csrf)

# ---------------------------------------------------------------------------
# Database helpers (imported by blueprints via `from app import get_db`)
# ---------------------------------------------------------------------------
DATABASE = os.getenv('DATABASE_PATH', 'postpilot.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute(CREATE_API_KEYS_TABLE)
        db.execute(WebsiteManager.create_table_sql())
        db.execute('''
            CREATE TABLE IF NOT EXISTS post_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT    NOT NULL,
                caption      TEXT,
                content_type TEXT    DEFAULT 'text',
                image_url    TEXT,
                video_url    TEXT,
                platforms    TEXT,
                results      TEXT,
                status       TEXT    DEFAULT 'published',
                post_url     TEXT,
                scheduled_at INTEGER,
                created_at   INTEGER DEFAULT (strftime('%s','now'))
            );
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id                 TEXT PRIMARY KEY,
                email              TEXT UNIQUE NOT NULL,
                password_hash      TEXT NOT NULL,
                display_name       TEXT,
                subscription_tier  TEXT DEFAULT 'free',
                stripe_customer_id TEXT,
                created_at         INTEGER,
                last_login_at      INTEGER
            );
        ''')
        # NOTE: OAuth tokens live in `platform_tokens` (auth_manager.py).
        # Business profile lives in `business_profiles` (user_manager.py).
        # Do NOT add platform_tokens TEXT or business_profile TEXT here.
        db.commit()
        db.close()
        print('DB initialised')
    auth_init_db()

try:
    init_db()
except Exception as _init_err:
    print(f'[WARN] init_db on startup failed: {_init_err}')

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    from flask import render_template
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    from flask import render_template
    return render_template('500.html'), 500

@app.errorhandler(429)
def rate_limited(e):
    if request.is_json:
        return jsonify({'success': False, 'error': 'Too many requests. Please wait and try again.'}), 429
    flash('Too many attempts. Please wait a minute and try again.')
    return redirect(url_for('auth.login')), 429

# ---------------------------------------------------------------------------
# Scheduler -- only in main process (not gunicorn workers or pytest imports)
# ---------------------------------------------------------------------------
if __name__ == '__main__' or (
    os.getenv('RAILWAY_ENVIRONMENT')
    and multiprocessing.current_process().name == 'MainProcess'
):
    init_scheduler()

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    init_db()
    print('Post-Pilot running at http://localhost:5000')
    app.run(debug=True, port=5000)
