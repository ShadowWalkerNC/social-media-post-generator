"""
PostPilot Pro — Meta API Client
Handles all Facebook and Instagram Graph API interactions.
"""

import requests
from datetime import datetime
from typing import Dict, Optional


class MetaAPI:
    BASE = 'https://graph.facebook.com/v19.0'

    def __init__(self, access_token: str, page_id: str, instagram_id: Optional[str] = None):
        self.token   = access_token
        self.page_id = page_id
        self.ig_id   = instagram_id

    def post_to_facebook(self, message: str, image_url: str = None) -> Dict:
        if image_url:
            endpoint = f'{self.BASE}/{self.page_id}/photos'
            params   = {'url': image_url, 'caption': message, 'access_token': self.token}
        else:
            endpoint = f'{self.BASE}/{self.page_id}/feed'
            params   = {'message': message, 'access_token': self.token}
        return requests.post(endpoint, params=params).json()

    def schedule_facebook_post(self, message: str, publish_time: datetime, image_url: str = None) -> Dict:
        return requests.post(
            f'{self.BASE}/{self.page_id}/feed',
            params={
                'message': message,
                'published': False,
                'scheduled_publish_time': int(publish_time.timestamp()),
                'access_token': self.token
            }
        ).json()

    def post_to_instagram(self, caption: str, image_url: str) -> Dict:
        if not self.ig_id:
            return {'error': 'Instagram ID not configured'}
        container = requests.post(
            f'{self.BASE}/{self.ig_id}/media',
            params={'image_url': image_url, 'caption': caption, 'access_token': self.token}
        ).json()
        creation_id = container.get('id')
        if not creation_id:
            return {'error': 'Failed to create media container', 'details': container}
        return requests.post(
            f'{self.BASE}/{self.ig_id}/media_publish',
            params={'creation_id': creation_id, 'access_token': self.token}
        ).json()

    def schedule_instagram_post(self, caption: str, image_url: str, publish_time: datetime) -> Dict:
        if not self.ig_id:
            return {'error': 'Instagram ID not configured'}
        container = requests.post(
            f'{self.BASE}/{self.ig_id}/media',
            params={
                'image_url': image_url, 'caption': caption,
                'scheduled_publish_time': int(publish_time.timestamp()),
                'media_type': 'IMAGE', 'access_token': self.token
            }
        ).json()
        creation_id = container.get('id')
        if not creation_id:
            return {'error': 'Failed to create scheduled container', 'details': container}
        return requests.post(
            f'{self.BASE}/{self.ig_id}/media_publish',
            params={'creation_id': creation_id, 'access_token': self.token}
        ).json()

    def get_page_posts(self, limit: int = 10) -> Dict:
        return requests.get(
            f'{self.BASE}/{self.page_id}/posts',
            params={'limit': limit, 'access_token': self.token}
        ).json()

    def get_post_insights(self, post_id: str) -> Dict:
        return requests.get(
            f'{self.BASE}/{post_id}/insights',
            params={
                'metric': 'post_impressions,post_engaged_users,post_reactions_by_type_total',
                'access_token': self.token
            }
        ).json()
