"""
blueprints/website.py
Website hub: save, publish toggle, domain verify, public site renderer.
"""

from markupsafe import escape
from flask import (
    Blueprint, render_template, request, jsonify, current_app
)
from flask_login import login_required, current_user

from modules.website_manager import WebsiteManager
from blueprints.utils        import _business_name

website_bp = Blueprint('website', __name__)


@website_bp.route('/website_hub')
@website_bp.route('/website')
@login_required
def website_hub():
    wm   = WebsiteManager(user_id=current_user.id)
    site = wm.get_site()
    return render_template('website_hub.html', site=site, business_name=_business_name())


@website_bp.route('/website/save', methods=['POST'])
@login_required
def website_save():
    wm      = WebsiteManager(user_id=current_user.id)
    payload = request.get_json(silent=True) or {}
    return jsonify(wm.save_site(payload))


@website_bp.route('/website/publish', methods=['POST'])
@login_required
def website_publish():
    wm        = WebsiteManager(user_id=current_user.id)
    data      = request.get_json(silent=True) or {}
    published = bool(data.get('published', False))
    return jsonify(wm.set_published(published))


@website_bp.route('/website/verify_domain', methods=['POST'])
@login_required
def website_verify_domain():
    wm     = WebsiteManager(user_id=current_user.id)
    data   = request.get_json(silent=True) or {}
    domain = data.get('domain', '').strip()
    if not domain:
        return jsonify({'success': False, 'error': 'domain required'})
    return jsonify(wm.verify_domain(domain))


@website_bp.route('/site/preview')
@login_required
def site_preview():
    wm   = WebsiteManager(user_id=current_user.id)
    site = wm.get_site()
    return _render_public_site(site, preview=True)


@website_bp.route('/site/<user_id>')
def site_public(user_id: str):
    wm   = WebsiteManager(user_id=user_id)
    site = wm.get_site()
    if not site.get('published'):
        return render_template('404.html'), 404
    return _render_public_site(site, preview=False)


def _render_public_site(site: dict, preview: bool = False):
    sections    = site.get('sections') or WebsiteManager.DEFAULT_SECTIONS
    active_secs = [s for s in sections if s.get('enabled')]
    seo         = site.get('seo') or {}
    socials     = site.get('socials') or {}
    theme       = site.get('theme', 'modern')
    color       = site.get('primary_color', '#6366f1')
    try:
        return render_template(
            'public_site.html',
            site=site, sections=active_secs, seo=seo, socials=socials,
            theme=theme, primary_color=color, preview=preview,
        )
    except Exception:
        current_app.logger.exception('public_site.html render failed, using raw HTML fallback')
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
            + ("<div style='background:#fbbf24;color:#000;text-align:center;padding:.5rem;font-size:.8rem'>PREVIEW MODE</div>" if preview else '')
            + f'<h1>{title}</h1>{sec_html}</body></html>'
        ), 200
