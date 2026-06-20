"""
notification_service.py — Morning Daily Prompt (Phase 4 Session 2)

The #1 retention feature. Sends a daily prompt at the user's set time.
Creates the daily habit loop that makes the app essential within 2 weeks.

Supports:
  - Email (via SMTP / SendGrid)
  - Web push (via Flask-SSE or simple polling endpoint)
  - APScheduler integration
"""

import os
import json
import logging
import smtplib
from datetime import datetime, time as dtime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

logger = logging.getLogger(__name__)

NOTIF_SETTINGS_PATH = Path('static/notification_settings.json')


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------
def load_notification_settings(user_id: str = 'default') -> dict:
    """Load user notification preferences."""
    defaults = {
        'enabled':        True,
        'send_time':      '07:00',
        'email':          '',
        'timezone':       'America/New_York',
        'prompt_message': 'Good morning! Where are you today? What\'s the special?',
        'last_sent':      None,
    }
    try:
        if NOTIF_SETTINGS_PATH.exists():
            with open(NOTIF_SETTINGS_PATH) as f:
                stored = json.load(f)
            return {**defaults, **stored.get(user_id, {})}
    except Exception as e:
        logger.error('Failed to load notification settings: %s', e)
    return defaults


def save_notification_settings(settings: dict, user_id: str = 'default'):
    """Persist notification settings for a user."""
    try:
        all_settings = {}
        if NOTIF_SETTINGS_PATH.exists():
            with open(NOTIF_SETTINGS_PATH) as f:
                all_settings = json.load(f)
        all_settings[user_id] = settings
        with open(NOTIF_SETTINGS_PATH, 'w') as f:
            json.dump(all_settings, f, indent=2)
        logger.info('Notification settings saved for user=%s', user_id)
        return True
    except Exception as e:
        logger.error('Failed to save notification settings: %s', e)
        return False


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------
def _send_email(to_email: str, subject: str, body_html: str, body_text: str) -> bool:
    """Send email via SMTP. Supports SendGrid and standard SMTP."""
    smtp_host     = os.environ.get('SMTP_HOST', 'smtp.sendgrid.net')
    smtp_port     = int(os.environ.get('SMTP_PORT', 587))
    smtp_user     = os.environ.get('SMTP_USER', 'apikey')
    smtp_password = os.environ.get('SMTP_PASSWORD') or os.environ.get('SENDGRID_API_KEY')
    from_email    = os.environ.get('FROM_EMAIL', 'noreply@postpilotpro.com')
    from_name     = os.environ.get('FROM_NAME', 'PostPilot Pro')

    if not smtp_password:
        logger.warning('SMTP not configured — email not sent')
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'{from_name} <{from_email}>'
        msg['To']      = to_email

        msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info('Morning prompt email sent to %s', to_email)
        return True
    except Exception as e:
        logger.error('Email send failed: %s', e)
        return False


# ---------------------------------------------------------------------------
# Morning prompt email builder
# ---------------------------------------------------------------------------
MORNING_EMAIL_HTML = '''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:520px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,.08);">
    <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:32px 24px;text-align:center;">
      <div style="font-size:40px;margin-bottom:8px;">☀️</div>
      <h1 style="color:#fff;margin:0;font-size:22px;font-weight:700;">Good morning, {name}!</h1>
      <p style="color:rgba(255,255,255,.85);margin:8px 0 0;font-size:15px;">{prompt_message}</p>
    </div>
    <div style="padding:28px 24px;">
      <p style="color:#444;font-size:15px;margin:0 0 20px;">It only takes 30 seconds. Tell us where you are and what's on the menu today.</p>
      <a href="{dashboard_url}" style="display:block;background:#667eea;color:#fff;text-align:center;padding:14px 24px;border-radius:10px;text-decoration:none;font-weight:600;font-size:16px;">
        📍 Post Today's Location
      </a>
      {yesterdays_stats}
    </div>
    <div style="padding:16px 24px;background:#f8f9fa;text-align:center;border-top:1px solid #eee;">
      <p style="color:#999;font-size:12px;margin:0;">PostPilot Pro · <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>
'''

YESTERDAYS_STATS_HTML = '''
      <div style="background:#f0f4ff;border-radius:10px;padding:16px;margin-top:20px;">
        <p style="margin:0;color:#667eea;font-size:14px;font-weight:600;">📊 Yesterday\'s performance</p>
        <p style="margin:6px 0 0;color:#555;font-size:14px;">Your last post reached <strong>{reach}</strong> people and got <strong>{likes}</strong> likes 🎉</p>
      </div>
'''


def send_morning_prompt(user_id: str = 'default', stats: dict = None) -> bool:
    """
    Send the morning prompt email to the user.

    Args:
        user_id: User identifier
        stats:   Optional dict with { reach, likes } from yesterday's post

    Returns:
        True if sent, False otherwise.
    """
    settings = load_notification_settings(user_id)

    if not settings.get('enabled'):
        logger.info('Notifications disabled for user=%s', user_id)
        return False

    email = settings.get('email')
    if not email:
        logger.warning('No email set for user=%s', user_id)
        return False

    dashboard_url   = os.environ.get('APP_URL', 'http://localhost:5000') + '/'
    unsubscribe_url = os.environ.get('APP_URL', 'http://localhost:5000') + '/notifications/unsubscribe'

    stats_html = ''
    if stats and stats.get('reach'):
        stats_html = YESTERDAYS_STATS_HTML.format(
            reach=f"{stats['reach']:,}",
            likes=stats.get('likes', 0),
        )

    body_html = MORNING_EMAIL_HTML.format(
        name=settings.get('name', 'there'),
        prompt_message=settings.get('prompt_message'),
        dashboard_url=dashboard_url,
        unsubscribe_url=unsubscribe_url,
        yesterdays_stats=stats_html,
    )

    body_text = (
        f"Good morning! {settings.get('prompt_message')}\n\n"
        f"Post today's location: {dashboard_url}\n\n"
        f"-- PostPilot Pro"
    )

    subject = '☀️ Where are you today?'

    sent = _send_email(email, subject, body_html, body_text)

    if sent:
        settings['last_sent'] = datetime.utcnow().isoformat()
        save_notification_settings(settings, user_id)

    return sent


# ---------------------------------------------------------------------------
# Pending notification queue (for dashboard polling)
# ---------------------------------------------------------------------------
PENDING_PATH = Path('static/pending_notifications.json')


def push_dashboard_notification(message: str, type_: str = 'info', user_id: str = 'default'):
    """
    Queue a notification for the dashboard to pick up via polling.
    Types: 'info' | 'warning' | 'success' | 'error'
    """
    try:
        notifications = []
        if PENDING_PATH.exists():
            with open(PENDING_PATH) as f:
                all_notifs = json.load(f)
            notifications = all_notifs.get(user_id, [])
        else:
            all_notifs = {}

        notifications.append({
            'message':   message,
            'type':      type_,
            'timestamp': datetime.utcnow().isoformat(),
            'read':      False,
        })

        all_notifs[user_id] = notifications[-50:]  # Keep last 50
        with open(PENDING_PATH, 'w') as f:
            json.dump(all_notifs, f, indent=2)
        return True
    except Exception as e:
        logger.error('Failed to push dashboard notification: %s', e)
        return False


def get_pending_notifications(user_id: str = 'default', mark_read: bool = True) -> list:
    """Fetch unread dashboard notifications."""
    try:
        if not PENDING_PATH.exists():
            return []

        with open(PENDING_PATH) as f:
            all_notifs = json.load(f)

        notifs = all_notifs.get(user_id, [])
        unread = [n for n in notifs if not n.get('read')]

        if mark_read:
            for n in notifs:
                n['read'] = True
            all_notifs[user_id] = notifs
            with open(PENDING_PATH, 'w') as f:
                json.dump(all_notifs, f, indent=2)

        return unread
    except Exception as e:
        logger.error('Failed to get notifications: %s', e)
        return []


# ---------------------------------------------------------------------------
# APScheduler integration
# ---------------------------------------------------------------------------
def schedule_morning_prompts(scheduler, user_id: str = 'default'):
    """
    Register the morning prompt job with APScheduler.
    Call this from app.py during startup.

    Usage:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        schedule_morning_prompts(scheduler)
        scheduler.start()
    """
    settings = load_notification_settings(user_id)
    send_time = settings.get('send_time', '07:00')
    hour, minute = map(int, send_time.split(':'))

    job_id = f'morning_prompt_{user_id}'

    # Remove existing job if present
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        func=send_morning_prompt,
        trigger='cron',
        hour=hour,
        minute=minute,
        id=job_id,
        kwargs={'user_id': user_id},
        replace_existing=True,
    )

    logger.info('Morning prompt scheduled at %s for user=%s', send_time, user_id)
