"""
blueprints/auth.py
Authentication routes: magic link (Supabase Auth), logout.
OAuth flows: Facebook, Google, TikTok, Twitter/X.
"""

import base64
import hashlib
import os
import secrets
import requests
from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify, current_app
)
from flask_login import login_user, logout_user, login_required, current_user

from modules.user_manager  import UserManager
from modules.auth_manager  import save_token, delete_token
from blueprints.utils      import _uid

auth_bp = Blueprint('auth', __name__)

APP_URL = os.getenv('APP_URL', 'https://post-pilot-opal.vercel.app')


# ---------------------------------------------------------------------------
# Magic Link helpers
# ---------------------------------------------------------------------------

def _get_supabase():
    return current_app.extensions['supabase']


def _send_magic_link(email: str, redirect_to: str = None) -> bool:
    sb = _get_supabase()
    try:
        params = {'email': email}
        if redirect_to:
            params['options'] = {'email_redirect_to': redirect_to}
        sb.auth.sign_in_with_otp(params)
        current_app.logger.info('Magic link sent to %s', email)
        return True
    except Exception as exc:
        current_app.logger.error('magic link send failed for %s: %s', email, exc, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# DEV LOGIN — bypass email for dashboard testing
# Usage: /dev-login?email=you@example.com&key=<DEV_LOGIN_KEY>
# Disabled automatically when DEV_LOGIN_KEY is not set.
# ---------------------------------------------------------------------------

@auth_bp.route('/dev-login')
def dev_login():
    dev_key = os.getenv('DEV_LOGIN_KEY', '')
    if not dev_key:
        return 'Dev login is disabled.', 403
    if request.args.get('key') != dev_key:
        return 'Invalid key.', 403
    email = request.args.get('email', '').strip().lower()
    if not email:
        return 'email param required.', 400
    user = UserManager.get_user_by_email(email)
    if not user:
        # Auto-create the user row if it doesn't exist yet
        import uuid
        fake_uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
        user = UserManager.upsert_user(fake_uid, email, full_name='Dev User')
    if not user:
        return 'Could not create user.', 500
    login_user(user, remember=True)
    UserManager.touch_login(user.id)
    flash('Dev login successful.', 'success')
    return redirect(url_for('pages.home'))


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    plan = request.args.get('plan', '')
    if current_user.is_authenticated:
        return redirect(url_for('pages.home'))
    if request.method == 'POST':
        email        = request.form.get('email', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        if not email:
            flash('Email is required.')
            return render_template('register.html', plan=plan)
        session['pending_display_name'] = display_name
        session['pending_plan']         = plan
        confirm_url = f"{APP_URL}/auth/confirm"
        if _send_magic_link(email, redirect_to=confirm_url):
            return render_template('magic_link_sent.html', email=email)
        flash('Could not send magic link — please try again or contact support.')
    return render_template('register.html', plan=plan)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('pages.home'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Email is required.')
            return render_template('login.html')
        confirm_url = f"{APP_URL}/auth/confirm"
        if _send_magic_link(email, redirect_to=confirm_url):
            return render_template('magic_link_sent.html', email=email)
        flash('Could not send magic link — please try again or contact support.')
    return render_template('login.html')


# ---------------------------------------------------------------------------
# Magic Link Confirm
# ---------------------------------------------------------------------------

@auth_bp.route('/auth/confirm')
def auth_confirm():
    token_hash = request.args.get('token_hash')
    link_type  = request.args.get('type', 'magiclink')

    if not token_hash:
        flash('Invalid or expired magic link.')
        return redirect(url_for('auth.login'))

    sb = _get_supabase()
    try:
        result  = sb.auth.verify_otp({'token_hash': token_hash, 'type': link_type})
        sb_user = result.user
    except Exception as exc:
        current_app.logger.error('OTP verify failed: %s', exc, exc_info=True)
        flash('Magic link expired or already used. Request a new one.')
        return redirect(url_for('auth.login'))

    if not sb_user:
        flash('Could not verify magic link. Please try again.')
        return redirect(url_for('auth.login'))

    email        = sb_user.email
    uid          = str(sb_user.id)
    display_name = session.pop('pending_display_name', '')
    plan         = session.pop('pending_plan', 'free')

    user = UserManager.get_user(uid)
    if not user:
        user = UserManager.upsert_user(uid, email, full_name=display_name, plan=plan)

    if not user:
        flash('Account setup failed. Please contact support.')
        return redirect(url_for('auth.login'))

    login_user(user, remember=True)
    UserManager.touch_login(uid)

    if plan and plan not in ('', 'free'):
        return redirect(url_for('billing.billing_checkout', plan=plan))
    return redirect(url_for('pages.onboarding') if display_name else url_for('pages.home'))


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'success')
    return redirect(url_for('pages.index'))


# ---------------------------------------------------------------------------
# Platform disconnect
# ---------------------------------------------------------------------------

@auth_bp.route('/auth/disconnect/<pid>', methods=['POST'])
@login_required
def auth_disconnect(pid):
    uid = _uid()
    platform_map = {
        'fb': 'facebook', 'ig': 'instagram',
        'tt': 'tiktok',   'yt': 'youtube',
        'gb': 'google',   'tw': 'twitter',
    }
    platform = platform_map.get(pid)
    if platform:
        delete_token(platform, uid)
        if platform == 'facebook':
            delete_token('instagram', uid)
        if platform == 'google':
            delete_token('youtube', uid)
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# OAuth: Facebook
# ---------------------------------------------------------------------------

@auth_bp.route('/auth/facebook')
@login_required
def auth_facebook():
    state = secrets.token_urlsafe(32)
    session['oauth_state_facebook'] = state
    session['oauth_next']           = request.args.get('next', '/')
    session['oauth_step']           = request.args.get('step', '2')
    app_id       = os.getenv('FACEBOOK_APP_ID')
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    scopes = (
        'pages_show_list,'
        'pages_read_engagement,'
        'pages_manage_posts,'
        'instagram_basic,'
        'instagram_content_publish,'
        'instagram_manage_insights'
    )
    return redirect(
        f'https://www.facebook.com/v19.0/dialog/oauth'
        f'?client_id={app_id}&redirect_uri={redirect_uri}&scope={scopes}&state={state}'
    )


@auth_bp.route('/auth/facebook/callback')
@login_required
def auth_facebook_callback():
    if request.args.get('state') != session.pop('oauth_state_facebook', None):
        flash('OAuth state mismatch. Please try connecting again.')
        return redirect(url_for('pages.connect_page'))
    if request.args.get('error'):
        flash('Facebook connection was cancelled or denied.')
        return redirect(url_for('pages.connect_page'))
    code       = request.args.get('code')
    app_id     = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    redir      = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    try:
        token = requests.get(
            'https://graph.facebook.com/v19.0/oauth/access_token',
            params={'client_id': app_id, 'client_secret': app_secret,
                    'redirect_uri': redir, 'code': code},
            timeout=10).json().get('access_token')
        page       = requests.get(
            'https://graph.facebook.com/v19.0/me/accounts',
            params={'access_token': token},
            timeout=10).json().get('data', [{}])[0]
        page_id    = page.get('id')
        page_token = page.get('access_token', token)
        ig_id      = requests.get(
            f'https://graph.facebook.com/v19.0/{page_id}',
            params={'fields': 'instagram_business_account', 'access_token': page_token},
            timeout=10).json().get('instagram_business_account', {}).get('id')
        save_token('facebook', page_token,
                   meta={'page_id': page_id, 'ig_id': ig_id},
                   user_id=_uid())
    except Exception:
        current_app.logger.exception('Facebook OAuth callback failed')
        flash('Facebook connection failed. Please try again.')
        return redirect(url_for('pages.connect_page'))
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '2')
    return redirect(
        f'/onboarding?connected=facebook&step={step}'
        if next_url == '/onboarding' else url_for('pages.home')
    )


# ---------------------------------------------------------------------------
# OAuth: Google
# ---------------------------------------------------------------------------

@auth_bp.route('/auth/google')
@login_required
def auth_google():
    state = secrets.token_urlsafe(32)
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


@auth_bp.route('/auth/google/callback')
@login_required
def auth_google_callback():
    if request.args.get('state') != session.pop('oauth_state_google', None):
        flash('OAuth state mismatch. Please try connecting again.')
        return redirect(url_for('pages.connect_page'))
    if request.args.get('error'):
        flash('Google connection was cancelled or denied.')
        return redirect(url_for('pages.connect_page'))
    code  = request.args.get('code')
    cid   = os.getenv('GOOGLE_CLIENT_ID')
    csec  = os.getenv('GOOGLE_CLIENT_SECRET')
    redir = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    try:
        tokens = requests.post(
            'https://oauth2.googleapis.com/token',
            data={'code': code, 'client_id': cid, 'client_secret': csec,
                  'redirect_uri': redir, 'grant_type': 'authorization_code'},
            timeout=10).json()
        gtoken = tokens.get('access_token')
        rtoken = tokens.get('refresh_token')
        accts  = requests.get(
            'https://mybusinessaccountmanagement.googleapis.com/v1/accounts',
            headers={'Authorization': f'Bearer {gtoken}'},
            timeout=10).json()
        acct   = (accts.get('accounts') or [{}])[0].get('name', '')
        locs   = requests.get(
            f'https://mybusinessbusinessinformation.googleapis.com/v1/{acct}/locations',
            headers={'Authorization': f'Bearer {gtoken}'},
            timeout=10).json()
        loc_id = (locs.get('locations') or [{}])[0].get('name', '')
        save_token('google', gtoken,
                   refresh_token=rtoken,
                   expires_at=datetime.utcnow() + timedelta(hours=1),
                   meta={'location_id': loc_id},
                   user_id=_uid())
    except Exception:
        current_app.logger.exception('Google OAuth callback failed')
        flash('Google connection failed. Please try again.')
        return redirect(url_for('pages.connect_page'))
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '3')
    return redirect(
        f'/onboarding?connected=google&step={step}'
        if next_url == '/onboarding' else url_for('pages.home')
    )


# ---------------------------------------------------------------------------
# OAuth: TikTok
# ---------------------------------------------------------------------------

@auth_bp.route('/auth/tiktok')
@login_required
def auth_tiktok():
    state = secrets.token_urlsafe(32)
    session['oauth_state_tiktok'] = state
    session['oauth_next']         = request.args.get('next', '/')
    session['oauth_step']         = request.args.get('step', '4')
    client_key = os.getenv('TIKTOK_CLIENT_KEY')
    redir      = os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:5000/auth/tiktok/callback')
    scope      = 'user.info.basic,video.upload,video.publish'
    return redirect(
        f'https://www.tiktok.com/v2/auth/authorize'
        f'?client_key={client_key}&redirect_uri={redir}'
        f'&response_type=code&scope={scope}&state={state}'
    )


@auth_bp.route('/auth/tiktok/callback')
@login_required
def auth_tiktok_callback():
    if request.args.get('state') != session.pop('oauth_state_tiktok', None):
        flash('OAuth state mismatch. Please try connecting again.')
        return redirect(url_for('pages.connect_page'))
    if request.args.get('error'):
        flash('TikTok connection was cancelled or denied.')
        return redirect(url_for('pages.connect_page'))
    code  = request.args.get('code')
    ckey  = os.getenv('TIKTOK_CLIENT_KEY')
    csec  = os.getenv('TIKTOK_CLIENT_SECRET')
    redir = os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:5000/auth/tiktok/callback')
    try:
        tokens = requests.post(
            'https://open.tiktokapis.com/v2/oauth/token/',
            data={'client_key': ckey, 'client_secret': csec, 'code': code,
                  'grant_type': 'authorization_code', 'redirect_uri': redir},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10).json()
        save_token('tiktok', tokens.get('access_token'),
                   refresh_token=tokens.get('refresh_token'),
                   expires_at=datetime.utcnow() + timedelta(hours=24),
                   user_id=_uid())
    except Exception:
        current_app.logger.exception('TikTok OAuth callback failed')
        flash('TikTok connection failed. Please try again.')
        return redirect(url_for('pages.connect_page'))
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '4')
    return redirect(
        f'/onboarding?connected=tiktok&step={step}'
        if next_url == '/onboarding' else url_for('pages.home')
    )


# ---------------------------------------------------------------------------
# OAuth: Twitter / X  (OAuth 2.0 + PKCE)
# ---------------------------------------------------------------------------

def _twitter_pkce_pair():
    verifier  = secrets.token_urlsafe(64)
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return verifier, challenge


@auth_bp.route('/auth/twitter')
@login_required
def auth_twitter():
    state                            = secrets.token_urlsafe(32)
    verifier, challenge              = _twitter_pkce_pair()
    session['oauth_state_twitter']   = state
    session['twitter_code_verifier'] = verifier
    session['oauth_next']            = request.args.get('next', '/')
    session['oauth_step']            = request.args.get('step', '5')
    client_id = os.getenv('TWITTER_CLIENT_ID')
    redir     = os.getenv('TWITTER_REDIRECT_URI', 'http://localhost:5000/auth/twitter/callback')
    scopes    = 'tweet.read%20tweet.write%20users.read%20offline.access'
    return redirect(
        f'https://twitter.com/i/oauth2/authorize'
        f'?response_type=code'
        f'&client_id={client_id}'
        f'&redirect_uri={redir}'
        f'&scope={scopes}'
        f'&state={state}'
        f'&code_challenge={challenge}'
        f'&code_challenge_method=S256'
    )


@auth_bp.route('/auth/twitter/callback')
@login_required
def auth_twitter_callback():
    if request.args.get('state') != session.pop('oauth_state_twitter', None):
        flash('OAuth state mismatch. Please try connecting again.')
        return redirect(url_for('pages.connect_page'))
    if request.args.get('error'):
        flash('Twitter / X connection was cancelled or denied.')
        return redirect(url_for('pages.connect_page'))
    code     = request.args.get('code')
    verifier = session.pop('twitter_code_verifier', '')
    cid      = os.getenv('TWITTER_CLIENT_ID')
    csec     = os.getenv('TWITTER_CLIENT_SECRET')
    redir    = os.getenv('TWITTER_REDIRECT_URI', 'http://localhost:5000/auth/twitter/callback')
    try:
        token_resp = requests.post(
            'https://api.twitter.com/2/oauth2/token',
            data={
                'code':          code,
                'grant_type':    'authorization_code',
                'redirect_uri':  redir,
                'code_verifier': verifier,
            },
            auth=(cid, csec),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10,
        ).json()
        access_token  = token_resp.get('access_token')
        refresh_token = token_resp.get('refresh_token')
        expires_in    = token_resp.get('expires_in', 7200)
        me = requests.get(
            'https://api.twitter.com/2/users/me',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        ).json().get('data', {})
        save_token(
            'twitter', access_token,
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
            meta={'user_id': me.get('id'), 'username': me.get('username')},
            user_id=_uid(),
        )
    except Exception:
        current_app.logger.exception('Twitter OAuth callback failed')
        flash('Twitter / X connection failed. Please try again.')
        return redirect(url_for('pages.connect_page'))
    next_url = session.pop('oauth_next', '/')
    step     = session.pop('oauth_step', '5')
    return redirect(
        f'/onboarding?connected=twitter&step={step}'
        if next_url == '/onboarding' else url_for('pages.home')
    )
