"""
PostPilot Pro — Post Scheduler
Schedules posts for auto-publishing at optimal times via APScheduler.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from modules.meta_client import MetaAPI

OPTIMAL_TIMES = {
    'instagram_location':   {'hour': 8,  'minute': 0},
    'instagram_menu':       {'hour': 11, 'minute': 0},
    'instagram_engagement': {'hour': 17, 'minute': 0},
    'instagram_team':       {'hour': 8,  'minute': 0},
    'facebook_giveaway':    {'hour': 11, 'minute': 0},
}

DAY_MAP = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
    'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
}


class PostScheduler:

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def schedule(self, data: Dict) -> Dict:
        try:
            publish_dt = datetime.fromisoformat(data.get('publish_time'))
            api = MetaAPI(
                access_token=data.get('access_token'),
                page_id=data.get('page_id'),
                instagram_id=data.get('instagram_id')
            )
            platform  = data.get('platform', 'instagram')
            caption   = data.get('caption', '')
            image_url = data.get('image_url')

            if platform == 'facebook':
                result = api.schedule_facebook_post(caption, publish_dt, image_url)
            else:
                result = api.schedule_instagram_post(caption, image_url, publish_dt)

            return {'success': True, 'scheduled_for': publish_dt.isoformat(), 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def bulk_schedule_week(self, posts: List[Dict], tokens: Dict, start_date: datetime = None) -> List[Dict]:
        if start_date is None:
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7 or 7
            start_date = (today + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0)

        weekly_plan = [
            ('instagram_location',   'Monday'),
            ('instagram_menu',       'Tuesday'),
            ('instagram_engagement', 'Wednesday'),
            ('instagram_team',       'Thursday'),
            ('facebook_giveaway',    'Friday'),
            ('instagram_location',   'Saturday'),
            ('instagram_engagement', 'Sunday'),
        ]

        results = []
        for post, (template, day_name) in zip(posts, weekly_plan):
            opt = OPTIMAL_TIMES[template]
            publish_dt = (start_date + timedelta(days=DAY_MAP[day_name])).replace(
                hour=opt['hour'], minute=opt['minute'])
            results.append(self.schedule({
                **tokens,
                'caption':      post.get('caption'),
                'image_url':    post.get('image_url'),
                'platform':     post.get('platform', 'instagram'),
                'publish_time': publish_dt.isoformat()
            }))
        return results

    def get_jobs(self) -> List[Dict]:
        return [{'id': j.id, 'next_run': str(j.next_run_time)} for j in self.scheduler.get_jobs()]

    def cancel_job(self, job_id: str) -> Dict:
        try:
            self.scheduler.remove_job(job_id)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
