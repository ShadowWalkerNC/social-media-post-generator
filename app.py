#!/usr/bin/env python3
"""
PostPilot Pro — Main Flask App
GUI web application with Facebook/Instagram API integration
"""

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from modules.post_generator import SocialMediaPostGenerator
from modules.meta_client import MetaAPI
from modules.post_scheduler import PostScheduler
from modules.analytics_client import Analytics

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

user_sessions = {}


# ─────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────

@app.route('/')
def home():
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
# API ROUTES
# ─────────────────────────────────────

@app.route('/api/setup_business', methods=['POST'])
def api_setup_business():
    data = request.json
    uid = data.get('user_id', 'default')
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
    uid = data.get('user_id', 'default')
    gen = user_sessions.get(uid, {}).get('generator', SocialMediaPostGenerator())
    gen.setup_api_tokens(data.get('tokens', {}))
    user_sessions[uid]['generator'] = gen
    return jsonify({'success': True, 'message': 'Tokens configured'})


@app.route('/api/generate_weekly', methods=['POST'])
def api_generate_weekly():
    data = request.json
    uid = data.get('user_id', 'default')
    gen = user_sessions.get(uid, {}).get('generator', SocialMediaPostGenerator())
    schedule = gen.generate_weekly_schedule()
    return jsonify({'success': True, 'schedule': schedule})


@app.route('/api/generate_post', methods=['POST'])
def api_generate_post():
    data = request.json
    uid = data.get('user_id', 'default')
    template = data.get('template')
    gen = user_sessions.get(uid, {}).get('generator', SocialMediaPostGenerator())
    post = gen.generate_post(template)
    return jsonify({'success': True, 'post': post})


@app.route('/api/publish_facebook', methods=['POST'])
def api_publish_facebook():
    data = request.json
    uid = data.get('user_id', 'default')
    gen = user_sessions.get(uid, {}).get('generator')
    if not gen:
        return jsonify({'success': False, 'error': 'Business not set up'})
    result = gen.publish_to_facebook(data.get('post', {}), data.get('image_url'))
    return jsonify(result)


@app.route('/api/publish_instagram', methods=['POST'])
def api_publish_instagram():
    data = request.json
    uid = data.get('user_id', 'default')
    gen = user_sessions.get(uid, {}).get('generator')
    if not gen:
        return jsonify({'success': False, 'error': 'Business not set up'})
    result = gen.publish_to_instagram(data.get('post', {}), data.get('image_url'))
    return jsonify(result)


@app.route('/api/schedule_post', methods=['POST'])
def api_schedule_post():
    data = request.json
    scheduler = PostScheduler()
    result = scheduler.schedule(data)
    return jsonify(result)


@app.route('/api/analytics', methods=['POST'])
def api_analytics():
    data = request.json
    a = Analytics(data.get('access_token'), data.get('page_id'))
    result = a.get_weekly_summary()
    return jsonify(result)


# ─────────────────────────────────────
# META OAUTH FLOW
# ─────────────────────────────────────

@app.route('/auth/facebook')
def auth_facebook():
    app_id = os.getenv('FACEBOOK_APP_ID')
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')
    scopes = 'pages_manage_posts,pages_read_engagement,instagram_content_publish,instagram_basic'
    url = (f"https://www.facebook.com/v19.0/dialog/oauth"
           f"?client_id={app_id}&redirect_uri={redirect_uri}&scope={scopes}")
    return redirect(url)


@app.route('/auth/facebook/callback')
def auth_facebook_callback():
    import requests as req
    code = request.args.get('code')
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/facebook/callback')

    token_res = req.get(
        'https://graph.facebook.com/v19.0/oauth/access_token',
        params={'client_id': app_id, 'client_secret': app_secret,
                'redirect_uri': redirect_uri, 'code': code}
    ).json()
    access_token = token_res.get('access_token')

    pages_res = req.get(
        'https://graph.facebook.com/v19.0/me/accounts',
        params={'access_token': access_token}
    ).json()
    page = pages_res.get('data', [{}])[0]
    page_id = page.get('id')
    page_token = page.get('access_token', access_token)

    ig_res = req.get(
        f'https://graph.facebook.com/v19.0/{page_id}',
        params={'fields': 'instagram_business_account', 'access_token': page_token}
    ).json()
    ig_id = ig_res.get('instagram_business_account', {}).get('id')

    session['tokens'] = {
        'facebook_token': page_token,
        'facebook_page_id': page_id,
        'instagram_token': page_token,
        'instagram_id': ig_id
    }
    return redirect(url_for('generate'))


if __name__ == '__main__':
    print('🚀 PostPilot Pro starting at http://localhost:5000')
    app.run(debug=True, port=5000)
