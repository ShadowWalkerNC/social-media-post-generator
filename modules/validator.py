"""
modules/validator.py
Input validation for post publish requests.

Call validate_post_input() before any publish route hits the publisher.
Returns (ok: bool, errors: list[str]).
"""

from urllib.parse import urlparse

# Per-platform caption character limits (enforced by each platform API)
CAPTION_LIMITS = {
    'fb':  63_206,   # Facebook
    'ig':   2_200,   # Instagram
    'yt':  5_000,    # YouTube description
    'tt':    150,    # TikTok title (script body is unlimited)
    'gb':   1_500,   # Google Business post
    'web':  5_000,   # Website banner (soft cap)
}

ALLOWED_CONTENT_TYPES = {'text', 'image', 'video', 'promo', 'update'}

# All platform keys the publisher understands
ALLOWED_PLATFORM_KEYS = {'fb', 'ig', 'yt', 'tt', 'gb', 'web',
                          'facebook', 'instagram', 'youtube',
                          'tiktok', 'google', 'website'}

# Platforms that require a media URL
IMAGE_REQUIRED  = {'ig'}
VIDEO_ONLY      = {'yt', 'tt'}


def _is_valid_url(url: str) -> bool:
    """Return True if url is an absolute http/https URL."""
    try:
        p = urlparse(url)
        return p.scheme in ('http', 'https') and bool(p.netloc)
    except Exception:
        return False


def validate_post_input(
    caption: str,
    content_type: str,
    platforms,           # list[str] or dict[str, bool]
    image_url: str = None,
    video_url: str = None,
    link_url:  str = None,
) -> tuple:
    """
    Validate a publish request.

    Returns:
        (True, [])           -- all good
        (False, [str, ...])  -- list of human-readable error strings
    """
    errors = []

    # ── 1. Caption ──────────────────────────────────────────────────────
    if not caption or not caption.strip():
        errors.append('Caption is required.')
    else:
        caption = caption.strip()
        # Check per-platform limits for every active platform
        active_keys = _normalise_platform_keys(platforms)
        for key in active_keys:
            limit = CAPTION_LIMITS.get(key)
            if limit and len(caption) > limit:
                errors.append(
                    f'Caption is too long for {key.upper()} '
                    f'({len(caption):,} chars, limit {limit:,}).'
                )

    # ── 2. content_type ─────────────────────────────────────────────────
    if not content_type:
        errors.append('content_type is required.')
    elif content_type not in ALLOWED_CONTENT_TYPES:
        errors.append(
            f'Invalid content_type "{content_type}". '
            f'Must be one of: {", ".join(sorted(ALLOWED_CONTENT_TYPES))}.'
        )

    # ── 3. Platform list / dict ──────────────────────────────────────────
    if platforms is None or platforms == [] or platforms == {}:
        errors.append('At least one platform must be selected.')
    else:
        if isinstance(platforms, list):
            bad = [p for p in platforms if p not in ALLOWED_PLATFORM_KEYS]
        elif isinstance(platforms, dict):
            bad = [p for p in platforms if p not in ALLOWED_PLATFORM_KEYS]
        else:
            bad = []
            errors.append('platforms must be a list or object.')
        if bad:
            errors.append(f'Unknown platform key(s): {", ".join(bad)}.')

    # ── 4. URL validation ────────────────────────────────────────────────
    if image_url and not _is_valid_url(image_url):
        errors.append(f'image_url is not a valid http/https URL: "{image_url}".')
    if video_url and not _is_valid_url(video_url):
        errors.append(f'video_url is not a valid http/https URL: "{video_url}".')
    if link_url and not _is_valid_url(link_url):
        errors.append(f'link_url is not a valid http/https URL: "{link_url}".')

    # ── 5. Platform / content-type compatibility ─────────────────────────
    if not errors:  # only run if basics passed
        active_keys = _normalise_platform_keys(platforms)

        # Instagram always needs a media URL
        if 'ig' in active_keys and not image_url and not video_url:
            errors.append('Instagram requires an image_url or video_url.')

        # YouTube and TikTok need a video URL
        for key in VIDEO_ONLY & active_keys:
            if not video_url:
                label = 'YouTube' if key == 'yt' else 'TikTok'
                errors.append(f'{label} requires a video_url.')

        # content_type=image should have an image_url
        if content_type == 'image' and not image_url and not video_url:
            errors.append(
                'content_type is "image" but no image_url or video_url was provided.'
            )

        # content_type=video should have a video_url
        if content_type == 'video' and not video_url:
            errors.append(
                'content_type is "video" but no video_url was provided.'
            )

    return (len(errors) == 0, errors)


def _normalise_platform_keys(platforms) -> set:
    """
    Convert a list or dict of platforms into a set of short keys
    (e.g. 'facebook' -> 'fb', 'ig' -> 'ig').
    """
    long_to_short = {
        'facebook': 'fb', 'instagram': 'ig', 'youtube': 'yt',
        'tiktok': 'tt', 'google': 'gb', 'website': 'web',
    }
    if isinstance(platforms, list):
        keys = set(platforms)
    elif isinstance(platforms, dict):
        keys = {k for k, v in platforms.items() if v}
    else:
        return set()
    return {long_to_short.get(k, k) for k in keys}
