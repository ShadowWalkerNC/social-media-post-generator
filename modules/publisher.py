"""
PostPilot Pro — Universal Publisher
Pushes one update to all connected platforms: Facebook, Instagram,
TikTok (script), Google Business, and Website banner.
"""

import requests
from typing import Dict, Optional
from modules.meta_client import MetaAPI


class UniversalPublisher:

    def __init__(self, tokens: Dict):
        self.tokens = tokens

    def push_all(self, caption: str, image_url: Optional[str], link_url: Optional[str],
                 platforms: Dict[str, bool], schedule_time: Optional[str] = None) -> Dict:
        results = {}

        if platforms.get('fb'):
            results['fb'] = self._publish_facebook(caption, image_url, schedule_time)

        if platforms.get('ig'):
            results['ig'] = self._publish_instagram(caption, image_url, schedule_time)

        if platforms.get('tt'):
            results['tt'] = self._generate_tiktok_script(caption)

        if platforms.get('gb'):
            results['gb'] = self._publish_google_business(caption, image_url, link_url)

        if platforms.get('web'):
            results['web'] = self._update_website_banner(caption, link_url)

        return results

    # ── Facebook ─────────────────────────────────────────────────────

    def _publish_facebook(self, caption: str, image_url: Optional[str],
                          schedule_time: Optional[str] = None) -> Dict:
        token   = self.tokens.get('facebook_token')
        page_id = self.tokens.get('facebook_page_id')
        if not token or not page_id:
            return {'success': False, 'error': 'Facebook not connected'}
        try:
            if image_url:
                endpoint = f'https://graph.facebook.com/v19.0/{page_id}/photos'
                params   = {'url': image_url, 'caption': caption, 'access_token': token}
            else:
                endpoint = f'https://graph.facebook.com/v19.0/{page_id}/feed'
                params   = {'message': caption, 'access_token': token}
            if schedule_time:
                from datetime import datetime
                ts = int(datetime.fromisoformat(schedule_time).timestamp())
                params.update({'published': False, 'scheduled_publish_time': ts})
            r = requests.post(endpoint, params=params)
            d = r.json()
            return {'success': r.status_code == 200, 'post_id': d.get('id'),
                    'message': 'Scheduled' if schedule_time else 'Published',
                    'error': d.get('error', {}).get('message') if r.status_code != 200 else None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Instagram ────────────────────────────────────────────────────

    def _publish_instagram(self, caption: str, image_url: Optional[str],
                           schedule_time: Optional[str] = None) -> Dict:
        token = self.tokens.get('instagram_token')
        ig_id = self.tokens.get('instagram_id')
        if not token or not ig_id:
            return {'success': False, 'error': 'Instagram not connected'}
        if not image_url:
            return {'success': False, 'error': 'Instagram requires an image URL'}
        try:
            c = requests.post(
                f'https://graph.facebook.com/v19.0/{ig_id}/media',
                params={'image_url': image_url, 'caption': caption, 'access_token': token}
            )
            if c.status_code != 200:
                return {'success': False, 'error': 'Failed to create media container'}
            p = requests.post(
                f'https://graph.facebook.com/v19.0/{ig_id}/media_publish',
                params={'creation_id': c.json().get('id'), 'access_token': token}
            )
            d = p.json()
            return {'success': p.status_code == 200, 'post_id': d.get('id'), 'message': 'Published',
                    'error': d.get('error', {}).get('message') if p.status_code != 200 else None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── TikTok (script generator — full API requires TikTok app) ─────

    def _generate_tiktok_script(self, caption: str) -> Dict:
        first   = caption.split('\n')[0]
        script  = (
            f"🎵 TIKTOK SCRIPT\n\n"
            f"[HOOK — first 3 seconds]\n\"{first}\"\n\n"
            f"[BODY]\n{caption}\n\n"
            f"[CALL TO ACTION]\n\""
            f"Follow us for daily updates — link in bio!\"\n\n"
            f"#foodtok #fyp #viral #foodie"
        )
        return {'success': True, 'message': 'Script generated', 'script': script,
                'note': 'Copy this script and record your TikTok video. Full auto-post coming in Phase 4.'}

    # ── Google Business ───────────────────────────────────────────────

    def _publish_google_business(self, caption: str, image_url: Optional[str],
                                  link_url: Optional[str]) -> Dict:
        token    = self.tokens.get('google_token')
        location = self.tokens.get('google_location_id')
        if not token or not location:
            return {'success': False, 'error': 'Google Business not connected — add GOOGLE_TOKEN to .env'}
        try:
            clean = ''.join(c for c in caption if ord(c) < 128)[:1500]
            body: Dict = {
                'languageCode': 'en',
                'summary': clean,
                'callToAction': {'actionType': 'LEARN_MORE', 'url': link_url or ''},
                'topicType': 'STANDARD'
            }
            if image_url:
                body['media'] = [{'mediaFormat': 'PHOTO', 'sourceUrl': image_url}]
            r = requests.post(
                f'https://mybusiness.googleapis.com/v4/{location}/localPosts',
                json=body,
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
            )
            d = r.json()
            return {'success': r.status_code == 200, 'post_id': d.get('name'), 'message': 'Posted to Google Business',
                    'error': d.get('error', {}).get('message') if r.status_code != 200 else None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Website Banner ────────────────────────────────────────────────

    def _update_website_banner(self, caption: str, link_url: Optional[str]) -> Dict:
        """
        Updates a hosted banner JSON file that your website reads via JS snippet.
        The website embeds: <script src='https://yourapp.com/static/banner.js'></script>
        """
        import json, os
        try:
            banner = {
                'message': caption.split('\n')[0][:120],
                'link':    link_url or '',
                'active':  True,
                'updated': __import__('datetime').datetime.now().isoformat()
            }
            path = os.path.join(os.path.dirname(__file__), '..', 'static', 'banner.json')
            with open(path, 'w') as f:
                json.dump(banner, f)
            return {'success': True, 'message': 'Website banner updated', 'banner': banner}
        except Exception as e:
            return {'success': False, 'error': str(e)}
