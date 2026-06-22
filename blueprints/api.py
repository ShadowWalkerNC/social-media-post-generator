"""
blueprints/api.py
All /api/* endpoints: publish, generate, schedule, history,
analytics, business profile, connection status, token setup.
"""

import json

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from modules.post_generator   import SocialMediaPostGenerator
from modules.post_scheduler    import PostScheduler
from modules.analytics_client  import Analytics
from modules.publisher         import UniversalPublisher
from modules.user_manager      import UserManager
from modules.auth_manager      import save_token
from modules.plan_guard        import require_plan, check_platform_limit
from blueprints.utils          import _uid, _get_tokens

api_bp = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _enforce_platform_limit(tier, platforms):
    """Returns (ok, error_response_or_None)."""
    if not platforms:
        return True, None
    allowed, limit = check_platform_limit(tier, platforms)
    if not allowed:
        return False, (jsonify({
            'success': False,
            'error': f'Your plan allows up to {limit} platform(s) at once. Upgrade at /billing.'
        }), 403)
    return True, None


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

@api_bp.route('/api/push_all', methods=['POST'])
@login_required
@require_plan('starter')
def api_push_all():
    data      = request.json or {}
    uid       = _uid()
    platforms = data.get('platforms') or []
    ok, err   = _enforce_platform_limit(current_user.subscription_tier, platforms)
    if not ok:
        return err
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


@api_bp.route('/api/publish', methods=['POST'])
@api_bp.route('/api/publish_post', methods=['POST'])
@login_required
@require_plan('starter')
def api_publish():
    data      = request.json or {}
    uid       = _uid()
    platforms = data.get('platforms') or []
    ok, err   = _enforce_platform_limit(current_user.subscription_tier, platforms)
    if not ok:
        return err
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


# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------

@api_bp.route('/api/connection_status', methods=['GET', 'POST'])
@login_required
def api_connection_status():
    tokens = _get_tokens(_uid())
    status = {
        'fb':  bool(tokens.get('facebook_token') and tokens.get('facebook_page_id')),
        'ig':  bool(tokens.get('instagram_token') and tokens.get('instagram_id')),
        'yt':  bool(tokens.get('youtube_token')),
        'tt':  bool(tokens.get('tiktok_token')),
        'gb':  bool(tokens.get('google_token')),
        'web': True,
    }
    return jsonify({'success': True, 'platforms': status, 'connections': status})


# ---------------------------------------------------------------------------
# Business profile
# ---------------------------------------------------------------------------

@api_bp.route('/api/setup_business', methods=['POST'])
@login_required
def api_setup_business():
    data = request.json or {}
    uid  = _uid()
    info = data.get('business_info', {})
    gen  = SocialMediaPostGenerator()
    gen.setup_business(info)
    UserManager.save_business_profile(uid, info)
    return jsonify({'success': True})


@api_bp.route('/api/get_business', methods=['GET'])
@login_required
def api_get_business():
    profile = getattr(current_user, 'business_profile', None)
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}
    return jsonify({'success': True, 'business_info': profile or {}})


@api_bp.route('/api/onboarding/setup', methods=['POST'])
@login_required
def api_onboarding_setup():
    data = request.json or {}
    business_info = {
        'name':          data.get('name', ''),
        'business_type': data.get('type', ''),
        'location':      data.get('location', ''),
        'hours':         data.get('hours', ''),
        'prompt_time':   data.get('prompt_time', '07:00'),
    }
    UserManager.save_business_profile(_uid(), business_info)
    return jsonify({'success': True, 'business': business_info})


# ---------------------------------------------------------------------------
# Token setup (manual / power-user)
# ---------------------------------------------------------------------------

@api_bp.route('/api/setup_tokens', methods=['POST'])
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


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

@api_bp.route('/api/generate_weekly', methods=['POST'])
@api_bp.route('/api/generate_posts', methods=['POST'])
@login_required
@require_plan('starter')
def api_generate_weekly():
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
    posts    = schedule if isinstance(schedule, list) else schedule.get('posts', [])
    return jsonify({'success': True, 'posts': posts, 'schedule': schedule})


@api_bp.route('/api/generate_post', methods=['POST'])
@api_bp.route('/api/generate_single', methods=['POST'])
@login_required
@require_plan('starter')
def api_generate_post():
    data     = request.json or {}
    template = data.get('template', 'instagram_location')
    gen      = SocialMediaPostGenerator()
    try:
        post = gen.generate_post(template)
        return jsonify({'success': True, 'post': post})
    except Exception:
        current_app.logger.exception('generate_post failed for template %s', template)
        return jsonify({'success': False, 'error': 'Post generation failed'})


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

@api_bp.route('/api/schedule_post', methods=['POST'])
@login_required
@require_plan('starter')
def api_schedule_post():
    return jsonify(PostScheduler().schedule(request.json))


@api_bp.route('/api/scheduled_posts', methods=['GET'])
@login_required
def api_scheduled_posts():
    from app import get_db
    uid = _uid()
    db  = get_db()
    try:
        rows = db.execute(
            'SELECT * FROM post_history WHERE user_id = ? AND status = "scheduled" '
            'ORDER BY scheduled_at ASC', (uid,)
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
        current_app.logger.exception('api_scheduled_posts failed for user %s', uid)
        posts = []
    return jsonify({'success': True, 'posts': posts})


@api_bp.route('/api/post_history', methods=['GET'])
@login_required
def api_post_history():
    from app import get_db
    uid = _uid()
    db  = get_db()
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
    except (ValueError, TypeError):
        limit = 20
    try:
        rows = db.execute(
            'SELECT * FROM post_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
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
    except Exception:
        current_app.logger.exception('api_post_history failed for user %s', uid)
        return jsonify({'success': False, 'error': 'Could not load history', 'posts': []})
    return jsonify({'success': True, 'posts': posts, 'count': len(posts)})


@api_bp.route('/api/bulk_schedule', methods=['POST'])
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


@api_bp.route('/api/delete_post', methods=['POST'])
@login_required
def api_delete_post():
    from app import get_db
    data    = request.json or {}
    post_id = data.get('post_id')
    uid     = _uid()
    if post_id:
        db = get_db()
        try:
            db.execute('DELETE FROM post_history WHERE id = ? AND user_id = ?', (post_id, uid))
            db.commit()
        except Exception:
            current_app.logger.exception('api_delete_post failed for post %s user %s', post_id, uid)
            return jsonify({'success': False, 'error': 'Delete failed'})
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@api_bp.route('/api/analytics', methods=['POST'])
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
