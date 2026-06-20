"""
media_handler.py — Image & Video Auto-Resize (Phase 4 Session 4)

Auto-resizes uploaded images to platform-specific specs.
Uses Pillow for images. Stores processed versions in static/uploads/.

Platform specs:
  Instagram:  1080x1080 (square) or 1080x1350 (portrait 4:5)
  Facebook:   1200x630
  YouTube:    1280x720 (thumbnail)
  TikTok:     1080x1920 (9:16 vertical)
  Google:     1200x900
  Website:    1200x628 (banner)
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path('static/uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Platform specs: (width, height, crop_mode)
PLATFORM_SPECS = {
    'instagram_square':   (1080, 1080, 'fill'),
    'instagram_portrait': (1080, 1350, 'fill'),
    'facebook':           (1200, 630,  'fill'),
    'youtube_thumbnail':  (1280, 720,  'fill'),
    'tiktok':             (1080, 1920, 'fill'),
    'google':             (1200, 900,  'fill'),
    'website':            (1200, 628,  'fill'),
}

# Which spec to use per platform name
PLATFORM_DEFAULT_SPEC = {
    'facebook':  'facebook',
    'instagram': 'instagram_square',
    'tiktok':    'tiktok',
    'youtube':   'youtube_thumbnail',
    'google':    'google',
    'website':   'website',
}


# ---------------------------------------------------------------------------
# Core resize
# ---------------------------------------------------------------------------
def _resize_image(img, target_w: int, target_h: int, crop_mode: str = 'fill'):
    """
    Resize and optionally crop image to exact target dimensions.
    crop_mode='fill': scale to cover then center crop.
    """
    from PIL import Image

    orig_w, orig_h = img.size
    target_ratio  = target_w / target_h
    orig_ratio    = orig_w / orig_h

    if crop_mode == 'fill':
        # Scale to cover
        if orig_ratio > target_ratio:
            new_h = target_h
            new_w = int(orig_w * (target_h / orig_h))
        else:
            new_w = target_w
            new_h = int(orig_h * (target_w / orig_w))

        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - target_w) // 2
        top  = (new_h - target_h) // 2
        img  = img.crop((left, top, left + target_w, top + target_h))
    else:
        img = img.resize((target_w, target_h), Image.LANCZOS)

    return img


# ---------------------------------------------------------------------------
# Process one platform
# ---------------------------------------------------------------------------
def process_image_for_platform(source_path: str, platform: str,
                               spec_override: str = None) -> Optional[str]:
    """
    Resize image for a specific platform.

    Args:
        source_path:    Path to original uploaded image
        platform:       Platform name ('facebook', 'instagram', etc.)
        spec_override:  Optional spec key from PLATFORM_SPECS

    Returns:
        Path to processed image file, or None on failure.
    """
    try:
        from PIL import Image

        spec_key = spec_override or PLATFORM_DEFAULT_SPEC.get(platform, 'facebook')
        spec     = PLATFORM_SPECS.get(spec_key)
        if not spec:
            logger.error('Unknown platform spec: %s', spec_key)
            return None

        target_w, target_h, crop_mode = spec

        img = Image.open(source_path).convert('RGB')
        img = _resize_image(img, target_w, target_h, crop_mode)

        out_name = f'{uuid.uuid4().hex}_{platform}_{target_w}x{target_h}.jpg'
        out_path = UPLOAD_DIR / out_name
        img.save(str(out_path), 'JPEG', quality=90, optimize=True)

        logger.info('Image processed: platform=%s spec=%s output=%s', platform, spec_key, out_path)
        return str(out_path)

    except ImportError:
        logger.error('Pillow not installed — run: pip install Pillow')
        return None
    except Exception as e:
        logger.error('Image processing failed for platform=%s: %s', platform, e)
        return None


# ---------------------------------------------------------------------------
# Process for all platforms at once
# ---------------------------------------------------------------------------
def process_image_all_platforms(source_path: str) -> dict:
    """
    Resize one source image for all 6 platforms.

    Returns dict: { 'facebook': '/path/to/file.jpg', 'instagram': '...', ... }
    Missing = None.
    """
    platforms = ['facebook', 'instagram', 'tiktok', 'youtube', 'google', 'website']
    return {
        p: process_image_for_platform(source_path, p)
        for p in platforms
    }


# ---------------------------------------------------------------------------
# Validate uploaded file
# ---------------------------------------------------------------------------
def validate_upload(file_path: str) -> tuple[bool, str]:
    """
    Check if uploaded file is a valid image.
    Returns (is_valid, error_message).
    """
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    max_size_mb = 50

    path = Path(file_path)
    if not path.exists():
        return False, 'File not found'

    if path.suffix.lower() not in allowed_extensions:
        return False, f'File type not supported. Use: {', '.join(allowed_extensions)}'

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f'File too large ({size_mb:.1f}MB). Max {max_size_mb}MB.'

    try:
        from PIL import Image
        with Image.open(file_path) as img:
            img.verify()
        return True, 'OK'
    except ImportError:
        return True, 'OK (Pillow not installed — skipping verification)'
    except Exception as e:
        return False, f'Invalid image: {e}'


# ---------------------------------------------------------------------------
# Cleanup old uploads
# ---------------------------------------------------------------------------
def cleanup_uploads(max_age_hours: int = 24):
    """
    Delete processed images older than max_age_hours.
    Run periodically to keep disk clean.
    """
    import time
    cutoff = time.time() - (max_age_hours * 3600)
    deleted = 0
    for f in UPLOAD_DIR.glob('*.jpg'):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    if deleted:
        logger.info('Cleaned up %d old upload files', deleted)
    return deleted
