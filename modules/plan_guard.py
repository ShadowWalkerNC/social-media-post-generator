"""
plan_guard.py — Subscription plan enforcement for Post-Pilot.

Provides:
    @require_plan('starter')       — route decorator
    check_platform_limit(tier, platforms)  — helper for push_all

Plan hierarchy (weakest → strongest):
    free < starter < pro < agency

Feature limits are defined in PRICING.md and enforced here.
This is the single source of truth for server-side plan checks.

Usage in app.py:
    from modules.plan_guard import require_plan, check_platform_limit

    @app.route('/api/generate_weekly', methods=['POST'])
    @login_required
    @require_plan('starter')
    def api_generate_weekly():
        ...

    # Inside api_push_all, before publishing:
    platforms = data.get('platforms') or []
    if not check_platform_limit(current_user.subscription_tier, platforms):
        return jsonify({'success': False, 'error': {...}}), 403
"""

import functools
import logging
from flask import jsonify, request, redirect, url_for, flash
from flask_login import current_user

logger = logging.getLogger(__name__)

# Plan rank: higher = more access
PLAN_RANK = {
    'free':    0,
    'starter': 1,
    'pro':     2,
    'agency':  3,
}

# Per-plan platform publish limits (PRICING.md)
PLATFORM_LIMITS = {
    'free':    1,
    'starter': 3,
    'pro':     6,
    'agency':  6,
}

# Per-plan monthly AI generation limits (PRICING.md)
AI_MONTHLY_LIMITS = {
    'free':    10,
    'starter': 100,
    'pro':     500,
    'agency':  999999,  # unlimited
}


def _rank(tier: str) -> int:
    return PLAN_RANK.get((tier or 'free').lower(), 0)


def require_plan(minimum_plan: str):
    """
    Decorator: block access if the logged-in user is below `minimum_plan`.

    - API routes (/api/*) and JSON requests return HTTP 403 JSON.
    - HTML routes redirect to /billing with a flash message.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            user_tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
            if _rank(user_tier) < _rank(minimum_plan):
                logger.warning(
                    'Plan gate blocked: user=%s tier=%s path=%s requires=%s',
                    getattr(current_user, 'id', 'anon'),
                    user_tier, request.path, minimum_plan,
                )
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False,
                        'error': {
                            'code':        'PLAN_REQUIRED',
                            'message':     f'This feature requires the {minimum_plan.title()} plan or higher.',
                            'upgrade_url': '/billing',
                        }
                    }), 403
                flash(
                    f'Upgrade to the {minimum_plan.title()} plan to unlock this feature.',
                    'warning'
                )
                return redirect(url_for('billing'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def check_platform_limit(user_tier: str, requested_platforms: list) -> tuple[bool, str]:
    """
    Check whether a user's plan allows publishing to the requested number of platforms.

    Returns:
        (True,  '')           — allowed
        (False, reason_str)   — blocked, with a user-facing reason message
    """
    tier  = (user_tier or 'free').lower()
    limit = PLATFORM_LIMITS.get(tier, 1)
    count = len(requested_platforms or [])
    if count <= limit:
        return True, ''
    return False, (
        f'Your {tier.title()} plan allows publishing to {limit} platform(s) at once. '
        f'You selected {count}. Upgrade to publish to more platforms.'
    )


def get_plan_limits(user_tier: str) -> dict:
    """
    Return a dict of all limits for the given tier.
    Useful for the billing/dashboard UI to show what the user can do.
    """
    tier = (user_tier or 'free').lower()
    return {
        'tier':              tier,
        'platform_limit':    PLATFORM_LIMITS.get(tier, 1),
        'ai_monthly_limit':  AI_MONTHLY_LIMITS.get(tier, 10),
        'scheduling':        _rank(tier) >= _rank('starter'),
        'analytics':         _rank(tier) >= _rank('pro'),
        'bulk_schedule':     _rank(tier) >= _rank('pro'),
        'api_access':        _rank(tier) >= _rank('pro'),
        'website_hub':       _rank(tier) >= _rank('starter'),
        'white_label':       _rank(tier) >= _rank('agency'),
    }
