"""
PostPilot Pro — Universal Publisher
Smart routing: videos → video platforms, text → text platforms,
images → image platforms. Write once, push everywhere.
"""

import json
import os
import requests
from datetime import datetime
from typing import Dict, Optional

from modules.google_client import GoogleBusinessClient, YouTubeClient
from modules.tiktok_client import TikTokClient, TikTokScriptGenerator


# Smart routing rules (mirrors frontend ROUTING constant)
ROUTING_RULES = {
    'text':   ['fb', 'gb', 'web'],
    'image':  ['fb', 'ig', 'gb', 'web'],
    'video':  ['fb', 'ig', 'yt', 'tt', 'web'],
    'promo':  ['fb', 'ig', 'tt', 'gb', 'web'],
    'update': ['fb', 'gb', 'web'],
}


class UniversalPublisher:

    def __init__(self, tokens: Dict, user_id: str = 'default'):
        self.tokens  = tokens
        self.user_id = user_id

    def push_all(
        self,
        caption:       str,
        content_type:  str = 'text',
        image_url:     Optional[str] = None,
        video_url:     Optional[str] = None,
        link_url:      Optional[str] = None,
        platforms:     Optional[Dict] = None,
        schedule_time: Optional[str] = None,
        web_data:      Optional[Dict] = None,
    ) -> Dict:

        # Auto-select platforms if not provided
        if platforms is None:
            auto      = ROUTING_RULES.get(content_type, ['fb', 'web'])
            platforms = {p: p in auto for p in ['fb', 'ig', 'yt', 'tt', 'gb', 'web']}

        # Normalise list → dict  (onboarding sends a list like ['facebook', 'website'])
        if isinstance(platforms, list):
            key_map   = {'facebook': 'fb', 'instagram': 'ig', 'youtube': 'yt',
                         'tiktok': 'tt', 'google': 'gb', 'website': 'web'}
            platforms = {key_map.get(p, p): True for p in platforms}

        results = {}

        if platforms.get('fb'):
            results['fb'] = self._publish_facebook(caption, image_url, video_url, schedule_time)

        if platforms.get('ig'):
            if image_url or video_url:
                results['ig'] = self._publish_instagram(caption, image_url or video_url, schedule_time)
            else:
                results['ig'] = {'success': False, 'error': 'Instagram requires an image or video URL'}

        if platforms.get('yt'):
            results['yt'] = self._handle_youtube(caption, video_url)

        if platforms.get('tt'):
            results['tt'] = self._handle_tiktok(caption, video_url)

        if platforms.get('gb'):
            results['gb'] = self._publish_google_business(caption, image_url, link_url)

        if platforms.get('web'):
            results['web'] = self._update_website(caption, image_url, link_url, web_data)

        return results

    # ── Facebook ───────────────────────────────────────────────────────────

    def _publish_facebook(self, caption, image_url, video_url, schedule_time=None):
        token   = self.tokens.get('facebook_token')
        page_id = self.tokens.get('facebook_page_id')
        if not token or not page_id:
            return {'success': False, 'error': 'Facebook not connected'}
        try:
            if video_url and not video_url.startswith('http'):
                return {'success': False, 'error': 'Video URL must be a public https URL'}
            if video_url:
                endpoint = f'https://graph.facebook.com/v19.0/{page_id}/videos'
                params   = {'file_url': video_url, 'description': caption, 'access_token': token}
            elif image_url:
                endpoint = f'https://graph.facebook.com/v19.0/{page_id}/photos'
                params   = {'url': image_url, 'caption': caption, 'access_token': token}
            else:
                endpoint = f'https://graph.facebook.com/v19.0/{page_id}/feed'
                params   = {'message': caption, 'access_token': token}
            if schedule_time:
                ts = int(datetime.fromisoformat(schedule_time).timestamp())
                params.update({'published': False, 'scheduled_publish_time': ts})
            r = requests.post(endpoint, params=params)
            d = r.json()
            label = 'Scheduled' if schedule_time else ('Video posted' if video_url else 'Posted')
            return {
                'success': r.status_code == 200,
                'post_id': d.get('id'),
                'message': label,
                'error':   d.get('error', {}).get('message') if r.status_code != 200 else None,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Instagram ────────────────────────────────────────────────────────

    def _publish_instagram(self, caption, media_url, schedule_time=None):
        token = self.tokens.get('instagram_token')
        ig_id = self.tokens.get('instagram_id')
        if not token or not ig_id:
            return {'success': False, 'error': 'Instagram not connected'}
        try:
            is_video = media_url and (media_url.endswith('.mp4') or 'video' in media_url)
            params   = {'caption': caption, 'access_token': token}
            if is_video:
                params['media_type'] = 'REELS'
                params['video_url']  = media_url
            else:
                params['image_url'] = media_url
            c = requests.post(f'https://graph.facebook.com/v19.0/{ig_id}/media', params=params)
            if c.status_code != 200:
                return {'success': False, 'error': 'Failed to create media container', 'detail': c.json()}
            p = requests.post(
                f'https://graph.facebook.com/v19.0/{ig_id}/media_publish',
                params={'creation_id': c.json().get('id'), 'access_token': token}
            )
            d     = p.json()
            label = 'Reel published' if is_video else 'Photo published'
            return {
                'success': p.status_code == 200,
                'post_id': d.get('id'),
                'message': label,
                'error':   d.get('error', {}).get('message') if p.status_code != 200 else None,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── YouTube — delegates to YouTubeClient ───────────────────────────────

    def _handle_youtube(self, caption, video_url):
        yt_token = self.tokens.get('youtube_token')

        # Script-only fallback — no token or no video
        if not yt_token or not video_url:
            return {
                'success': True,
                'message': 'YouTube description ready — connect YouTube in Settings to auto-upload',
                'description': caption,
                'video_url':   video_url or 'No video URL provided',
                'note':        'Full YouTube auto-upload requires YouTube Data API v3 OAuth',
            }

        # Full upload via YouTubeClient (handles temp-file download + multipart)
        try:
            client = YouTubeClient(user_id=self.user_id)
            title  = caption.split('\n')[0][:100]
            result = client.upload_video(
                title       = title,
                description = caption,
                video_url   = video_url,
                tags        = ['food', 'local', 'update'],
                privacy     = 'public',
            )
            if result.get('id'):
                return {
                    'success':  True,
                    'message':  'YouTube video uploaded',
                    'video_id': result['id'],
                }
            return {'success': False, 'error': result.get('error', 'Upload failed'), 'raw': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── TikTok — delegates to TikTokClient / TikTokScriptGenerator ──────────

    def _handle_tiktok(self, caption, video_url=None):
        tt_token = self.tokens.get('tiktok_token')

        # Script-only fallback — no token or pending app approval
        if not tt_token:
            script = TikTokScriptGenerator.generate(caption)
            return {
                'success': True,
                'message': 'TikTok script ready — connect TikTok to auto-upload videos',
                'script':  script['full_script'],
            }

        # Token present but no video — return script so dashboard can display it
        if not video_url:
            script = TikTokScriptGenerator.generate(caption)
            return {
                'success': True,
                'message': 'TikTok script ready (no video URL provided for auto-upload)',
                'script':  script['full_script'],
            }

        # Full upload via TikTokClient (PULL_FROM_URL)
        try:
            client = TikTokClient(user_id=self.user_id)
            title  = caption.split('\n')[0][:150]
            result = client.upload_video(title=title, video_url=video_url)
            if result.get('publish_id'):
                return {
                    'success':    True,
                    'message':    'TikTok video upload initiated',
                    'publish_id': result['publish_id'],
                    'note':       'Use get_video_status(publish_id) to confirm PUBLISH_COMPLETE',
                }
            return {'success': False, 'error': result.get('error', 'Upload failed'), 'raw': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Google Business — delegates to GoogleBusinessClient ────────────────

    def _publish_google_business(self, caption, image_url=None, link_url=None):
        token    = self.tokens.get('google_token')
        location = self.tokens.get('google_location_id')
        if not token or not location:
            return {'success': False, 'error': 'Google Business not connected'}
        try:
            client = GoogleBusinessClient(
                location_id = location,
                user_id     = self.user_id,
            )
            result = client.create_post(
                text           = caption,
                image_url      = image_url,
                call_to_action = 'LEARN_MORE' if link_url else None,
                cta_url        = link_url,
            )
            if result.get('name'):
                return {
                    'success': True,
                    'post_id': result['name'],
                    'message': 'Posted to Google Business',
                }
            return {
                'success': False,
                'error':   result.get('error', {}).get('message', 'Unknown error'),
                'raw':     result,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Website (banner + sections) ──────────────────────────────────────

    def _update_website(self, caption, image_url=None, link_url=None, web_data=None):
        try:
            data = {
                'message':  caption.split('\n')[0][:120],
                'full':     caption,
                'image':    image_url or '',
                'link':     link_url  or '',
                'active':   True,
                'updated':  datetime.now().isoformat(),
                'specials': (web_data or {}).get('specials', ''),
                'hours':    (web_data or {}).get('hours',    ''),
                'location': (web_data or {}).get('location', ''),
            }
            path = os.path.join(os.path.dirname(__file__), '..', 'static', 'banner.json')
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            return {'success': True, 'message': 'Website banner + sections updated', 'data': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}
