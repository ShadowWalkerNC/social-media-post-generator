"""
PostPilot Pro — Post Generator
Generates high-engagement posts for 5 business types using 5 proven templates.
"""

from datetime import datetime
from typing import Dict, List
import requests


class SocialMediaPostGenerator:

    def __init__(self):
        self.business_type = 'restaurant'
        self.business_name = 'My Business'
        self.location = 'Downtown'
        self.hours = '11 AM - 8 PM'
        self.city = 'My City'
        self.special_item = "Today's Special"
        self.hashtags = []
        self.facebook_token = None
        self.facebook_page_id = None
        self.instagram_token = None
        self.instagram_id = None

    def setup_business(self, info: Dict):
        self.business_type  = info.get('business_type',  self.business_type)
        self.business_name  = info.get('business_name',  self.business_name)
        self.location       = info.get('location',       self.location)
        self.hours          = info.get('hours',          self.hours)
        self.city           = info.get('city',           self.city)
        self.special_item   = info.get('special_item',   self.special_item)
        self.hashtags       = info.get('hashtags',       self.hashtags)

    def setup_api_tokens(self, tokens: Dict):
        self.facebook_token    = tokens.get('facebook_token')
        self.facebook_page_id  = tokens.get('facebook_page_id')
        self.instagram_token   = tokens.get('instagram_token')
        self.instagram_id      = tokens.get('instagram_id')

    def generate_post(self, template: str, day: str = None, date: str = None) -> Dict:
        day  = day  or datetime.now().strftime('%A')
        date = date or datetime.now().strftime('%B %d')
        dispatch = {
            'instagram_location':   self._location_post,
            'instagram_menu':       self._menu_post,
            'instagram_engagement': self._engagement_post,
            'instagram_team':       self._team_post,
            'facebook_giveaway':    self._giveaway_post,
        }
        if template not in dispatch:
            raise ValueError(f'Unknown template: {template}')
        return dispatch[template](day, date)

    def generate_weekly_schedule(self) -> List[Dict]:
        today = datetime.now()
        plan = [
            ('instagram_location',   'Monday'),
            ('instagram_menu',       'Tuesday'),
            ('instagram_engagement', 'Wednesday'),
            ('instagram_team',       'Thursday'),
            ('facebook_giveaway',    'Friday'),
            ('instagram_location',   'Saturday'),
            ('instagram_engagement', 'Sunday'),
        ]
        return [self.generate_post(t, day, today.strftime('%B %d')) for t, day in plan]

    # ─── Templates ───────────────────────────────────────────────────────────

    def _location_post(self, day, date) -> Dict:
        emojis = {'food_truck': '🍔', 'restaurant': '🍷', 'hotel': '🏨', 'cafe': '☕', 'food_company': '🍳'}
        emoji  = emojis.get(self.business_type, '📍')
        caption = (
            f"{emoji} OPEN TODAY!\n\n"
            f"🗓️ {day}, {date}\n"
            f"📍 {self.location}\n"
            f"⏰ {self.hours}\n\n"
            f"🔥 First 10 customers get a FREE item 🎁\n\n"
            f"📲 Tag us for a shoutout!\n"
            f"👇 What should we add next week?\n\n"
            f"{self._hashtags()}"
        )
        return {'platform': 'instagram', 'type': 'location', 'caption': caption,
                'post_time': '8 AM', 'image_suggestion': 'Hero product shot — close-up, natural light'}

    def _menu_post(self, day, date) -> Dict:
        caption = (
            f"🔥 NEW THIS {day.upper()}: {self.special_item}\n\n"
            f"Chef's recipe — perfected over 8 years\n"
            f"✨ Fresh local ingredients\n"
            f"✨ Made from scratch daily\n\n"
            f"📍 Available {date} only\n"
            f"💰 Free for followers — show this post!\n\n"
            f"👇 Want this on the regular menu? Reply YES\n\n"
            f"{self._hashtags()}"
        )
        return {'platform': 'instagram', 'type': 'menu', 'caption': caption,
                'post_time': '11 AM', 'image_suggestion': 'Close-up food shot — bright, warm tones'}

    def _engagement_post(self, day, date) -> Dict:
        caption = (
            f"❓ QUICK QUESTION for {day}!\n\n"
            f"What should we add next week?\n"
            f"🔘 Option A\n"
            f"🔘 Option B\n"
            f"🔘 Option C\n\n"
            f"Vote below! 👇\n\n"
            f"Find us at {self.location} today — {self.hours}\n\n"
            f"{self._hashtags()}"
        )
        return {'platform': 'instagram', 'type': 'engagement', 'caption': caption,
                'post_time': '5 PM', 'image_suggestion': 'Fun poll graphic or food flat-lay'}

    def _team_post(self, day, date) -> Dict:
        caption = (
            f"👨‍🍳 MEET OUR TEAM!\n\n"
            f"We've been proudly serving {self.city}.\n\n"
            f"❤️ Favourite dish: {self.special_item}\n"
            f"🌟 8 years of experience\n"
            f"🎉 500+ happy customers served\n\n"
            f"Thank you for your support! 🙏\n\n"
            f"Find us at {self.location} — {self.hours}\n\n"
            f"{self._hashtags()}"
        )
        return {'platform': 'instagram', 'type': 'team', 'caption': caption,
                'post_time': '8 AM', 'image_suggestion': 'Team photo — smiling, in uniform'}

    def _giveaway_post(self, day, date) -> Dict:
        caption = (
            f"🎊 GIVEAWAY ALERT! 🎊\n\n"
            f"Free {self.special_item} for 3 lucky people!\n\n"
            f"🎁 Prize: Free {self.special_item} for 2\n"
            f"💰 Value: $50 — no code needed, we'll DM the winner\n\n"
            f"HOW TO WIN:\n"
            f"1️⃣ Follow us\n"
            f"2️⃣ LIKE this post\n"
            f"3️⃣ Tag 2 friends who'd love this\n\n"
            f"🗓️ Winner announced Monday 5 PM!\n\n"
            f"{self._hashtags()}"
        )
        return {'platform': 'facebook', 'type': 'giveaway', 'caption': caption,
                'post_time': '11 AM', 'image_suggestion': 'Product or prize photo — bold colours'}

    def _hashtags(self) -> str:
        if self.hashtags:
            return ' '.join(self.hashtags)
        defaults = {
            'food_truck':   f'#{self.city.lower()}eats #foodtruck #streetfood #foodie #foodporn',
            'restaurant':   f'#{self.city.lower()}eats #finedining #restaurant #foodie #foodporn',
            'hotel':        f'#{self.city.lower()}hotel #luxurytravel #hotel #travel #vacation',
            'cafe':         f'#{self.city.lower()}cafe #coffee #cafe #foodie #coffeelover',
            'food_company': f'#{self.city.lower()}food #organicfood #foodie #cooking #homemade',
        }
        return defaults.get(self.business_type, '#food #foodie #foodporn')

    # ─── Publishing ──────────────────────────────────────────────────────────

    def publish_to_facebook(self, post: Dict, image_url: str = None) -> Dict:
        if not self.facebook_token or not self.facebook_page_id:
            return {'success': False, 'error': 'Facebook token not configured'}
        try:
            if image_url:
                endpoint = f'https://graph.facebook.com/v19.0/{self.facebook_page_id}/photos'
                params   = {'url': image_url, 'caption': post['caption'], 'access_token': self.facebook_token}
            else:
                endpoint = f'https://graph.facebook.com/v19.0/{self.facebook_page_id}/feed'
                params   = {'message': post['caption'], 'access_token': self.facebook_token}
            res  = requests.post(endpoint, params=params)
            data = res.json()
            return {'success': True, 'post_id': data.get('id')} if res.status_code == 200 \
                else {'success': False, 'error': data.get('error', {}).get('message')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def publish_to_instagram(self, post: Dict, image_url: str) -> Dict:
        if not self.instagram_token or not self.instagram_id:
            return {'success': False, 'error': 'Instagram token not configured'}
        try:
            c = requests.post(
                f'https://graph.facebook.com/v19.0/{self.instagram_id}/media',
                params={'image_url': image_url, 'caption': post['caption'], 'access_token': self.instagram_token}
            )
            if c.status_code != 200:
                return {'success': False, 'error': 'Failed to create media container'}
            p = requests.post(
                f'https://graph.facebook.com/v19.0/{self.instagram_id}/media_publish',
                params={'creation_id': c.json().get('id'), 'access_token': self.instagram_token}
            )
            data = p.json()
            return {'success': True, 'post_id': data.get('id')} if p.status_code == 200 \
                else {'success': False, 'error': data.get('error', {}).get('message')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
