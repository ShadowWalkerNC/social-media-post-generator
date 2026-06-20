"""
ai_generator.py — AI Caption Generation (Phase 4 Session 3)

Generates platform-optimized captions using:
  - OpenAI GPT-4o-mini (primary, $0.002/caption)
  - Template fallback (no API key required)

Each platform gets a different caption style automatically.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Tone system prompts
TONE_PROMPTS = {
    'hype':      'You write energetic, hype social media captions with lots of excitement and urgency. Use fire/rocket emojis sparingly.',
    'friendly':  'You write warm, conversational social media captions. Friendly and approachable, like a neighbor.',
    'urgent':    'You write urgent, time-sensitive social media captions. Create FOMO. Limited time. Act now.',
    'funny':     'You write witty, humorous social media captions. Light puns welcome. Keep it fun and shareable.',
    'community': 'You write community-focused social media captions. Emphasize connection, local love, and belonging.',
}

# Per-platform style instructions
PLATFORM_STYLES = {
    'facebook': (
        'Facebook post: 1-3 sentences. Conversational tone. '
        'Can include a question to drive comments. 1-2 relevant hashtags max.'
    ),
    'instagram': (
        'Instagram caption: Hook in first line (cuts off at ~125 chars). '
        'Expand below the fold. End with 5-10 relevant hashtags on a new line. '
        'Emojis welcome throughout.'
    ),
    'tiktok': (
        'TikTok video title/description: Short punchy hook under 150 chars. '
        'Extremely casual, trending language. 3-5 hashtags including niche ones.'
    ),
    'youtube': (
        'YouTube video description: First 2-3 sentences are the hook (shown before More). '
        'Mention what viewers will see/get. Include location and business name naturally.'
    ),
    'google': (
        'Google Business post: Professional but warm. 1-2 sentences. '
        'No hashtags (Google ignores them). ASCII-safe characters only (no special emojis). '
        'Max 1500 characters. Include a clear call to action.'
    ),
    'website': (
        'Website banner message: Ultra-short. 1 punchy sentence or less. '
        'No hashtags. Just the key info + action. Max 120 characters.'
    ),
}


# ---------------------------------------------------------------------------
# Primary: OpenAI GPT-4o-mini
# ---------------------------------------------------------------------------
def _generate_openai(business_info: dict, content_type: str, tone: str,
                     keywords: list, platform: str) -> Optional[str]:
    """Call OpenAI API to generate a caption. Returns None on failure."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        business_name = business_info.get('name', 'our business')
        business_type = business_info.get('type', 'food business')
        location      = business_info.get('location', '')
        special       = business_info.get('special', '')

        tone_instruction = TONE_PROMPTS.get(tone, TONE_PROMPTS['friendly'])
        platform_style   = PLATFORM_STYLES.get(platform, '')

        system_msg = (
            f'{tone_instruction}\n\n'
            f'You are writing for: {business_name}, a {business_type}.'
            + (f' Located at: {location}.' if location else '')
            + f'\n\nPlatform rules: {platform_style}'
        )

        user_msg = (
            f'Write a {content_type} post.'
            + (f' Today\'s special: {special}.' if special else '')
            + (f' Keywords to include: {', '.join(keywords)}.' if keywords else '')
            + ' Return only the caption text, nothing else.'
        )

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_msg},
                {'role': 'user',   'content': user_msg},
            ],
            max_tokens=300,
            temperature=0.8,
        )

        caption = response.choices[0].message.content.strip()
        logger.info('OpenAI caption generated for platform=%s tone=%s', platform, tone)
        return caption

    except Exception as e:
        logger.error('OpenAI generation failed: %s', e)
        return None


# ---------------------------------------------------------------------------
# Fallback: Template-based generation
# ---------------------------------------------------------------------------
TEMPLATES = {
    'daily_special': {
        'facebook':  "🍽️ Today's special at {name}: {special}! Come in and try it — you won't be disappointed. {location_tag}",
        'instagram': "✨ TODAY'S SPECIAL ✨\n\n{special} — made fresh and ready for you at {name}.\n\nCome find us {location_tag} and treat yourself! 🙌\n\n#{hashtag1} #{hashtag2} #foodie #localfood #dailyspecial",
        'tiktok':    "{special} just dropped at {name} 🔥 Don't miss it #{hashtag1} #foodtruck #todaysspecial",
        'google':    "Today's special: {special}. Visit {name} at {location} to enjoy it today.",
        'website':   "Today's Special: {special} — available now!",
        'youtube':   "Today at {name} we're serving up {special}. Come find us at {location} — here's everything you need to know!",
    },
    'location': {
        'facebook':  "📍 We're set up at {location} today! Come find us — open until {hours}. {name} is ready for you!",
        'instagram': "📍 FIND US TODAY\n\nWe're at {location} and ready to serve!\nOpen until {hours}.\n\nTag a friend who needs to know 👇\n\n#{hashtag1} #foodtruck #localeats #{hashtag2}",
        'tiktok':    "We're at {location} right now 📍 Open until {hours}! #{hashtag1} #foodtruck",
        'google':    "We are at {location} today, open until {hours}. Come visit {name}!",
        'website':   "📍 Today's Location: {location} | Open until {hours}",
        'youtube':   "We're parked at {location} today until {hours}! Here's how to find us at {name}.",
    },
    'general': {
        'facebook':  "Come visit {name}! We'd love to see you. {location_tag}",
        'instagram': "Fresh eats. Good vibes. {name} 🙌\n\n#{hashtag1} #{hashtag2} #localfood #supportlocal",
        'tiktok':    "{name} bringing the good stuff 🔥 #{hashtag1} #foodie",
        'google':    "Visit {name} for great food and friendly service. We look forward to seeing you!",
        'website':   "Welcome to {name} — great food, great vibes.",
        'youtube':   "Welcome to {name}! Here's what we've been up to lately.",
    },
}


def _generate_template(business_info: dict, content_type: str, platform: str) -> str:
    """Generate caption from template. Always returns something."""
    name     = business_info.get('name', 'Our Business')
    location = business_info.get('location', 'our location')
    hours    = business_info.get('hours', 'closing time')
    special  = business_info.get('special', 'our daily special')
    biz_type = business_info.get('type', 'food').lower().replace(' ', '')

    hashtag1 = name.lower().replace(' ', '')
    hashtag2 = biz_type if biz_type else 'foodtruck'
    location_tag = f'at {location}' if location else ''

    template_group = TEMPLATES.get(content_type, TEMPLATES['general'])
    template       = template_group.get(platform, template_group.get('facebook', ''))

    return template.format(
        name=name,
        location=location,
        hours=hours,
        special=special,
        hashtag1=hashtag1,
        hashtag2=hashtag2,
        location_tag=location_tag,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_caption(business_info: dict,
                     content_type: str = 'general',
                     tone: str = 'friendly',
                     keywords: list = None,
                     platform: str = 'facebook') -> str:
    """
    Generate a platform-optimized caption.

    Args:
        business_info: dict with keys: name, type, location, hours, special
        content_type:  'daily_special' | 'location' | 'general'
        tone:          'hype' | 'friendly' | 'urgent' | 'funny' | 'community'
        keywords:      extra words to weave into the caption
        platform:      'facebook' | 'instagram' | 'tiktok' | 'youtube' | 'google' | 'website'

    Returns:
        Caption string, always.
    """
    keywords = keywords or []

    # Try OpenAI first
    caption = _generate_openai(business_info, content_type, tone, keywords, platform)

    # Fall back to template
    if not caption:
        logger.info('Using template fallback for platform=%s', platform)
        caption = _generate_template(business_info, content_type, platform)

    return caption


def generate_all_platforms(business_info: dict,
                           content_type: str = 'general',
                           tone: str = 'friendly',
                           keywords: list = None) -> dict:
    """
    Generate captions for all 6 platforms in one call.

    Returns dict: { 'facebook': '...', 'instagram': '...', ... }
    """
    platforms = ['facebook', 'instagram', 'tiktok', 'youtube', 'google', 'website']
    return {
        p: generate_caption(business_info, content_type, tone, keywords, p)
        for p in platforms
    }
