"""
location_service.py — One-Tap Location Post (Phase 4 Session 5)

The single biggest daily action for food trucks.
GPS pull or manual pin drop → auto-writes location post → pushes to all platforms.

No other tool does this specifically for food trucks.
"""

import os
import json
import logging
import requests
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BANNER_PATH = Path('static/banner.json')


# ---------------------------------------------------------------------------
# Geocoding helpers
# ---------------------------------------------------------------------------
def reverse_geocode(lat: float, lng: float) -> dict:
    """
    Convert coordinates to human-readable address.
    Uses OpenStreetMap Nominatim (free, no key required).

    Returns: { address, city, neighborhood, display_name }
    """
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lng, 'format': 'json'},
            headers={'User-Agent': 'PostPilotPro/1.0'},
            timeout=5,
        )
        if resp.status_code != 200:
            return {'address': f'{lat:.4f}, {lng:.4f}', 'display_name': 'Current Location'}

        data    = resp.json()
        addr    = data.get('address', {})
        parts   = []
        for key in ['road', 'neighbourhood', 'suburb', 'city', 'town', 'village']:
            val = addr.get(key)
            if val:
                parts.append(val)
                if len(parts) == 2:
                    break

        display = ', '.join(parts) if parts else data.get('display_name', 'Current Location')
        return {
            'address':      data.get('display_name', ''),
            'city':         addr.get('city') or addr.get('town') or addr.get('village', ''),
            'neighborhood': addr.get('neighbourhood') or addr.get('suburb', ''),
            'display_name': display,
            'lat':          lat,
            'lng':          lng,
        }
    except Exception as e:
        logger.error('Reverse geocode failed: %s', e)
        return {'address': '', 'display_name': f'{lat:.4f}, {lng:.4f}', 'lat': lat, 'lng': lng}


# ---------------------------------------------------------------------------
# Location post caption builder
# ---------------------------------------------------------------------------
LOCATION_TEMPLATES = {
    'facebook': (
        '📍 We're at {location} today!\n'
        '{special_line}'
        'Open until {hours}. Come find us! 🚚'
    ),
    'instagram': (
        '📍 FIND US TODAY\n\n'
        'We're set up at {location} and ready to serve!\n'
        '{special_line}'
        '⏰ Open until {hours}\n\n'
        'Tag a friend who needs to eat! 👇\n\n'
        '#{hashtag} #foodtruck #localeats #streetfood'
    ),
    'tiktok': (
        'We're at {location} right now 📍 Open until {hours}! '
        '{special_short} #{hashtag} #foodtruck #findus'
    ),
    'google': (
        'We are at {location} today, open until {hours}. '
        '{special_line_plain}'
        'Come visit us!'
    ),
    'website': '📍 Today: {location} | Open until {hours}',
    'youtube': (
        'We're parked at {location} today until {hours}! '
        '{special_line_plain}'
        'Here's everything you need to know to find us.'
    ),
}


def build_location_captions(business_info: dict, location_data: dict) -> dict:
    """
    Build location post captions for all platforms.

    Args:
        business_info:  { name, hours, special, type }
        location_data:  { display_name, lat, lng } from reverse_geocode or manual input

    Returns:
        dict of { platform: caption_string }
    """
    name     = business_info.get('name', 'Us')
    hours    = business_info.get('hours', 'closing time')
    special  = business_info.get('special', '')
    hashtag  = name.lower().replace(' ', '')
    location = location_data.get('display_name', 'our location')

    special_line       = f'Today\'s special: {special}\n' if special else ''
    special_line_plain = f'Today\'s special: {special}. ' if special else ''
    special_short      = f'Today: {special}!' if special else ''

    captions = {}
    for platform, template in LOCATION_TEMPLATES.items():
        captions[platform] = template.format(
            location=location,
            hours=hours,
            special_line=special_line,
            special_line_plain=special_line_plain,
            special_short=special_short,
            hashtag=hashtag,
            name=name,
        )

    return captions


# ---------------------------------------------------------------------------
# Update banner.json with live location
# ---------------------------------------------------------------------------
def update_website_location(location_data: dict, business_info: dict):
    """
    Write current location + hours to banner.json so the website widget updates live.
    """
    try:
        banner = {}
        if BANNER_PATH.exists():
            with open(BANNER_PATH) as f:
                banner = json.load(f)

        banner['location'] = {
            'text':    location_data.get('display_name', ''),
            'lat':     location_data.get('lat'),
            'lng':     location_data.get('lng'),
            'updated': datetime.utcnow().isoformat(),
        }
        banner['hours'] = {
            'text':    business_info.get('hours', ''),
            'updated': datetime.utcnow().isoformat(),
        }

        with open(BANNER_PATH, 'w') as f:
            json.dump(banner, f, indent=2)

        logger.info('Website location updated: %s', location_data.get('display_name'))
        return True
    except Exception as e:
        logger.error('Failed to update website location: %s', e)
        return False


# ---------------------------------------------------------------------------
# One-tap post — the main entry point
# ---------------------------------------------------------------------------
def one_tap_location_post(business_info: dict, location_input: dict) -> dict:
    """
    The one-tap location post workflow:
    1. Resolve location (GPS coords or manual address string)
    2. Build captions for all platforms
    3. Update website banner.json
    4. Return payload ready for publisher.py

    Args:
        business_info:  { name, hours, special, type }
        location_input: { lat, lng } OR { address: 'manual text' }

    Returns:
        {
            'captions':  { platform: caption },
            'location':  resolved location dict,
            'ready':     True/False,
            'error':     None or error string,
        }
    """
    # Resolve location
    if 'lat' in location_input and 'lng' in location_input:
        location_data = reverse_geocode(location_input['lat'], location_input['lng'])
    elif 'address' in location_input:
        location_data = {
            'display_name': location_input['address'],
            'address':      location_input['address'],
            'lat':          None,
            'lng':          None,
        }
    else:
        return {'ready': False, 'error': 'location_input must have lat/lng or address'}

    # Build captions
    captions = build_location_captions(business_info, location_data)

    # Update website
    update_website_location(location_data, business_info)

    logger.info('One-tap location post ready: %s', location_data.get('display_name'))

    return {
        'captions':  captions,
        'location':  location_data,
        'ready':     True,
        'error':     None,
        'content_type': 'location',
        'timestamp': datetime.utcnow().isoformat(),
    }
