#!/usr/bin/env python3
"""
PostPilot Pro — Smart Content Hub
Write once → smart routing sends videos to video platforms,
text to text platforms, images to image platforms.
"""

import os
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, flash
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from dotenv import load_dotenv

from modules.post_generator   import SocialMediaPostGenerator
from modules.post_scheduler    import PostScheduler
from modules.analytics_client  import Analytics
from modules.publisher         import UniversalPublisher
from modules.user_manager      import UserManager, User
from modules.billing_manager   import BillingManager

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me')

# ── Flask-Login ──────────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view    = 'login'
login_manager.login_message = 'Please sign in to access PostPilot Pro.'

@login_manager.user_loader
def load_user(user_id: str):
    return UserManager.get_user(user_id)


user_sessions = {}   # in-memory token cache, keyed by user UUID


# ── AUTH ROUTES ───────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email        = request.form.get('email', '').strip()
        password     = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        if not email or not password:
            flash('Email and password are required.')
            return render_template('register.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters.')
            return render_template('register.html')
        user = UserManager.create_user(email, password, display_name=display_name)
        if not user:
            flash('An account with that email already exists.')
            return render_template('register.html')
        login_user(user, remember=True)
        UserManager.touch_login(user.id)
        return redirect(url_for('onboarding'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
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
    return redirect(url_for('login'))


# ── BILLING ROUTES ────────────────────────────────────────────────────────

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
        flash('Your plan will cancel at the end of the billing period. You keep access until then.', 'success')
    else:
        flash('Could not cancel. Please use Manage Plan or contact support.')
    return redirect(url_for('billing'))


@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Stripe sends events here. Must be public (no @login_required)."""
    payload    = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    body, code = BillingManager.handle_webhook(payload, sig_header)
    return jsonify(body), code


# ── PAGE ROUTES ───────────────────────────────────────────────────────────

@app.route('/')
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


# ── HELPER ────────────────────────────────────────────────────────────────

def _uid() -> str:
    return current_user.id if current_user.is_authenticated else 'default'


# ── CORE: UNIVERSAL PUSH ─────────────────────────────────────────────────

@app.route('/api/push_all', methods=['POST'])
@login_required
def api_push_all():
    data      = request.json
    uid       = _uid()
    tokens    = user_sessions.get(uid, {}).get('tokens', {})
    publisher = UniversalPublisher(tokens, user_id=uid)
    results   = publisher.push_all(
        caption       = data.get('caption', ''),
        content_type  = data.get('content_type', 'text'),
        image_url     = data.get('image_url'),
        video_url     = data.get('video_url'),
        link_url      = data.get('link_url'),
        platforms     = data.get('platforms'),
        schedule_time = data.get('schedule_time'),
        web_data      = data.get('web_data'),
    )
    UserManager.log_post(
        user_id      = uid,
        caption      = data.get('caption', ''),
        content_type = data.get('content_type', 'text'),
        image_url    = data.get('image_url'),
        video_url    = data.get('video_url'),
        platforms    = data.get('platforms'),
        results      = results,
        scheduled_at = data.get('schedule_time'),
        status       = 'scheduled' if data.get('schedule_time') else 'published',
    )
    return jsonify({'success': True, 'results': results})


@app.route('/api/publish', methods=['POST'])
@login_required
def api_publish():
    data      = request.json
    uid       = _uid()
    tokens    = user_sessions.get(uid, {}).get('tokens', {})
    publisher = UniversalPublisher(tokens, user_id=uid)
    results   = publisher.push_all(
        caption      = data.get('caption', ''),
        content_type = data.get('content_type', 'text'),
        image_url    = data.get('image_url'),
        video_url    = data.get('video_url'),
        link_url     = data.get('link_url'),
        platforms    = data.get('platforms'),
    )
    UserManager.log_post(
        user_id      = uid,
        caption      = data.get('caption', ''),
        content_type = data.get('content_type', 'text'),
        image_url    = data.get('image_url'),
        video_url    = data.get('video_url'),
        platforms    = data.get('platforms'),
        results      = results,
    )
    return jsonify({'success': True, 'results': results})


# ── ONBOARDING SETUP ─────────────────────────────────────────────────────

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
    user_sessions.setdefault(uid, {})
    user_sessions[uid]['business'] = business_info
    gen = user_sessions[uid].get('generator', SocialMediaPostGenerator())
    gen.setup_business(business_info)
    user_sessions[uid]['generator'] = gen
    return jsonify({'success': True, 'business': business_info})


# ── CONNECTION STATUS ────────────────────────────────────────────────────

@app.route('/api/connection_status', methods=['POST'])
@login_required
def api_connection_status():
    uid    = _uid()
    tokens = user_sessions.get(uid, {}).get('tokens', {})
    return jsonify({
        'success': True,
        'platforms': {
            'fb':  bool(tokens.get('facebook_token') and tokens.get('facebook_page_id')),
            'ig':  bool(tokens.get('instagram_token') and tokens.get('instagram_id')),
            'yt':  bool(tokens.get('youtube_token')),
            'tt':  True,
            'gb':  bool(tokens.get('google_token')),
            'web': True,
        }
    })


# ── GENERATE / SCHEDULE / ANALYTICS ─────────────────────────────────────

@app.route('/api/setup_business', methods=['POST'])
@login_required
def api_setup_business():
    data = request.json
    uid  = _uid()
    user_sessions.setdefault(uid, {})
    gen  = SocialMediaPostGenerator()
    gen.setup_business(data.get('business_info', {}))
    user_sessions[uid]['generator'] = gen
    return jsonify({'success': True})


@app.route('/api/setup_tokens', methods=['POST'])
@login_required
def api_setup_tokens():
    data = request.json
    uid  = _uid()
    user_sessions.setdefault(uid, {})
    user_sessions[uid]['tokens'] = data.get('tokens', {})
    gen = user_sessions[uid].get('generator', SocialMediaPostGenerator())
    gen.setup_api_tokens(data.get('tokens', {}))
    user_sessions[uid]['generator'] = gen
    return jsonify({'success': True})


@app.route('/api/generate_weekly', methods=['POST'])
@login_required
def api_generate_weekly():
    uid = _uid()
    gen = user_sessions.get(uid, {}).get('generator', SocialMediaPostGenerator())
    return jsonify({'success': True, 'schedule': gen.generate_weekly_schedule()})


@app.route('/api/generate_post', methods=['POST'])
@login_required
def api_generate_post():
    data     = request.json
    uid      = _uid()
    template = data.get('template', 'instagram_location')
    gen      = user_sessions.get(uid, {}).get('generator', SocialMediaPostGenerator())
    try:
        return jsonify({'success': True, 'post': gen.generate_post(template)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/schedule_post', methods=['POST'])
@login_required
def api_schedule_post():
    return jsonify(PostScheduler().schedule(request.json))


@app.route('/api/analytics', methods=['POST'])
@login_required
def api_analytics():
    uid     = _uid()
    data    = request.json
    tokens  = user_sessions.get(uid, {}).get('tokens', {})
    token   = tokens.get('facebook_token') or data.get('access_token')
    page_id = tokens.get('facebook_page_id') or data.get('page_id')
    if not token or not page_id:
        return jsonify({'success': False, 'error': 'Facebook not connected',
                        'posts': [], 'total_posts': 0})
    return jsonify(Analytics(token, page_id).get_weekly_summary())


# ── OAUTH: META ────────────────────────────────────────────────────────

@app.route('/auth/facebook')
@login_required
def auth_facebook():
    app_id       = os.getenv('FACEBOOK_APP_ID')
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    scopes       = 'pages_manage_posts,pages_read_engagement,instagram_content_publish,instagram_basic'
    session['oauth_next'] = request.args.get('next', '/')
    session['oauth_step'] = request.args.get('step', '2')
    session['oauth_platform'] = 'facebook'
    return redirect(f'https://www.facebook.com/v19.0/dialog/oauth?client_id={app_id}&redirect_uri={redirect_uri}&scope={scopes}')


@app.route('/auth/facebook/callback')
@login_required
def auth_facebook_callback():
    import requests as req
    code       = request.args.get('code')
    app_id     = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    redir      = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    token      = req.get('https://graph.facebook.com/v19.0/oauth/access_token',
                         params={'client_id': app_id, 'client_secret': app_secret,
                                 'redirect_uri': redir, 'code': code}).json().get('access_token')
    page       = req.get('https://graph.facebook.com/v19.0/me/accounts',
                         params={'access_token': token}).json().get('data', [{}])[0]
    page_id    = page.get('id')
    page_token = page.get('access_token', token)
    ig_id      = req.get(f'https://graph.facebook.com/v19.0/{page_id}',
                         params={'fields': 'instagram_business_account',
                                 'access_token': page_token}).json()\
                    .get('instagram_business_account', {}).get('id')
    uid = _uid()
    user_sessions.setdefault(uid, {})
    user_sessions[uid].setdefault('tokens', {}).update(
        facebook_token=page_token, facebook_page_id=page_id,
        instagram_token=page_token, instagram_id=ig_id)
    from modules.auth_manager import save_token
    save_token('facebook', page_token, meta={'page_id': page_id, 'ig_id': ig_id}, user_id=uid)
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '2')
    platform = session.pop('oauth_platform', 'facebook')
    return redirect(f'/onboarding?connected={platform}&step={step}' if next_url == '/onboarding' else url_for('home'))


# ── OAUTH: GOOGLE ────────────────────────────────────────────────────────

@app.route('/auth/google')
@login_required
def auth_google():
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    redir     = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    scope     = 'https://www.googleapis.com/auth/business.manage https://www.googleapis.com/auth/youtube.upload'
    session['oauth_next'] = request.args.get('next', '/')
    session['oauth_step'] = request.args.get('step', '3')
    session['oauth_platform'] = 'google'
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redir}&response_type=code&scope={scope}&access_type=offline')


@app.route('/auth/google/callback')
@login_required
def auth_google_callback():
    import requests as req
    from modules.auth_manager import save_token
    from datetime import datetime, timedelta
    code    = request.args.get('code')
    cid     = os.getenv('GOOGLE_CLIENT_ID')
    csec    = os.getenv('GOOGLE_CLIENT_SECRET')
    redir   = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    tokens  = req.post('https://oauth2.googleapis.com/token',
                       data={'code': code, 'client_id': cid, 'client_secret': csec,
                             'redirect_uri': redir, 'grant_type': 'authorization_code'}).json()
    gtoken  = tokens.get('access_token')
    rtoken  = tokens.get('refresh_token')
    accts   = req.get('https://mybusinessaccountmanagement.googleapis.com/v1/accounts',
                      headers={'Authorization': f'Bearer {gtoken}'}).json()
    acct    = (accts.get('accounts') or [{}])[0].get('name', '')
    locs    = req.get(f'https://mybusinessbusinessinformation.googleapis.com/v1/{acct}/locations',
                      headers={'Authorization': f'Bearer {gtoken}'}).json()
    loc_id  = (locs.get('locations') or [{}])[0].get('name', '')
    uid = _uid()
    user_sessions.setdefault(uid, {})
    user_sessions[uid].setdefault('tokens', {}).update(
        google_token=gtoken, google_location_id=loc_id, youtube_token=gtoken)
    save_token('google', gtoken, refresh_token=rtoken,
               expires_at=datetime.utcnow() + timedelta(hours=1),
               meta={'location_id': loc_id}, user_id=uid)
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '3')
    platform = session.pop('oauth_platform', 'google')
    return redirect(f'/onboarding?connected={platform}&step={step}' if next_url == '/onboarding' else url_for('home'))


# ── OAUTH: TIKTOK ────────────────────────────────────────────────────────

@app.route('/auth/tiktok')
@login_required
def auth_tiktok():
    client_key = os.getenv('TIKTOK_CLIENT_KEY')
    redir      = os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:5000/auth/tiktok/callback')
    scope      = 'user.info.basic,video.upload,video.publish'
    session['oauth_next'] = request.args.get('next', '/')
    session['oauth_step'] = request.args.get('step', '4')
    session['oauth_platform'] = 'tiktok'
    return redirect(f'https://www.tiktok.com/v2/auth/authorize?client_key={client_key}&redirect_uri={redir}&response_type=code&scope={scope}')


@app.route('/auth/tiktok/callback')
@login_required
def auth_tiktok_callback():
    import requests as req
    from modules.auth_manager import save_token
    from datetime import datetime, timedelta
    code   = request.args.get('code')
    ckey   = os.getenv('TIKTOK_CLIENT_KEY')
    csec   = os.getenv('TIKTOK_CLIENT_SECRET')
    redir  = os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:5000/auth/tiktok/callback')
    tokens = req.post('https://open.tiktokapis.com/v2/oauth/token/',
                      data={'client_key': ckey, 'client_secret': csec, 'code': code,
                            'grant_type': 'authorization_code', 'redirect_uri': redir},
                      headers={'Content-Type': 'application/x-www-form-urlencoded'}).json()
    tt_token  = tokens.get('access_token')
    tt_rtoken = tokens.get('refresh_token')
    uid = _uid()
    user_sessions.setdefault(uid, {})
    user_sessions[uid].setdefault('tokens', {}).update(tiktok_token=tt_token)
    save_token('tiktok', tt_token, refresh_token=tt_rtoken,
               expires_at=datetime.utcnow() + timedelta(hours=24), user_id=uid)
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '4')
    platform = session.pop('oauth_platform', 'tiktok')
    return redirect(f'/onboarding?connected={platform}&step={step}' if next_url == '/onboarding' else url_for('home'))


if __name__ == '__main__':
    print('🚀 PostPilot Pro — Smart Content Hub')
    print('🌐 Open: http://localhost:5000')
    app.run(debug=True, port=5000)
