#!/usr/bin/env python3
"""
PostPilot Pro — Main Flask App
One-page command center: write once, push to Facebook, Instagram,
TikTok, Google Business, and your website simultaneously.
"""

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from modules.post_generator import SocialMediaPostGenerator
from modules.meta_client import MetaAPI
from modules.post_scheduler import PostScheduler
from modules.analytics_client import Analytics
from modules.publisher import UniversalPublisher

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

user_sessions = {}


# ─────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────

@app.route('/')
def home():
    return render_template('dashboard.html')  # Default to command center

@app.route('/landing')
def landing():
    return render_template('index.html')

@app.route('/setup')
def setup():
    return render_template('setup.html')

@app.route('/generate')
def generate():
    return render_template('generate.html')

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')


# ─────────────────────────────────────
# UNIVERSAL PUSH — core endpoint
# ─────────────────────────────────────

@app.route('/api/push_all', methods=['POST'])
def api_push_all():
    data      = request.json
    uid       = data.get('user_id', 'default')
    tokens    = user_sessions.get(uid, {}).get('tokens', {})
    publisher = UniversalPublisher(tokens)
    results   = publisher.push_all(
        caption       = data.get('caption', ''),
        image_url     = data.get('image_url'),
        link_url      = data.get('link_url'),
        platforms     = data.get('platforms', {}),
        schedule_time = data.get('schedule_time')
    )
    return jsonify({'success': True, 'results': results})


# ─────────────────────────────────────
# CONNECTION STATUS
# ─────────────────────────────────────

@app.route('/api/connection_status', methods=['POST'])
def api_connection_status():
    data   = request.json
    uid    = data.get('user_id', 'default')
    tokens = user_sessions.get(uid, {}).get('tokens', {})
    return jsonify({
        'success': True,
        'platforms': {
            'fb':  bool(tokens.get('facebook_token') and tokens.get('facebook_page_id')),
            'ig':  bool(tokens.get('instagram_token') and tokens.get('instagram_id')),
            'tt':  True,   # TikTok script always available
            'gb':  bool(tokens.get('google_token')),
            'web': True,   # Website banner always available
        }
    })


# ─────────────────────────────────────
# EXISTING API ROUTES
# ─────────────────────────────────────

@app.route('/api/setup_business', methods=['POST'])
def api_setup_business():
    data = request.json
    uid  = data.get('user_id', 'default')
    if uid not in user_sessions:
        user_sessions[uid] = {}
    gen = SocialMediaPostGenerator()
    gen.setup_business(data.get('business_info', {}))
    user_sessions[uid]['generator'] = gen
    user_sessions[uid]['business_info'] = data.get('business_info', {})
    return jsonify({'success': True, 'message': 'Business setup complete'})


@app.route('/api/setup_tokens', methods=['POST'])
def api_setup_tokens():
    data = request.json
    uid  = data.get('user_id', 'default')
    if uid not in user_sessions:
        user_sessions[uid] = {}
    user_sessions[uid]['tokens'] = data.get('tokens', {})
    gen = user_sessions[uid].get('generator', SocialMediaPostGenerator())
    gen.setup_api_tokens(data.get('tokens', {}))
    user_sessions[uid]['generator'] = gen
    return jsonify({'success': True, 'message': 'Tokens configured'})


@app.route('/api/generate_weekly', methods=['POST'])
def api_generate_weekly():
    data = request.json
    uid  = data.get('user_id', 'default')
    gen  = user_sessions.get(uid, {}).get('generator', SocialMediaPostGenerator())
    return jsonify({'success': True, 'schedule': gen.generate_weekly_schedule()})


@app.route('/api/generate_post', methods=['POST'])
def api_generate_post():
    data     = request.json
    uid      = data.get('user_id', 'default')
    template = data.get('template')
    gen      = user_sessions.get(uid, {}).get('generator', SocialMediaPostGenerator())
    return jsonify({'success': True, 'post': gen.generate_post(template)})


@app.route('/api/schedule_post', methods=['POST'])
def api_schedule_post():
    data      = request.json
    scheduler = PostScheduler()
    return jsonify(scheduler.schedule(data))


@app.route('/api/analytics', methods=['POST'])
def api_analytics():
    data     = request.json
    uid      = data.get('user_id', 'default')
    tokens   = user_sessions.get(uid, {}).get('tokens', {})
    token    = tokens.get('facebook_token') or data.get('access_token')
    page_id  = tokens.get('facebook_page_id') or data.get('page_id')
    if not token or not page_id:
        return jsonify({'success': False, 'error': 'Facebook not connected', 'posts': [], 'total_posts': 0})
    a = Analytics(token, page_id)
    return jsonify(a.get_weekly_summary())


# ─────────────────────────────────────
# META OAUTH
# ─────────────────────────────────────

@app.route('/auth/facebook')
def auth_facebook():
    app_id       = os.getenv('FACEBOOK_APP_ID')
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    scopes       = 'pages_manage_posts,pages_read_engagement,instagram_content_publish,instagram_basic'
    url = (f'https://www.facebook.com/v19.0/dialog/oauth'
           f'?client_id={app_id}&redirect_uri={redirect_uri}&scope={scopes}')
    return redirect(url)


@app.route('/auth/facebook/callback')
def auth_facebook_callback():
    import requests as req
    code         = request.args.get('code')
    app_id       = os.getenv('FACEBOOK_APP_ID')
    app_secret   = os.getenv('FACEBOOK_APP_SECRET')
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')

    token_res = req.get(
        'https://graph.facebook.com/v19.0/oauth/access_token',
        params={'client_id': app_id, 'client_secret': app_secret,
                'redirect_uri': redirect_uri, 'code': code}
    ).json()
    access_token = token_res.get('access_token')

    pages_res  = req.get('https://graph.facebook.com/v19.0/me/accounts',
                         params={'access_token': access_token}).json()
    page       = pages_res.get('data', [{}])[0]
    page_id    = page.get('id')
    page_token = page.get('access_token', access_token)

    ig_res = req.get(f'https://graph.facebook.com/v19.0/{page_id}',
                     params={'fields': 'instagram_business_account',
                             'access_token': page_token}).json()
    ig_id  = ig_res.get('instagram_business_account', {}).get('id')

    uid = 'default'
    if uid not in user_sessions:
        user_sessions[uid] = {}
    user_sessions[uid]['tokens'] = {
        'facebook_token':    page_token,
        'facebook_page_id':  page_id,
        'instagram_token':   page_token,
        'instagram_id':      ig_id
    }
    return redirect(url_for('home'))


# ─────────────────────────────────────
# GOOGLE OAUTH
# ─────────────────────────────────────

@app.route('/auth/google')
def auth_google():
    client_id    = os.getenv('GOOGLE_CLIENT_ID')
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    scopes       = 'https://www.googleapis.com/auth/business.manage'
    url = (f'https://accounts.google.com/o/oauth2/v2/auth'
           f'?client_id={client_id}&redirect_uri={redirect_uri}'
           f'&response_type=code&scope={scopes}&access_type=offline')
    return redirect(url)


@app.route('/auth/google/callback')
def auth_google_callback():
    import requests as req
    code         = request.args.get('code')
    client_id    = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')

    token_res = req.post('https://oauth2.googleapis.com/token', data={
        'code': code, 'client_id': client_id, 'client_secret': client_secret,
        'redirect_uri': redirect_uri, 'grant_type': 'authorization_code'
    }).json()
    google_token = token_res.get('access_token')

    # Get location ID
    accounts_res = req.get(
        'https://mybusinessaccountmanagement.googleapis.com/v1/accounts',
        headers={'Authorization': f'Bearer {google_token}'}
    ).json()
    account  = (accounts_res.get('accounts') or [{}])[0]
    acct_name = account.get('name', '')

    locations_res = req.get(
        f'https://mybusinessbusinessinformation.googleapis.com/v1/{acct_name}/locations',
        headers={'Authorization': f'Bearer {google_token}'}
    ).json()
    location = (locations_res.get('locations') or [{}])[0]
    loc_name = location.get('name', '')

    uid = 'default'
    if uid not in user_sessions:
        user_sessions[uid] = {}
    user_sessions[uid].setdefault('tokens', {}).update({
        'google_token':       google_token,
        'google_location_id': loc_name
    })
    return redirect(url_for('home'))


if __name__ == '__main__':
    print('🚀 PostPilot Pro — Command Center starting at http://localhost:5000')
    app.run(debug=True, port=5000)
