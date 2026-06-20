"""
Analytics Module
Fetches post performance from Meta Insights API
"""

import requests
from typing import Dict, List
from datetime import datetime, timedelta


class Analytics:
    BASE = "https://graph.facebook.com/v19.0"

    def __init__(self, access_token: str, page_id: str):
        self.token = access_token
        self.page_id = page_id

    def get_weekly_summary(self) -> Dict:
        """Get this week's post performance summary"""
        posts = self._get_recent_posts(limit=7)
        summary = []
        for post in posts.get('data', []):
            post_id = post.get('id')
            insights = self._get_post_insights(post_id)
            summary.append({
                'post_id': post_id,
                'message': post.get('message', '')[:80],
                'created_time': post.get('created_time'),
                'likes': self._extract_metric(insights, 'post_reactions_by_type_total'),
                'reach': self._extract_metric(insights, 'post_impressions'),
                'engaged': self._extract_metric(insights, 'post_engaged_users'),
            })
        best = max(summary, key=lambda x: x['reach']) if summary else {}
        return {'success': True, 'posts': summary, 'best_post': best, 'total_posts': len(summary)}

    def get_page_insights(self, days: int = 7) -> Dict:
        """Get page-level insights over the past N days"""
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        until = int(datetime.now().timestamp())
        res = requests.get(
            f"{self.BASE}/{self.page_id}/insights",
            params={
                'metric': 'page_impressions,page_engaged_users,page_fans',
                'since': since,
                'until': until,
                'access_token': self.token
            }
        )
        return res.json()

    def _get_recent_posts(self, limit: int = 7) -> Dict:
        res = requests.get(
            f"{self.BASE}/{self.page_id}/posts",
            params={'limit': limit, 'fields': 'id,message,created_time', 'access_token': self.token}
        )
        return res.json()

    def _get_post_insights(self, post_id: str) -> Dict:
        res = requests.get(
            f"{self.BASE}/{post_id}/insights",
            params={
                'metric': 'post_impressions,post_engaged_users,post_reactions_by_type_total',
                'access_token': self.token
            }
        )
        return res.json()

    def _extract_metric(self, insights: Dict, metric_name: str) -> int:
        for item in insights.get('data', []):
            if item.get('name') == metric_name:
                values = item.get('values', [{}])
                val = values[-1].get('value', 0) if values else 0
                return val if isinstance(val, int) else sum(val.values()) if isinstance(val, dict) else 0
        return 0
