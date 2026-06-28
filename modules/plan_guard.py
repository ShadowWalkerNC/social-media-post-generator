"""
plan_guard.py -- Subscription plan enforcement for Post-Pilot.

Plan hierarchy (weakest to strongest):
    free < starter < pro < agency

Tier definitions (mirrors billing.html and PRICING.md):

    Free     $0          -- 5 posts/mo, 3 platforms, no agent, no inbox
    Starter  $19/$15     -- 30 posts/mo, 5 platforms, agent, inbox read-only, basic embed
    Pro      $49/$39     -- unlimited posts, 8 platforms, full agent, inbox + AI replies, full embed
    Agency   $99/$79     -- up to 5 locations, everything in Pro per location

Usage:
    @require_plan('starter')   -- blocks free users
    @require_plan('pro')       -- blocks free + starter users
    @require_plan('agency')    -- blocks all but agency

    check_platform_limit(tier, platforms)  -- returns (allowed, limit)
    check_post_limit(tier, posts_this_month)  -- returns (allowed, limit)
"""

import functools
import logging
from flask import jsonify, request, redirect, url_for, flash
from flask_login import current_user

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan hierarchy
# ---------------------------------------------------------------------------

PLAN_RANK = {
    'free':    0,
    'starter': 1,
    'pro':     2,
    'agency':  3,
}

# ---------------------------------------------------------------------------
# Feature -> minimum required plan
# ---------------------------------------------------------------------------

FEATURE_PLANS = {
    # Scheduling & publishing
    'scheduling':        'starter',   # AutomationAgent + manual schedule
    'multi_platform':    'starter',   # more than 1 platform at once
    'ai_generate':       'starter',   # OpenAI caption generation
    'bulk_schedule':     'pro',       # bulk import/schedule

    # Inbox & replies
    'inbox_read':        'starter',   # view comments from all platforms
    'inbox_reply':       'pro',       # AI draft replies + approval flow

    # Website embed
    'embed_basic':       'starter',   # specials-only embed
    'embed_full':        'pro',       # specials + events + hours embed

    # Analytics
    'analytics':         'starter',   # basic 30-day analytics
    'analytics_advanced':'pro',       # 90-day + cross-platform

    # Multi-location
    'multi_location':    'agency',    # up to 5 locations

    # Misc
    'api_access':        'pro',
    'white_label':       'agency',
    'priority_support':  'agency',
}

# ---------------------------------------------------------------------------
# Per-plan limits
# ---------------------------------------------------------------------------

# Max platforms per publish call
PLATFORM_LIMITS = {
    'free':    3,
    'starter': 5,
    'pro':     8,
    'agency':  8,
}

# Max scheduled/published posts per calendar month
POST_LIMITS = {
    'free':    5,
    'starter': 30,
    'pro':     None,    # unlimited
    'agency':  None,    # unlimited
}

# Max locations (Agency feature)
LOCATION_LIMITS = {
    'free':    1,
    'starter': 1,
    'pro':     1,
    'agency':  5,
}

# ---------------------------------------------------------------------------
# Stripe price IDs  (set real IDs in Vercel env vars)
# Format: STRIPE_PRICE_<TIER>_<INTERVAL>
# ---------------------------------------------------------------------------
import os

STRIPE_PRICES = {
    'starter_monthly': os.getenv('STRIPE_PRICE_STARTER_MONTHLY', 'price_starter_monthly'),
    'starter_annual':  os.getenv('STRIPE_PRICE_STARTER_ANNUAL',  'price_starter_annual'),
    'pro_monthly':     os.getenv('STRIPE_PRICE_PRO_MONTHLY',     'price_pro_monthly'),
    'pro_annual':      os.getenv('STRIPE_PRICE_PRO_ANNUAL',      'price_pro_annual'),
    'agency_monthly':  os.getenv('STRIPE_PRICE_AGENCY_MONTHLY',  'price_agency_monthly'),
    'agency_annual':   os.getenv('STRIPE_PRICE_AGENCY_ANNUAL',   'price_agency_annual'),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan_rank(tier: str) -> int:
    return PLAN_RANK.get((tier or 'free').lower(), 0)


# ---------------------------------------------------------------------------
# Decorator: require minimum plan
# ---------------------------------------------------------------------------

def require_plan(minimum_plan: str):
    """
    Decorator: block users below `minimum_plan`.
    - API / JSON requests -> 403 JSON with upgrade_url
    - Browser requests   -> redirect to /billing with flash
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            user_tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
            if _plan_rank(user_tier) < _plan_rank(minimum_plan):
                logger.warning(
                    'Plan gate blocked: user=%s tier=%s path=%s requires=%s',
                    getattr(current_user, 'id', 'anon'), user_tier,
                    request.path, minimum_plan
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
                flash(f'Upgrade to {minimum_plan.title()} to unlock this feature.', 'warning')
                return redirect(url_for('billing'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# Runtime checks (no decorator needed)
# ---------------------------------------------------------------------------

def check_platform_limit(user_tier: str, requested_platforms: list) -> tuple:
    """
    Returns (allowed: bool, limit: int).
    """
    tier  = (user_tier or 'free').lower()
    limit = PLATFORM_LIMITS.get(tier, 3)
    return len(requested_platforms) <= limit, limit


def check_post_limit(user_tier: str, posts_this_month: int) -> tuple:
    """
    Returns (allowed: bool, limit: int | None).
    limit is None for unlimited plans.
    """
    tier  = (user_tier or 'free').lower()
    limit = POST_LIMITS.get(tier, 5)
    if limit is None:
        return True, None
    return posts_this_month < limit, limit


def check_location_limit(user_tier: str, location_count: int) -> tuple:
    """
    Returns (allowed: bool, limit: int).
    """
    tier  = (user_tier or 'free').lower()
    limit = LOCATION_LIMITS.get(tier, 1)
    return location_count <= limit, limit


def get_plan_limits(user_tier: str) -> dict:
    """
    Return all limits for a given tier as a dict.
    Useful for injecting into templates.
    """
    tier = (user_tier or 'free').lower()
    return {
        'tier':       tier,
        'platforms':  PLATFORM_LIMITS.get(tier, 3),
        'posts':      POST_LIMITS.get(tier, 5),
        'locations':  LOCATION_LIMITS.get(tier, 1),
        'rank':       _plan_rank(tier),
    }
