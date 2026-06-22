"""
blueprints/pages.py
Simple page routes: landing, dashboard, setup, generate, calendar,
onboarding, connect, analytics, legal.
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('pages.home'))
    return render_template('index.html', site={})


@pages_bp.route('/dashboard')
@login_required
def home():
    return render_template('dashboard.html')


@pages_bp.route('/setup')
@login_required
def setup():
    return render_template('setup.html')


@pages_bp.route('/generate')
@login_required
def generate():
    return render_template('generate.html')


@pages_bp.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')


@pages_bp.route('/analytics')
@login_required
def analytics_page():
    return render_template('analytics.html')


@pages_bp.route('/onboarding')
@login_required
def onboarding():
    return render_template('onboarding.html')


@pages_bp.route('/connect')
@login_required
def connect_page():
    return render_template('connect.html')


@pages_bp.route('/legal/privacy')
def legal_privacy():
    return render_template('legal/privacy.html')


@pages_bp.route('/legal/terms')
def legal_terms():
    return render_template('legal/terms.html')
