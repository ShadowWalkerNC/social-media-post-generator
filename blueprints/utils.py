"""
blueprints/utils.py
Shared helpers used across multiple blueprints.
Import from here rather than duplicating in each blueprint.
"""

import json
from flask_login import current_user
from modules.auth_manager import load_token


def _uid() -> str:
    """
    Return the current user's ID.
    WARNING: the 'default' fallback buckets all unauthenticated callers
    under a single key. All callers must be protected by @login_required
    to prevent cross-user token leakage.
    """
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
