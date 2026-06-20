"""
Post Scheduler Module
Schedules posts for auto-publishing at optimal times
"""

from datetime import datetime, timedelta
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from modules.meta_api import MetaAPI


# Optimal post times per platform (based on engagement research)
OPTIMAL_TIMES = {
    'instagram_location':   {'hour': 8,  'minute': 0},
    'instagram_menu':       {'hour': 11, 'minute': 0},
    'instagram_engagement': {'hour': 17, 'minute': 0},
    'instagram_team':       {'hour': 8,  'minute': 0},
    'facebook_giveaway':    {'hour': 11, 'minute': 0},
}

# Day of week map
DAY_MAP = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
    'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
}


class PostScheduler:

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.scheduled_jobs = []

    def schedule(self, data: Dict) -> Dict:
        """Schedule a single post"""
        try:
            publish_dt = datetime.fromisoformat(data.get('publish_time'))
            api = MetaAPI(
                access_token=data.get('access_token'),
                page_id=data.get('page_id'),
                instagram_id=data.get('instagram_id')
            )
            platform = data.get('platform', 'instagram')
            caption = data.get('caption', '')
            image_url = data.get('image_url')

            if platform == 'facebook':
                result = api.schedule_facebook_post(caption, publish_dt, image_url)
            else:
                result = api.schedule_instagram_post(caption, image_url, publish_dt)

            return {'success': True, 'scheduled_for': publish_dt.isoformat(), 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def bulk_schedule_week(self, posts: List[Dict], tokens: Dict, start_date: datetime = None) -> List[Dict]:
        """Schedule a full week of posts starting from start_date (defaults to next Monday)"""
        if start_date is None:
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7 or 7
            start_date = today + timedelta(days=days_until_monday)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        results = []
        weekly_plan = [
            ('instagram_location',   'Monday'),
            ('instagram_menu',       'Tuesday'),
            ('instagram_engagement', 'Wednesday'),
            ('instagram_team',       'Thursday'),
            ('facebook_giveaway',    'Friday'),
            ('instagram_location',   'Saturday'),
            ('instagram_engagement', 'Sunday'),
        ]

        for post, (template, day_name) in zip(posts, weekly_plan):
            day_offset = DAY_MAP[day_name]
            optimal = OPTIMAL_TIMES[template]
            publish_dt = start_date + timedelta(days=day_offset)
            publish_dt = publish_dt.replace(hour=optimal['hour'], minute=optimal['minute'])

            schedule_data = {
                **tokens,
                'caption': post.get('caption'),
                'image_url': post.get('image_url'),
                'platform': post.get('platform', 'instagram'),
                'publish_time': publish_dt.isoformat()
            }
            results.append(self.schedule(schedule_data))

        return results

    def get_scheduled_jobs(self) -> List[Dict]:
        """Return list of all scheduled jobs"""
        return [{'id': job.id, 'next_run': str(job.next_run_time)} for job in self.scheduler.get_jobs()]

    def cancel_job(self, job_id: str) -> Dict:
        """Cancel a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
