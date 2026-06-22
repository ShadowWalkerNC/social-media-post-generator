"""
tests/test_validator.py
Unit tests for modules/validator.py -- validate_post_input().

All tests are pure unit tests; no Flask app context needed.
"""

import pytest
from modules.validator import validate_post_input


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOOD = dict(
    caption      = 'Great lunch special today!',
    content_type = 'text',
    platforms    = ['fb'],
    image_url    = None,
    video_url    = None,
    link_url     = None,
)


def valid(**overrides):
    """Return a valid base payload with optional field overrides."""
    return {**GOOD, **overrides}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:

    def test_minimal_text_post_passes(self):
        ok, errors = validate_post_input(**valid())
        assert ok is True
        assert errors == []

    def test_image_post_with_url_passes(self):
        ok, errors = validate_post_input(**valid(
            content_type='image',
            platforms=['fb', 'ig'],
            image_url='https://example.com/photo.jpg',
        ))
        assert ok is True

    def test_video_post_with_url_passes(self):
        ok, errors = validate_post_input(**valid(
            content_type='video',
            platforms=['fb', 'yt'],
            video_url='https://example.com/video.mp4',
        ))
        assert ok is True

    def test_long_name_platforms_accepted(self):
        """Publisher accepts both short ('fb') and long ('facebook') platform keys."""
        ok, errors = validate_post_input(**valid(platforms=['facebook', 'instagram'],
                                                  image_url='https://example.com/img.jpg'))
        assert ok is True

    def test_dict_platforms_accepted(self):
        ok, errors = validate_post_input(**valid(platforms={'fb': True, 'ig': False}))
        assert ok is True


# ---------------------------------------------------------------------------
# Caption validation
# ---------------------------------------------------------------------------

class TestCaption:

    def test_empty_caption_fails(self):
        ok, errors = validate_post_input(**valid(caption=''))
        assert ok is False
        assert any('caption' in e.lower() for e in errors)

    def test_whitespace_only_caption_fails(self):
        ok, errors = validate_post_input(**valid(caption='   '))
        assert ok is False

    def test_tiktok_caption_over_limit_fails(self):
        """TikTok title limit is 150 chars."""
        ok, errors = validate_post_input(**valid(
            caption   = 'x' * 151,
            platforms = ['tt'],
            video_url = 'https://example.com/v.mp4',
        ))
        assert ok is False
        assert any('TT' in e for e in errors)

    def test_instagram_caption_over_limit_fails(self):
        ok, errors = validate_post_input(**valid(
            caption   = 'x' * 2201,
            platforms = ['ig'],
            image_url = 'https://example.com/img.jpg',
        ))
        assert ok is False
        assert any('IG' in e for e in errors)

    def test_caption_at_limit_passes(self):
        """Exactly at the limit should pass."""
        ok, errors = validate_post_input(**valid(
            caption   = 'x' * 150,
            platforms = ['tt'],
            video_url = 'https://example.com/v.mp4',
        ))
        assert ok is True


# ---------------------------------------------------------------------------
# content_type validation
# ---------------------------------------------------------------------------

class TestContentType:

    def test_invalid_content_type_fails(self):
        ok, errors = validate_post_input(**valid(content_type='tweet'))
        assert ok is False
        assert any('content_type' in e.lower() for e in errors)

    def test_all_valid_content_types_pass(self):
        for ct in ('text', 'image', 'video', 'promo', 'update'):
            kwargs = valid(content_type=ct)
            if ct == 'image':
                kwargs['image_url'] = 'https://example.com/img.jpg'
            if ct == 'video':
                kwargs['video_url'] = 'https://example.com/v.mp4'
            ok, errors = validate_post_input(**kwargs)
            assert ok is True, f'Expected {ct} to pass, got: {errors}'


# ---------------------------------------------------------------------------
# Platform validation
# ---------------------------------------------------------------------------

class TestPlatforms:

    def test_empty_list_fails(self):
        ok, errors = validate_post_input(**valid(platforms=[]))
        assert ok is False
        assert any('platform' in e.lower() for e in errors)

    def test_none_platforms_fails(self):
        ok, errors = validate_post_input(**valid(platforms=None))
        assert ok is False

    def test_unknown_platform_key_fails(self):
        ok, errors = validate_post_input(**valid(platforms=['twitter']))
        assert ok is False
        assert any('twitter' in e for e in errors)


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

class TestURLs:

    def test_invalid_image_url_fails(self):
        ok, errors = validate_post_input(**valid(
            content_type='image',
            platforms=['fb'],
            image_url='not-a-url',
        ))
        assert ok is False
        assert any('image_url' in e for e in errors)

    def test_invalid_video_url_fails(self):
        ok, errors = validate_post_input(**valid(
            content_type='video',
            platforms=['fb'],
            video_url='ftp://wrong-scheme.com/v.mp4',
        ))
        assert ok is False
        assert any('video_url' in e for e in errors)

    def test_invalid_link_url_fails(self):
        ok, errors = validate_post_input(**valid(link_url='javascript:alert(1)'))
        assert ok is False
        assert any('link_url' in e for e in errors)

    def test_valid_https_url_passes(self):
        ok, errors = validate_post_input(**valid(
            content_type='image',
            platforms=['fb', 'ig'],
            image_url='https://cdn.example.com/image.png',
        ))
        assert ok is True


# ---------------------------------------------------------------------------
# Platform / content_type compatibility
# ---------------------------------------------------------------------------

class TestCompatibility:

    def test_instagram_without_media_fails(self):
        ok, errors = validate_post_input(**valid(platforms=['ig']))
        assert ok is False
        assert any('instagram' in e.lower() for e in errors)

    def test_youtube_without_video_fails(self):
        ok, errors = validate_post_input(**valid(platforms=['yt']))
        assert ok is False
        assert any('youtube' in e.lower() for e in errors)

    def test_tiktok_without_video_fails(self):
        ok, errors = validate_post_input(**valid(platforms=['tt']))
        assert ok is False
        assert any('tiktok' in e.lower() for e in errors)

    def test_content_type_video_without_video_url_fails(self):
        ok, errors = validate_post_input(**valid(content_type='video', platforms=['fb']))
        assert ok is False
        assert any('video_url' in e for e in errors)

    def test_content_type_image_without_any_media_fails(self):
        ok, errors = validate_post_input(**valid(content_type='image', platforms=['fb']))
        assert ok is False

    def test_multiple_errors_returned_at_once(self):
        """A single bad request should surface all errors, not just the first."""
        ok, errors = validate_post_input(
            caption='',
            content_type='badtype',
            platforms=['twitter'],
        )
        assert ok is False
        assert len(errors) >= 3
