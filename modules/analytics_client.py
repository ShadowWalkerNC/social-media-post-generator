"""
PostPilot Pro — Analytics Client
Fetches post performance data from the Meta Insights API.
"""

import requests
from typing import Dict
from datetime import datetime, timedelta


class Analytics:
    BASE = 'https://graph.facebook.com/v19.0'

    def __init__(self, access_token: str, page_id: str):
        self.token   = access_token
        self.page_id = page_id

    def get_weekly_summary(self) -> Dict:
        posts   = self._get_recent_posts(limit=7)
        summary = []
        for post in posts.get('data', []):
            pid      = post.get('id')
            insights = self._get_post_insights(pid)
            summary.append({
                'post_id':      pid,
                'message':      post.get('message', '')[:80],
                'created_time': post.get('created_time'),
                'likes':        self._metric(insights, 'post_reactions_by_type_total'),
                'reach':        self._metric(insights, 'post_impressions'),
                'engaged':      self._metric(insights, 'post_engaged_users'),
            })
        best = max(summary, key=lambda x: x['reach']) if summary else {}
        return {'success': True, 'posts': summary, 'best_post': best, 'total_posts': len(summary)}

    def get_page_insights(self, days: int = 7) -> Dict:
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        until = int(datetime.now().timestamp())
        return requests.get(
            f'{self.BASE}/{self.page_id}/insights',
            params={
                'metric': 'page_impressions,page_engaged_users,page_fans',
                'since': since, 'until': until, 'access_token': self.token
            }
        ).json()

    def _get_recent_posts(self, limit: int = 7) -> Dict:
        return requests.get(
            f'{self.BASE}/{self.page_id}/posts',
            params={'limit': limit, 'fields': 'id,message,created_time', 'access_token': self.token}
        ).json()

    def _get_post_insights(self, post_id: str) -> Dict:
        return requests.get(
            f'{self.BASE}/{post_id}/insights',
            params={
                'metric': 'post_impressions,post_engaged_users,post_reactions_by_type_total',
                'access_token': self.token
            }
        ).json()

    def _metric(self, insights: Dict, name: str) -> int:
        for item in insights.get('data', []):
            if item.get('name') == name:
                values = item.get('values', [{}])
                val = values[-1].get('value', 0) if values else 0
                return val if isinstance(val, int) else sum(val.values()) if isinstance(val, dict) else 0
        return 0
