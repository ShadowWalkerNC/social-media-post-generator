#!/usr/bin/env python3
"""
Post-Pilot -- Smart Social Media Hub

Changes (audit fixes):
  - OAuth state nonce (`secrets.token_urlsafe(32)`) on all three OAuth flows (CSRF-on-OAuth fix)
  - @require_plan applied to premium API routes
  - check_platform_limit enforced in api_push_all AND api_publish (billing bypass fix)
  - init_scheduler() only fires in the main process, never on gunicorn workers or test imports
  - XSS fixed in _render_public_site fallback -- user data escaped via markupsafe.escape()
  - OAuth state keys namespaced per-platform (session[f'oauth_state_{platform}'])
  - limit param in api_post_history wrapped in try/except (ValueError 500 fix)
  - Silent exception swallows now log via app.logger.exception() before returning
  - requests imported at module level (not inside route functions)
"""

import os
import json
import secrets
import sqlite3
import requests
from datetime import datetime, timedelta
from markupsafe import escape
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, flash, g
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from modules.post_generator   import SocialMediaPostGenerator
from modules.post_scheduler    import PostScheduler
from modules.analytics_client  import Analytics
from modules.publisher         import UniversalPublisher
from modules.user_manager      import UserManager, User
from modules.billing_manager   import BillingManager
from modules.website_manager   import WebsiteManager
from modules.api_manager       import v1 as v1_blueprint, CREATE_API_KEYS_TABLE
from modules.auth_manager      import (
    save_token, load_token, delete_token,
    get_valid_google_token, init_db as auth_init_db
)
from modules.plan_guard        import require_plan, check_platform_limit
from modules.scheduler_worker  import init_scheduler

load_dotenv()

# -- Secret key -- hard-fail if missing in production ---------------------
_secret = os.getenv('FLASK_SECRET_KEY')
if not _secret:
    import sys
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('RAILWAY_ENVIRONMENT'):
        sys.exit('FATAL: FLASK_SECRET_KEY is not set. Refusing to start in production.')
    _secret = 'dev-only-insecure-key'

app = Flask(__name__)
app.config['SECRET_KEY'] = _secret
app.config['WTF_CSRF_TIME_LIMIT'] = 7200  # 2 hrs -- forms open >1hr no longer silently fail

# -- Extensions -----------------------------------------------------------
csrf = CSRFProtect(app)

# NOTE: In production with multiple gunicorn workers, set REDIS_URL so
# Flask-Limiter uses a shared store. Without it each worker has its own
# counter, effectively multiplying the rate limit by worker count.
# Add REDIS_URL=redis://... to your .env for production deployments.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.getenv('REDIS_URL', 'memory://'),
)

# -- Register blueprints --------------------------------------------------
app.register_blueprint(v1_blueprint)
csrf.exempt(v1_blueprint)

# -- Flask-Login ----------------------------------------------------------
login_manager = LoginManager(app)
login_manager.login_view    = 'login'
login_manager.login_message = 'Please sign in to access Post-Pilot.'

@login_manager.user_loader
def load_user(user_id: str):
    return UserManager.get_user(user_id)


# -- DB init --------------------------------------------------------------

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
    """Create all tables that don't yet exist."""
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
            id                TEXT PRIMARY KEY,
            email             TEXT UNIQUE NOT NULL,
            password_hash     TEXT NOT NULL,
            display_name      TEXT,
            subscription_tier TEXT DEFAULT 'free',
            stripe_customer_id TEXT,
            created_at        INTEGER,
            last_login_at     INTEGER,
            business_profile  TEXT,
            platform_tokens   TEXT
        );
        ''')

        db.commit()
        db.close()
        print('DB initialised')

    auth_init_db()


try:
    init_db()
except Exception as _init_err:
    print(f'[WARN] init_db on startup failed: {_init_err}')


# -- Token helpers --------------------------------------------------------

def _uid() -> str:
    # WARNING: the 'default' fallback buckets all unauthenticated callers
    # under a single key. All callers of _get_tokens() must be protected
    # by @login_required to prevent cross-user token leakage.
    return current_user.id if current_user.is_authenticated else 'default'

def _get_tokens(uid: str = None) -> dict:
    uid = uid or _uid()
    tokens = {}
    platform_map = {
        'facebook': ['facebook_token', 'facebook_page_id'],
        'google':   ['google_token',   'google_location_id'],
        'tiktok':   ['tiktok_token'],
        'youtube':  ['youtube_token'],
    }
    for platform, keys in platform_map.items():
        rec = load_token(platform, uid)
        if rec:
            tokens[keys[0]] = rec['access_token']
            if len(keys) > 1 and rec.get('meta'):
                if platform == 'facebook':
                    tokens['facebook_page_id']  = rec['meta'].get('page_id', '')
                    tokens['instagram_token']   = rec['access_token']
                    tokens['instagram_id']      = rec['meta'].get('ig_id', '')
                elif platform == 'google':
                    tokens['google_location_id'] = rec['meta'].get('location_id', '')
                    tokens['youtube_token']      = rec['access_token']
    return tokens

def _business_name() -> str:
    if not current_user.is_authenticated:
        return 'Your Business'
    profile = current_user.__dict__.get('business_profile') or {}
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}
    return profile.get('name') or current_user.__dict__.get('display_name') or 'Your Business'


# -- Error handlers -------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(429)
def rate_limited(e):
    if request.is_json:
        return jsonify({'success': False, 'error': 'Too many requests. Please wait and try again.'}), 429
    flash('Too many attempts. Please wait a minute and try again.')
    return redirect(url_for('login')), 429


# -- AUTH ROUTES ----------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def register():
    plan = request.args.get('plan', '')
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email        = request.form.get('email', '').strip()
        password     = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        if not email or not password:
            flash('Email and password are required.')
            return render_template('register.html', plan=plan)
        if len(password) < 8:
            flash('Password must be at least 8 characters.')
            return render_template('register.html', plan=plan)
        user = UserManager.create_user(email, password, display_name=display_name)
        if not user:
            flash('An account with that email already exists.')
            return render_template('register.html', plan=plan)
        login_user(user, remember=True)
        UserManager.touch_login(user.id)
        if plan and plan != 'free':
            return redirect(url_for('billing_checkout', plan=plan))
        return redirect(url_for('onboarding'))
    return render_template('register.html', plan=plan)


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user     = UserManager.get_user_by_email(email)
        if not user or not UserManager.verify_password(user, password):
            flash('Invalid email or password.')
            return render_template('login.html')
        login_user(user, remember=True)
        UserManager.touch_login(user.id)
        return redirect(request.args.get('next') or url_for('home'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'success')
    return redirect(url_for('index'))


# -- LANDING / PUBLIC ROUTES ----------------------------------------------

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('index.html', site={})


# -- LEGAL PAGES ----------------------------------------------------------

@app.route('/legal/privacy')
def legal_privacy():
    return render_template('legal/privacy.html')

@app.route('/legal/terms')
def legal_terms():
    return render_template('legal/terms.html')


# -- BILLING ROUTES -------------------------------------------------------

@app.route('/billing')
@login_required
def billing():
    sub_info     = BillingManager.get_subscription_info(current_user.id)
    current_tier = current_user.subscription_tier
    return render_template('billing.html', sub_info=sub_info, current_tier=current_tier)


@app.route('/billing/checkout')
@login_required
def billing_checkout():
    plan        = request.args.get('plan', '')
    base        = request.host_url.rstrip('/')
    success_url = f'{base}/billing?upgraded=1'
    cancel_url  = f'{base}/billing'
    url         = BillingManager.create_checkout_session(
        current_user.id, plan, success_url, cancel_url
    )
    if not url:
        flash('Could not start checkout. Please try again.')
        return redirect(url_for('billing'))
    return redirect(url)


@app.route('/billing/portal')
@login_required
def billing_portal():
    base       = request.host_url.rstrip('/')
    return_url = f'{base}/billing'
    url        = BillingManager.create_customer_portal_session(current_user.id, return_url)
    if not url:
        flash('Could not open billing portal. Please contact support.')
        return redirect(url_for('billing'))
    return redirect(url)


@app.route('/billing/cancel', methods=['POST'])
@login_required
def billing_cancel():
    ok = BillingManager.cancel_subscription(current_user.id)
    if ok:
        flash('Your plan will cancel at the end of the billing period.', 'success')
    else:
        flash('Could not cancel. Please use Manage Plan or contact support.')
    return redirect(url_for('billing'))


@app.route('/webhooks/stripe', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    payload    = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    body, code = BillingManager.handle_webhook(payload, sig_header)
    return jsonify(body), code


# -- WEBSITE HUB ROUTES ---------------------------------------------------

@app.route('/website_hub')
@app.route('/website')
@login_required
def website_hub():
    wm   = WebsiteManager(user_id=current_user.id)
    site = wm.get_site()
    return render_template(
        'website_hub.html',
        site=site,
        business_name=_business_name(),
    )


@app.route('/website/save', methods=['POST'])
@login_required
def website_save():
    wm      = WebsiteManager(user_id=current_user.id)
    payload = request.get_json(silent=True) or {}
    result  = wm.save_site(payload)
    return jsonify(result)


@app.route('/website/publish', methods=['POST'])
@login_required
def website_publish():
    wm        = WebsiteManager(user_id=current_user.id)
    data      = request.get_json(silent=True) or {}
    published = bool(data.get('published', False))
    result    = wm.set_published(published)
    return jsonify(result)


@app.route('/website/verify_domain', methods=['POST'])
@login_required
def website_verify_domain():
    wm     = WebsiteManager(user_id=current_user.id)
    data   = request.get_json(silent=True) or {}
    domain = data.get('domain', '').strip()
    if not domain:
        return jsonify({'success': False, 'error': 'domain required'})
    result = wm.verify_domain(domain)
    return jsonify(result)


# -- PUBLIC SITE RENDERER -------------------------------------------------

@app.route('/site/preview')
@login_required
def site_preview():
    wm   = WebsiteManager(user_id=current_user.id)
    site = wm.get_site()
    return _render_public_site(site, preview=True)


@app.route('/site/<user_id>')
def site_public(user_id: str):
    wm   = WebsiteManager(user_id=user_id)
    site = wm.get_site()
    if not site.get('published'):
        return render_template('404.html'), 404
    return _render_public_site(site, preview=False)


def _render_public_site(site: dict, preview: bool = False):
    sections     = site.get('sections') or WebsiteManager.DEFAULT_SECTIONS
    active_secs  = [s for s in sections if s.get('enabled')]
    seo          = site.get('seo') or {}
    socials      = site.get('socials') or {}
    theme        = site.get('theme', 'modern')
    color        = site.get('primary_color', '#6366f1')
    try:
        return render_template(
            'public_site.html',
            site=site, sections=active_secs, seo=seo, socials=socials,
            theme=theme, primary_color=color, preview=preview,
        )
    except Exception:
        app.logger.exception('public_site.html render failed, falling back to raw HTML')
        # FIX (P0 XSS): escape all user-controlled values before interpolating into HTML
        safe_color = escape(color)
        sec_html = ''.join(
            f'<section id="{escape(s["id"])}" style="padding:2rem;border-bottom:1px solid #eee">'
            f'<h2>{escape(s["label"])}</h2></section>'
            for s in active_secs
        )
        title = escape(seo.get('title') or 'My Business')
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">'
            f'<title>{title}</title>'
            f'<style>body{{font-family:sans-serif;margin:0;padding:0}}'
            f'h1{{background:{safe_color};color:#fff;padding:2rem;margin:0}}</style>'
            f'</head><body>'
            f'{"<div style=\\"background:#fbbf24;color:#000;text-align:center;padding:.5rem;font-size:.8rem\\">PREVIEW MODE</div>" if preview else ""}'
            f'<h1>{title}</h1>{sec_html}</body></html>'
        ), 200


# -- DASHBOARD & APP PAGES ------------------------------------------------

@app.route('/dashboard')
@login_required
def home():
    return render_template('dashboard.html')

@app.route('/setup')
@login_required
def setup():
    return render_template('setup.html')

@app.route('/generate')
@login_required
def generate():
    return render_template('generate.html')

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')

@app.route('/analytics')
@login_required
def analytics_page():
    return render_template('analytics.html')

@app.route('/onboarding')
@login_required
def onboarding():
    return render_template('onboarding.html')

@app.route('/connect')
@login_required
def connect_page():
    return render_template('connect.html')


# -- CORE: UNIVERSAL PUSH -------------------------------------------------

@app.route('/api/push_all', methods=['POST'])
@login_required
@require_plan('starter')
def api_push_all():
    data      = request.json or {}
    uid       = _uid()
    platforms = data.get('platforms') or []

    # Enforce per-plan platform count limit
    if platforms:
        allowed, limit = check_platform_limit(current_user.subscription_tier, platforms)
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'Your plan allows up to {limit} platform(s) at once. Upgrade at /billing.'
            }), 403

    tokens    = _get_tokens(uid)
    publisher = UniversalPublisher(tokens, user_id=uid)
    results   = publisher.push_all(
        caption       = data.get('caption', ''),
        content_type  = data.get('content_type', 'text'),
        image_url     = data.get('image_url'),
        video_url     = data.get('video_url'),
        link_url      = data.get('link_url'),
        platforms     = platforms,
        schedule_time = data.get('schedule_time'),
        web_data      = data.get('web_data'),
    )
    UserManager.log_post(
        user_id      = uid,
        caption      = data.get('caption', ''),
        content_type = data.get('content_type', 'text'),
        image_url    = data.get('image_url'),
        video_url    = data.get('video_url'),
        platforms    = platforms,
        results      = results,
        scheduled_at = data.get('schedule_time'),
        status       = 'scheduled' if data.get('schedule_time') else 'published',
    )
    return jsonify({'success': True, 'results': results})


@app.route('/api/publish', methods=['POST'])
@app.route('/api/publish_post', methods=['POST'])
@login_required
@require_plan('starter')
def api_publish():
    data      = request.json or {}
    uid       = _uid()
    platforms = data.get('platforms') or []

    # FIX (P0 billing bypass): enforce platform limit on this route too
    if platforms:
        allowed, limit = check_platform_limit(current_user.subscription_tier, platforms)
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'Your plan allows up to {limit} platform(s) at once. Upgrade at /billing.'
            }), 403

    tokens    = _get_tokens(uid)
    publisher = UniversalPublisher(tokens, user_id=uid)
    results   = publisher.push_all(
        caption      = data.get('caption', ''),
        content_type = data.get('content_type', 'text'),
        image_url    = data.get('image_url'),
        video_url    = data.get('video_url'),
        link_url     = data.get('link_url'),
        platforms    = platforms,
    )
    UserManager.log_post(
        user_id      = uid,
        caption      = data.get('caption', ''),
        content_type = data.get('content_type', 'text'),
        image_url    = data.get('image_url'),
        video_url    = data.get('video_url'),
        platforms    = platforms,
        results      = results,
    )
    return jsonify({'success': True, 'results': results})


# -- ONBOARDING -----------------------------------------------------------

@app.route('/api/onboarding/setup', methods=['POST'])
@login_required
def api_onboarding_setup():
    data = request.json or {}
    uid  = _uid()
    business_info = {
        'name':          data.get('name', ''),
        'business_type': data.get('type', ''),
        'location':      data.get('location', ''),
        'hours':         data.get('hours', ''),
        'prompt_time':   data.get('prompt_time', '07:00'),
    }
    UserManager.save_business_profile(uid, business_info)
    return jsonify({'success': True, 'business': business_info})


# -- CONNECTION STATUS ----------------------------------------------------

@app.route('/api/connection_status', methods=['GET', 'POST'])
@login_required
def api_connection_status():
    uid    = _uid()
    tokens = _get_tokens(uid)
    status = {
        'fb':  bool(tokens.get('facebook_token') and tokens.get('facebook_page_id')),
        'ig':  bool(tokens.get('instagram_token') and tokens.get('instagram_id')),
        'yt':  bool(tokens.get('youtube_token')),
        'tt':  bool(tokens.get('tiktok_token')),
        'gb':  bool(tokens.get('google_token')),
        'web': True,
    }
    return jsonify({'success': True, 'platforms': status, 'connections': status})


# -- DISCONNECT -----------------------------------------------------------

@app.route('/auth/disconnect/<pid>', methods=['POST'])
@login_required
def auth_disconnect(pid):
    uid = _uid()
    platform_map = {
        'fb': 'facebook', 'ig': 'instagram',
        'tt': 'tiktok',   'yt': 'youtube', 'gb': 'google',
    }
    platform = platform_map.get(pid)
    if platform:
        delete_token(platform, uid)
        if platform == 'facebook':
            delete_token('instagram', uid)
        if platform == 'google':
            delete_token('youtube', uid)
    return jsonify({'success': True})


# -- GENERATE / SCHEDULE / ANALYTICS -------------------------------------

@app.route('/api/setup_business', methods=['POST'])
@login_required
def api_setup_business():
    data = request.json or {}
    uid  = _uid()
    info = data.get('business_info', {})
    gen  = SocialMediaPostGenerator()
    gen.setup_business(info)
    UserManager.save_business_profile(uid, info)
    return jsonify({'success': True})


@app.route('/api/get_business', methods=['GET'])
@login_required
def api_get_business():
    profile = getattr(current_user, 'business_profile', None)
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}
    return jsonify({'success': True, 'business_info': profile or {}})


@app.route('/api/setup_tokens', methods=['POST'])
@login_required
def api_setup_tokens():
    data     = request.json or {}
    uid      = _uid()
    incoming = data.get('tokens', {})
    if incoming.get('facebook_token'):
        save_token('facebook', incoming['facebook_token'],
                   meta={'page_id': incoming.get('facebook_page_id', ''),
                         'ig_id':   incoming.get('instagram_id', '')},
                   user_id=uid)
    if incoming.get('google_token'):
        save_token('google', incoming['google_token'],
                   meta={'location_id': incoming.get('google_location_id', '')},
                   user_id=uid)
    if incoming.get('tiktok_token'):
        save_token('tiktok', incoming['tiktok_token'], user_id=uid)
    return jsonify({'success': True})


@app.route('/api/generate_weekly', methods=['POST'])
@app.route('/api/generate_posts', methods=['POST'])
@login_required
@require_plan('starter')
def api_generate_weekly():
    uid     = _uid()
    profile = getattr(current_user, 'business_profile', None)
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}
    gen = SocialMediaPostGenerator()
    if profile:
        gen.setup_business(profile)
    schedule = gen.generate_weekly_schedule()
    posts = schedule if isinstance(schedule, list) else schedule.get('posts', [])
    return jsonify({'success': True, 'posts': posts, 'schedule': schedule})


@app.route('/api/generate_post', methods=['POST'])
@app.route('/api/generate_single', methods=['POST'])
@login_required
@require_plan('starter')
def api_generate_post():
    data     = request.json or {}
    template = data.get('template', 'instagram_location')
    gen      = SocialMediaPostGenerator()
    try:
        post = gen.generate_post(template)
        return jsonify({'success': True, 'post': post})
    except Exception as e:
        app.logger.exception('generate_post failed for template %s', template)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/schedule_post', methods=['POST'])
@login_required
@require_plan('starter')
def api_schedule_post():
    return jsonify(PostScheduler().schedule(request.json))


@app.route('/api/scheduled_posts', methods=['GET'])
@login_required
def api_scheduled_posts():
    uid  = _uid()
    db   = get_db()
    try:
        rows = db.execute(
            'SELECT * FROM post_history WHERE user_id = ? AND status = "scheduled" '
            'ORDER BY scheduled_at ASC',
            (uid,)
        ).fetchall()
        posts = [{
            'id':             row['id'],
            'caption':        row['caption'],
            'platforms':      json.loads(row['platforms'] or '[]'),
            'status':         row['status'],
            'scheduled_date': row['scheduled_at'],
            'time':           '',
        } for row in rows]
    except Exception:
        app.logger.exception('api_scheduled_posts failed for user %s', uid)
        posts = []
    return jsonify({'success': True, 'posts': posts})


@app.route('/api/post_history', methods=['GET'])
@login_required
def api_post_history():
    uid = _uid()
    db  = get_db()
    # FIX (P1): wrap limit param -- ?limit=abc raised ValueError -> 500
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
    except (ValueError, TypeError):
        limit = 20
    try:
        rows = db.execute(
            'SELECT * FROM post_history WHERE user_id = ? '
            'ORDER BY created_at DESC LIMIT ?',
            (uid, limit)
        ).fetchall()
        posts = [{
            'id':           row['id'],
            'caption':      row['caption'],
            'content_type': row['content_type'],
            'image_url':    row['image_url'],
            'platforms':    json.loads(row['platforms'] or '[]'),
            'status':       row['status'],
            'scheduled_at': row['scheduled_at'],
            'created_at':   row['created_at'],
            'results':      json.loads(row['results'] or '{}'),
        } for row in rows]
    except Exception as e:
        app.logger.exception('api_post_history failed for user %s', uid)
        return jsonify({'success': False, 'error': str(e), 'posts': []})
    return jsonify({'success': True, 'posts': posts, 'count': len(posts)})


@app.route('/api/bulk_schedule', methods=['POST'])
@login_required
@require_plan('pro')
def api_bulk_schedule():
    data  = request.json or {}
    uid   = _uid()
    posts = data.get('posts', [])
    for p in posts:
        UserManager.log_post(
            user_id      = uid,
            caption      = p.get('caption', ''),
            content_type = 'text',
            platforms    = p.get('platforms'),
            results      = {},
            scheduled_at = p.get('scheduled_date'),
            status       = 'scheduled',
        )
    return jsonify({'success': True, 'count': len(posts)})


@app.route('/api/delete_post', methods=['POST'])
@login_required
def api_delete_post():
    data    = request.json or {}
    post_id = data.get('post_id')
    uid     = _uid()
    if post_id:
        db = get_db()
        try:
            db.execute('DELETE FROM post_history WHERE id = ? AND user_id = ?', (post_id, uid))
            db.commit()
        except Exception as e:
            app.logger.exception('api_delete_post failed for post %s user %s', post_id, uid)
            return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': True})


@app.route('/api/analytics', methods=['POST'])
@login_required
@require_plan('pro')
def api_analytics():
    uid     = _uid()
    data    = request.json or {}
    tokens  = _get_tokens(uid)
    token   = tokens.get('facebook_token') or data.get('access_token')
    page_id = tokens.get('facebook_page_id') or data.get('page_id')
    if not token or not page_id:
        return jsonify({'success': False, 'error': 'Facebook not connected',
                        'posts': [], 'total_posts': 0})
    return jsonify(Analytics(token, page_id).get_weekly_summary())


# -- OAUTH: FACEBOOK (with state nonce) -----------------------------------

@app.route('/auth/facebook')
@login_required
def auth_facebook():
    state = secrets.token_urlsafe(32)
    # FIX (P1): namespace state key per-platform to prevent collisions
    # when user opens multiple OAuth tabs simultaneously
    session['oauth_state_facebook'] = state
    session['oauth_next']           = request.args.get('next', '/')
    session['oauth_step']           = request.args.get('step', '2')
    app_id       = os.getenv('FACEBOOK_APP_ID')
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    scopes       = 'pages_manage_posts,pages_read_engagement,instagram_content_publish,instagram_basic'
    return redirect(
        f'https://www.facebook.com/v19.0/dialog/oauth'
        f'?client_id={app_id}&redirect_uri={redirect_uri}&scope={scopes}&state={state}'
    )


@app.route('/auth/facebook/callback')
@login_required
def auth_facebook_callback():
    # FIX (P1): validate against namespaced state key
    if request.args.get('state') != session.pop('oauth_state_facebook', None):
        flash('OAuth state mismatch. Please try connecting again.')
        return redirect(url_for('connect_page'))
    if request.args.get('error'):
        flash('Facebook connection was cancelled or denied.')
        return redirect(url_for('connect_page'))
    code       = request.args.get('code')
    app_id     = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    redir      = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    try:
        token = requests.get('https://graph.facebook.com/v19.0/oauth/access_token',
                        params={'client_id': app_id, 'client_secret': app_secret,
                                'redirect_uri': redir, 'code': code},
                        timeout=10).json().get('access_token')
        page       = requests.get('https://graph.facebook.com/v19.0/me/accounts',
                             params={'access_token': token},
                             timeout=10).json().get('data', [{}])[0]
        page_id    = page.get('id')
        page_token = page.get('access_token', token)
        ig_id      = requests.get(f'https://graph.facebook.com/v19.0/{page_id}',
                             params={'fields': 'instagram_business_account',
                                     'access_token': page_token},
                             timeout=10).json()\
                        .get('instagram_business_account', {}).get('id')
        uid = _uid()
        save_token('facebook', page_token,
                   meta={'page_id': page_id, 'ig_id': ig_id},
                   user_id=uid)
    except Exception as e:
        app.logger.exception('Facebook OAuth callback failed')
        flash(f'Facebook connection failed: {e}')
        return redirect(url_for('connect_page'))
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '2')
    return redirect(
        f'/onboarding?connected=facebook&step={step}'
        if next_url == '/onboarding' else url_for('home')
    )


# -- OAUTH: GOOGLE (with state nonce) -------------------------------------

@app.route('/auth/google')
@login_required
def auth_google():
    state = secrets.token_urlsafe(32)
    # FIX (P1): namespace state key per-platform
    session['oauth_state_google'] = state
    session['oauth_next']         = request.args.get('next', '/')
    session['oauth_step']         = request.args.get('step', '3')
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    redir     = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    scope     = 'https://www.googleapis.com/auth/business.manage https://www.googleapis.com/auth/youtube.upload'
    return redirect(
        f'https://accounts.google.com/o/oauth2/v2/auth'
        f'?client_id={client_id}&redirect_uri={redir}'
        f'&response_type=code&scope={scope}&access_type=offline&state={state}'
    )


@app.route('/auth/google/callback')
@login_required
def auth_google_callback():
    # FIX (P1): validate against namespaced state key
    if request.args.get('state') != session.pop('oauth_state_google', None):
        flash('OAuth state mismatch. Please try connecting again.')
        return redirect(url_for('connect_page'))
    if request.args.get('error'):
        flash('Google connection was cancelled or denied.')
        return redirect(url_for('connect_page'))
    code   = request.args.get('code')
    cid    = os.getenv('GOOGLE_CLIENT_ID')
    csec   = os.getenv('GOOGLE_CLIENT_SECRET')
    redir  = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    try:
        tokens = requests.post('https://oauth2.googleapis.com/token',
                          data={'code': code, 'client_id': cid, 'client_secret': csec,
                                'redirect_uri': redir, 'grant_type': 'authorization_code'},
                          timeout=10).json()
        gtoken = tokens.get('access_token')
        rtoken = tokens.get('refresh_token')
        accts  = requests.get('https://mybusinessaccountmanagement.googleapis.com/v1/accounts',
                         headers={'Authorization': f'Bearer {gtoken}'},
                         timeout=10).json()
        acct   = (accts.get('accounts') or [{}])[0].get('name', '')
        locs   = requests.get(f'https://mybusinessbusinessinformation.googleapis.com/v1/{acct}/locations',
                         headers={'Authorization': f'Bearer {gtoken}'},
                         timeout=10).json()
        loc_id = (locs.get('locations') or [{}])[0].get('name', '')
        uid = _uid()
        save_token('google', gtoken,
                   refresh_token=rtoken,
                   expires_at=datetime.utcnow() + timedelta(hours=1),
                   meta={'location_id': loc_id},
                   user_id=uid)
    except Exception as e:
        app.logger.exception('Google OAuth callback failed')
        flash(f'Google connection failed: {e}')
        return redirect(url_for('connect_page'))
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '3')
    return redirect(
        f'/onboarding?connected=google&step={step}'
        if next_url == '/onboarding' else url_for('home')
    )


# -- OAUTH: TIKTOK (with state nonce) -------------------------------------

@app.route('/auth/tiktok')
@login_required
def auth_tiktok():
    state = secrets.token_urlsafe(32)
    # FIX (P1): namespace state key per-platform
    session['oauth_state_tiktok'] = state
    session['oauth_next']         = request.args.get('next', '/')
    session['oauth_step']         = request.args.get('step', '4')
    client_key = os.getenv('TIKTOK_CLIENT_KEY')
    redir      = os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:5000/auth/tiktok/callback')
    scope      = 'user.info.basic,video.upload,video.publish'
    return redirect(
        f'https://www.tiktok.com/v2/auth/authorize'
        f'?client_key={client_key}&redirect_uri={redir}&response_type=code&scope={scope}&state={state}'
    )


@app.route('/auth/tiktok/callback')
@login_required
def auth_tiktok_callback():
    # FIX (P1): validate against namespaced state key
    if request.args.get('state') != session.pop('oauth_state_tiktok', None):
        flash('OAuth state mismatch. Please try connecting again.')
        return redirect(url_for('connect_page'))
    if request.args.get('error'):
        flash('TikTok connection was cancelled or denied.')
        return redirect(url_for('connect_page'))
    code   = request.args.get('code')
    ckey   = os.getenv('TIKTOK_CLIENT_KEY')
    csec   = os.getenv('TIKTOK_CLIENT_SECRET')
    redir  = os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:5000/auth/tiktok/callback')
    try:
        tokens = requests.post('https://open.tiktokapis.com/v2/oauth/token/',
                          data={'client_key': ckey, 'client_secret': csec, 'code': code,
                                'grant_type': 'authorization_code', 'redirect_uri': redir},
                          headers={'Content-Type': 'application/x-www-form-urlencoded'},
                          timeout=10).json()
        tt_token  = tokens.get('access_token')
        tt_rtoken = tokens.get('refresh_token')
        uid = _uid()
        save_token('tiktok', tt_token,
                   refresh_token=tt_rtoken,
                   expires_at=datetime.utcnow() + timedelta(hours=24),
                   user_id=uid)
    except Exception as e:
        app.logger.exception('TikTok OAuth callback failed')
        flash(f'TikTok connection failed: {e}')
        return redirect(url_for('connect_page'))
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '4')
    return redirect(
        f'/onboarding?connected=tiktok&step={step}'
        if next_url == '/onboarding' else url_for('home')
    )


# -- ENTRYPOINT -----------------------------------------------------------

# FIX (P0): Only start the background scheduler in the main process.
# Previously init_scheduler() ran at module import level, causing it to
# fire on every gunicorn worker and on every pytest import, resulting in
# duplicate scheduled post execution and background jobs running in tests.
# gunicorn --preload users the main process; pytest never reaches this block.
import multiprocessing
if __name__ == '__main__' or (
    os.getenv('RAILWAY_ENVIRONMENT') and multiprocessing.current_process().name == 'MainProcess'
):
    init_scheduler()

if __name__ == '__main__':
    init_db()
    print('Post-Pilot running at http://localhost:5000')
    app.run(debug=True, port=5000)
