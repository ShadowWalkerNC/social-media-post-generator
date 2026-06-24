#!/usr/bin/env python3
"""
Post-Pilot -- Smart Social Media Hub
app.py: application factory, extensions, DB init, error handlers, entrypoint.

All routes live in blueprints/:
  auth.py     -- magic link auth (Supabase), logout, OAuth (FB/Google/TikTok/Twitter)
  billing.py  -- Stripe checkout, portal, cancel, webhook
  api.py      -- /api/* endpoints
  website.py  -- website hub + public site renderer
  pages.py    -- dashboard, setup, calendar, onboarding, legal

Auth note:
  Password auth has been replaced with Supabase magic links.
  supabase client is stored as app.extensions['supabase'] for use in blueprints.

Token storage note:
  OAuth tokens are stored EXCLUSIVELY in the `platform_tokens` table owned
  by modules/auth_manager.py (Fernet-encrypted). There is NO second copy
  anywhere in the `users` table.
"""

import os
from flask import Flask, g, jsonify, redirect, url_for, flash, request
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

from modules.user_manager    import UserManager
from modules.auth_manager    import init_db as auth_init_db
from modules.api_manager     import CREATE_API_KEYS_TABLE
from modules.website_manager import WebsiteManager

load_dotenv()

# ---------------------------------------------------------------------------
# Secret key
# ---------------------------------------------------------------------------
_secret = os.getenv('FLASK_SECRET_KEY')
if not _secret:
    import sys
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('VERCEL_ENV'):
        sys.exit('FATAL: FLASK_SECRET_KEY is not set. Refusing to start in production.')
    _secret = 'dev-only-insecure-key'

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY']          = _secret
app.config['WTF_CSRF_TIME_LIMIT'] = 7200

# ---------------------------------------------------------------------------
# Supabase client (used for Auth — magic links)
# ---------------------------------------------------------------------------
_sb_url = os.getenv('SUPABASE_URL')
_sb_key = os.getenv('SUPABASE_ANON_KEY')
if not _sb_url or not _sb_key:
    import sys
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('VERCEL_ENV'):
        sys.exit('FATAL: SUPABASE_URL and SUPABASE_ANON_KEY must be set.')
    # Dev fallback — auth routes will fail but app still starts
    _sb_url = _sb_url or 'https://placeholder.supabase.co'
    _sb_key = _sb_key or 'placeholder'

supabase: Client = create_client(_sb_url, _sb_key)
app.extensions['supabase'] = supabase

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS(app, origins=[
    'https://cheezies-gourmet.vercel.app',
    'https://post-pilot-opal.vercel.app',
    'http://localhost:5173',
    'http://localhost:3000',
])

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------
csrf = CSRFProtect(app)

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
from blueprints import register_blueprints  # noqa: E402
register_blueprints(app, csrf)

# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, 'db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass

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
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print('Post-Pilot running at http://localhost:5000')
    app.run(debug=True, port=5000)
