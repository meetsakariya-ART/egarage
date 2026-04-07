"""
core/otp_utils.py
─────────────────
Handles:
  • OTP generation (6-digit secure random)
  • Storing OTPs in Django cache (auto-expire in 10 min)
  • Sending beautiful HTML emails for:
      - Email verification (signup)
      - Login OTP
      - Welcome email
      - Booking confirmation
      - Password reset OTP
"""

import random
import string
import logging
from django.core.cache   import cache
from django.core.mail    import EmailMultiAlternatives
from django.conf         import settings
from django.utils        import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# OTP CORE
# ─────────────────────────────────────────────────────────────

OTP_EXPIRY_SECONDS = 600   # 10 minutes
OTP_MAX_ATTEMPTS   = 5     # lock after 5 wrong tries
OTP_RESEND_COOLDOWN = 60   # seconds before user can request new OTP


def _cache_key(purpose: str, identifier: str) -> str:
    """Generates a namespaced cache key."""
    return f'egarage:otp:{purpose}:{identifier.lower().strip()}'


def _attempts_key(purpose: str, identifier: str) -> str:
    return f'egarage:otp_attempts:{purpose}:{identifier.lower().strip()}'


def _cooldown_key(purpose: str, identifier: str) -> str:
    return f'egarage:otp_cooldown:{purpose}:{identifier.lower().strip()}'


def generate_otp(length: int = 6) -> str:
    """Returns a secure 6-digit numeric OTP."""
    return ''.join(random.SystemRandom().choices(string.digits, k=length))


def store_otp(purpose: str, identifier: str) -> str:
    """
    Generates a new OTP, stores it in cache, returns it.
    `purpose`    : 'signup' | 'login' | 'reset'
    `identifier` : email address
    """
    # Cooldown check
    if cache.get(_cooldown_key(purpose, identifier)):
        return None   # caller should tell user to wait

    otp = generate_otp()
    cache.set(_cache_key(purpose, identifier), otp, timeout=OTP_EXPIRY_SECONDS)
    cache.set(_cooldown_key(purpose, identifier), True, timeout=OTP_RESEND_COOLDOWN)
    # Reset attempt counter
    cache.delete(_attempts_key(purpose, identifier))
    return otp


def verify_otp(purpose: str, identifier: str, submitted_otp: str) -> dict:
    """
    Returns {'valid': True/False, 'reason': '...'}
    Increments failed-attempt counter; locks after OTP_MAX_ATTEMPTS.
    """
    identifier = identifier.lower().strip()
    attempts_key = _attempts_key(purpose, identifier)

    # Check lock
    attempts = cache.get(attempts_key, 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        return {'valid': False, 'reason': 'Too many incorrect attempts. Request a new OTP.'}

    stored = cache.get(_cache_key(purpose, identifier))

    if stored is None:
        return {'valid': False, 'reason': 'OTP has expired. Please request a new one.'}

    if stored != submitted_otp.strip():
        cache.set(attempts_key, attempts + 1, timeout=OTP_EXPIRY_SECONDS)
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        return {
            'valid':  False,
            'reason': f'Incorrect OTP. {remaining} attempt{"s" if remaining != 1 else ""} remaining.'
        }

    # ✅ Correct — clear cache
    cache.delete(_cache_key(purpose, identifier))
    cache.delete(_attempts_key(purpose, identifier))
    return {'valid': True, 'reason': ''}


def is_on_cooldown(purpose: str, identifier: str) -> bool:
    return bool(cache.get(_cooldown_key(purpose, identifier)))


# ─────────────────────────────────────────────────────────────
# EMAIL SENDER (HTML + plain text)
# ─────────────────────────────────────────────────────────────

BRAND_RED    = '#e8192c'
BRAND_DARK   = '#0f0824'
BRAND_GREEN  = '#00a651'
BRAND_BLUE   = '#1a56db'


def _base_html(title: str, content: str) -> str:
    """Wraps `content` in the eGarage branded email shell."""
    year = timezone.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Helvetica Neue',Arial,sans-serif;">

<!-- PRE-HEADER (hidden preview text) -->
<span style="display:none;max-height:0;overflow:hidden;">{title}</span>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:32px 16px;">
<tr><td align="center">
<table width="100%" style="max-width:560px;" cellpadding="0" cellspacing="0">

  <!-- HEADER -->
  <tr>
    <td style="background:{BRAND_DARK};border-radius:16px 16px 0 0;padding:24px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:{BRAND_RED};border-radius:9px;width:36px;height:36px;text-align:center;vertical-align:middle;">
                  <span style="color:white;font-size:18px;">🚗</span>
                </td>
                <td style="padding-left:10px;">
                  <span style="font-family:Georgia,serif;font-size:20px;font-weight:bold;color:{BRAND_RED};">e</span>
                  <span style="font-family:Georgia,serif;font-size:20px;font-weight:bold;color:#ffffff;">Garage</span>
                </td>
              </tr>
            </table>
          </td>
          <td align="right">
            <span style="font-size:11px;color:rgba(255,255,255,0.35);">India's Trusted Car Service</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- BODY -->
  <tr>
    <td style="background:#ffffff;padding:32px;">
      {content}
    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="background:#f8f8f8;border-radius:0 0 16px 16px;padding:20px 32px;border-top:1px solid #e0e0e0;">
      <p style="margin:0 0 6px;font-size:12px;color:#aaa;text-align:center;">
        eGarage · Rajkot, Gujarat, India<br>
        <a href="#" style="color:{BRAND_RED};text-decoration:none;">Unsubscribe</a> ·
        <a href="#" style="color:{BRAND_RED};text-decoration:none;">Privacy Policy</a> ·
        <a href="#" style="color:{BRAND_RED};text-decoration:none;">Help</a>
      </p>
      <p style="margin:0;font-size:11px;color:#ccc;text-align:center;">© {year} eGarage. All rights reserved.</p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _otp_block(otp: str, expiry_min: int = 10) -> str:
    """Returns the styled OTP digit block HTML."""
    digits = ''.join(
        f'<td style="width:46px;height:56px;background:#f8f8f8;border:2px solid #e0e0e0;'
        f'border-radius:10px;text-align:center;vertical-align:middle;'
        f'font-size:26px;font-weight:bold;color:{BRAND_DARK};font-family:Georgia,monospace;">'
        f'{d}</td><td style="width:6px;"></td>'
        for d in otp
    )
    return f"""
<table cellpadding="0" cellspacing="0" style="margin:24px auto;">
  <tr>{digits}</tr>
</table>
<p style="text-align:center;font-size:12px;color:#aaa;margin:0;">
  This OTP expires in <strong>{expiry_min} minutes</strong>. Do not share it with anyone.
</p>"""


def send_signup_otp(email: str, name: str, otp: str):
    """Send OTP email for new account verification."""
    content = f"""
<h2 style="font-size:22px;color:{BRAND_DARK};margin:0 0 8px;">Verify your email 🔐</h2>
<p style="color:#555;font-size:15px;line-height:1.6;margin:0 0 20px;">
  Hi <strong>{name}</strong>! Welcome to eGarage. <br>
  Use the OTP below to verify your email address and activate your account.
</p>
{_otp_block(otp)}
<div style="margin:28px 0;padding:16px;background:#fff7ed;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0;">
  <p style="margin:0;font-size:13px;color:#92400e;">
    ⚠️ <strong>Never share this OTP</strong> with anyone, including eGarage support.
    We will never ask for your OTP.
  </p>
</div>
<p style="color:#aaa;font-size:12px;margin:0;">
  If you did not create an eGarage account, you can safely ignore this email.
</p>"""
    _send(
        to=email,
        subject='Your eGarage verification OTP',
        html=_base_html('Verify your eGarage account', content),
        plain=f'Hi {name},\n\nYour eGarage signup OTP is: {otp}\n\nExpires in 10 minutes. Do not share.\n\neGarage Team'
    )


def send_login_otp(email: str, name: str, otp: str):
    """Send OTP email for login verification."""
    content = f"""
<h2 style="font-size:22px;color:{BRAND_DARK};margin:0 0 8px;">Login verification 🔑</h2>
<p style="color:#555;font-size:15px;line-height:1.6;margin:0 0 20px;">
  Hi <strong>{name}</strong>! We received a login request for your eGarage account.<br>
  Enter the OTP below to continue.
</p>
{_otp_block(otp)}
<div style="margin:28px 0;padding:16px;background:#eff6ff;border-left:4px solid {BRAND_BLUE};border-radius:0 8px 8px 0;">
  <p style="margin:0;font-size:13px;color:#1e40af;">
    🔒 If this wasn't you, <strong>change your password immediately</strong>.
    This OTP will expire in 10 minutes.
  </p>
</div>"""
    _send(
        to=email,
        subject='Your eGarage login OTP',
        html=_base_html('eGarage Login OTP', content),
        plain=f'Hi {name},\n\nYour eGarage login OTP is: {otp}\n\nExpires in 10 minutes.\n\neGarage Team'
    )


def send_password_reset_otp(email: str, name: str, otp: str):
    content = f"""
<h2 style="font-size:22px;color:{BRAND_DARK};margin:0 0 8px;">Reset your password 🔒</h2>
<p style="color:#555;font-size:15px;line-height:1.6;margin:0 0 20px;">
  Hi <strong>{name}</strong>! You requested a password reset for your eGarage account.
  Use the OTP below to proceed.
</p>
{_otp_block(otp)}
<p style="color:#aaa;font-size:12px;margin:16px 0 0;">
  If you did not request a password reset, please ignore this email. Your password will remain unchanged.
</p>"""
    _send(
        to=email,
        subject='Reset your eGarage password',
        html=_base_html('Reset eGarage Password', content),
        plain=f'Hi {name},\n\nYour eGarage password reset OTP is: {otp}\n\nExpires in 10 minutes.\n\neGarage Team'
    )


def send_welcome_email(email: str, name: str, role: str):
    """Sends a beautiful welcome email after successful signup."""
    role_label = {
        'owner':    'Vehicle Owner',
        'mechanic': 'Mechanic',
        'manager':  'Garage Manager',
        'admin':    'Administrator',
    }.get(role, 'Member')

    role_tips = {
        'owner': [
            ('📅', 'Book your first service', 'Choose from 11 services — free pickup & drop included.'),
            ('🚗', 'Add your vehicles', 'Save your car/bike details for faster bookings next time.'),
            ('📍', 'Find a garage near you', 'Locate the nearest eGarage in your city.'),
            ('📦', 'Track your job live', 'Watch your mechanic\'s checklist update in real time.'),
        ],
        'mechanic': [
            ('🔧', 'Check your job queue', 'View assigned jobs and update status as you work.'),
            ('💰', 'Track your earnings', 'See daily, weekly and monthly payout summaries.'),
            ('📅', 'Set your availability', 'Configure your shifts for all three seasons.'),
            ('📸', 'Upload job photos', 'Before/after photos build customer trust and protect you.'),
        ],
        'manager': [
            ('📊', 'View garage reports', 'Revenue, jobs and team performance at a glance.'),
            ('👥', 'Manage your team', 'Add mechanics, assign jobs, approve leave requests.'),
            ('⚙️', 'Configure garage settings', 'Set working hours, services and pricing.'),
            ('🔔', 'Monitor alerts', 'Get notified of issues, low stock and customer complaints.'),
        ],
    }.get(role, [])

    tips_html = ''.join(f"""
<tr>
  <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;">
    <table cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td style="width:42px;vertical-align:top;font-size:20px;">{ico}</td>
        <td>
          <p style="margin:0 0 2px;font-size:14px;font-weight:bold;color:{BRAND_DARK};">{title}</p>
          <p style="margin:0;font-size:13px;color:#777;">{desc}</p>
        </td>
      </tr>
    </table>
  </td>
</tr>""" for ico, title, desc in role_tips)

    content = f"""
<div style="text-align:center;padding:8px 0 24px;">
  <div style="font-size:48px;margin-bottom:12px;">🎉</div>
  <h1 style="font-size:24px;color:{BRAND_DARK};margin:0 0 8px;">Welcome to eGarage, {name}!</h1>
  <p style="font-size:15px;color:#555;margin:0;">
    Your account is verified and ready.<br>
    <strong style="color:{BRAND_RED};">{role_label}</strong> access activated.
  </p>
</div>

<div style="background:linear-gradient(135deg,{BRAND_DARK},{BRAND_BLUE});border-radius:12px;padding:20px;text-align:center;margin-bottom:24px;">
  <p style="color:rgba(255,255,255,0.5);font-size:11px;margin:0 0 4px;letter-spacing:1px;text-transform:uppercase;">Your Account</p>
  <p style="color:#fff;font-size:16px;font-weight:bold;margin:0;">{email}</p>
  <p style="color:rgba(255,255,255,0.4);font-size:12px;margin:6px 0 0;">{role_label}</p>
</div>

{"<h3 style='font-size:16px;color:" + BRAND_DARK + ";margin:0 0 12px;'>Getting started</h3><table width='100%' cellpadding='0' cellspacing='0'>" + tips_html + "</table>" if tips_html else ""}

<div style="text-align:center;margin:28px 0 0;">
  <a href="{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}/dashboard/"
     style="display:inline-block;padding:14px 36px;background:{BRAND_RED};color:#fff;
            text-decoration:none;border-radius:10px;font-weight:bold;font-size:15px;">
    Go to Dashboard →
  </a>
</div>"""

    _send(
        to=email,
        subject=f'Welcome to eGarage, {name}! 🎉',
        html=_base_html(f'Welcome to eGarage, {name}!', content),
        plain=f'Hi {name},\n\nWelcome to eGarage! Your {role_label} account is active.\nLogin at: {getattr(settings, "SITE_URL", "http://127.0.0.1:8000")}/login/\n\neGarage Team'
    )


def send_payment_confirmation(booking):
    """Sends payment receipt email after advance is paid."""
    svc_name = booking.service.name if booking.service else 'Car Service'
    garage   = booking.garage.name  if booking.garage  else 'eGarage'
    method   = {'upi': 'UPI', 'card': 'Card', 'cash': 'Cash'}.get(
                  str(booking.advance_method), 'Online')
    advance  = float(booking.advance_amount)
    balance  = float(booking.final_price) - advance

    content = f"""
<h2 style="font-size:22px;color:{BRAND_DARK};margin:0 0 8px;">Payment Received 💳</h2>
<p style="color:#555;font-size:15px;line-height:1.6;margin:0 0 20px;">
  Hi <strong>{booking.customer_name}</strong>! Your advance payment has been received.
  Here is your payment receipt:
</p>

<table width="100%" cellpadding="0" cellspacing="0"
  style="background:#f8f8f8;border-radius:12px;padding:20px;margin-bottom:20px;">
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Booking Ref</td>
      <td align="right" style="font-size:14px;font-weight:bold;color:{BRAND_BLUE};">{booking.reference}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Service</td>
      <td align="right" style="font-size:14px;font-weight:bold;color:{BRAND_DARK};">{svc_name}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Garage</td>
      <td align="right" style="font-size:14px;color:{BRAND_DARK};">{garage}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Date & Time</td>
      <td align="right" style="font-size:14px;color:{BRAND_DARK};">{booking.scheduled_date.strftime("%d %b %Y")} at {str(booking.scheduled_slot)[:5]}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Payment Method</td>
      <td align="right" style="font-size:14px;color:{BRAND_DARK};">{method}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">✅ Advance Paid Now</td>
      <td align="right" style="font-size:18px;font-weight:bold;color:{BRAND_GREEN};">₹{advance:.0f}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">⏳ Balance at Garage</td>
      <td align="right" style="font-size:16px;font-weight:bold;color:#f59e0b;">₹{balance:.0f}</td>
    </tr></table>
  </td></tr>
</table>

<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px;margin-bottom:16px;">
  <p style="margin:0;font-size:13px;color:#166534;">
    ✅ Your slot is <strong>confirmed</strong>. The remaining balance of
    <strong>₹{balance:.0f}</strong> is payable at the garage after service completion.
  </p>
</div>

<div style="text-align:center;margin:24px 0 0;">
  <a href="{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}/track/?ref={booking.reference}"
     style="display:inline-block;padding:13px 30px;background:{BRAND_RED};color:#fff;
            text-decoration:none;border-radius:10px;font-weight:bold;font-size:14px;">
    Track Your Booking →
  </a>
</div>"""

    _send(
        to=booking.customer_email or booking.customer.email,
        subject=f'✅ Payment of ₹{advance:.0f} received — {booking.reference}',
        html=_base_html('Payment Receipt', content),
        plain=(f'Payment received for {booking.reference}.\n'
               f'Advance paid: ₹{advance:.0f} via {method}\n'
               f'Balance at garage: ₹{balance:.0f}\n'
               f'Service: {svc_name} at {garage}\n'
               f'Date: {booking.scheduled_date} at {str(booking.scheduled_slot)[:5]}\n\neGarage Team')
    )


def send_booking_confirmation(booking):
    """Sends booking confirmation email to the customer."""
    svc_name = booking.service.name if booking.service else 'Car Service'
    garage   = booking.garage.name  if booking.garage  else 'eGarage'
    content  = f"""
<h2 style="font-size:22px;color:{BRAND_DARK};margin:0 0 8px;">Booking Confirmed ✅</h2>
<p style="color:#555;font-size:15px;line-height:1.6;margin:0 0 20px;">
  Hi <strong>{booking.customer_name}</strong>! Your booking is confirmed. Here are the details:
</p>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f8f8;border-radius:12px;padding:20px;margin-bottom:20px;">
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Booking Ref</td>
      <td align="right" style="font-size:14px;font-weight:bold;color:{BRAND_BLUE};">{booking.reference}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Service</td>
      <td align="right" style="font-size:14px;font-weight:bold;color:{BRAND_DARK};">{svc_name} ({booking.get_package_display()})</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Garage</td>
      <td align="right" style="font-size:14px;color:{BRAND_DARK};">{garage}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Date & Time</td>
      <td align="right" style="font-size:14px;color:{BRAND_DARK};">{booking.scheduled_date.strftime("%d %b %Y")} at {str(booking.scheduled_slot)[:5]}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Amount Paid</td>
      <td align="right" style="font-size:16px;font-weight:bold;color:{BRAND_GREEN};">₹{float(booking.final_price):.0f}</td>
    </tr></table>
  </td></tr>
</table>

{"<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px;margin-bottom:16px;'><p style='margin:0;font-size:13px;color:#166534;'>🚗 <strong>Free pickup</strong> from your door. Our driver will call you 10 minutes before arrival.</p></div>" if booking.pickup_required else ""}

<div style="text-align:center;margin:24px 0 0;">
  <a href="{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}/track/?ref={booking.reference}"
     style="display:inline-block;padding:13px 30px;background:{BRAND_RED};color:#fff;
            text-decoration:none;border-radius:10px;font-weight:bold;font-size:14px;">
    Track Live →
  </a>
</div>"""

    _send(
        to=booking.customer_email or booking.customer.email,
        subject=f'Booking {booking.reference} confirmed — {svc_name}',
        html=_base_html(f'Booking {booking.reference} Confirmed', content),
        plain=f'Booking {booking.reference} confirmed.\n{svc_name} on {booking.scheduled_date} at {str(booking.scheduled_slot)[:5]}.\nAmount: ₹{float(booking.final_price):.0f}\n\neGarage Team'
    )


# ─────────────────────────────────────────────────────────────
# INTERNAL SEND HELPER
# ─────────────────────────────────────────────────────────────

def send_service_completed_email(booking, job=None):
    """Sends service completion email to customer AND summary to manager."""
    svc_name = booking.service.name if booking.service else 'Car Service'
    garage   = booking.garage.name  if booking.garage  else 'eGarage'
    amount   = float(booking.final_price)

    # ── Customer email ──
    tasks_html = ''
    if job:
        tasks = job.tasks.filter(is_done=True).select_related('mechanic')
        if tasks.exists():
            tasks_html = '<div style="margin-bottom:16px;"><div style="font-size:13px;font-weight:bold;color:#333;margin-bottom:8px;">Work Done:</div>'
            for t in tasks:
                mech = t.mechanic.name if t.mechanic else 'Mechanic'
                tasks_html += f'<div style="padding:6px 10px;background:#f8f8f8;border-radius:6px;margin-bottom:4px;font-size:13px;">✅ {t.task_name} <span style="color:#999;font-size:11px;">by {mech}</span></div>'
            tasks_html += '</div>'

    customer_content = f"""
<h2 style="font-size:22px;color:{BRAND_DARK};margin:0 0 8px;">Service Completed ✅</h2>
<p style="color:#555;font-size:15px;line-height:1.6;margin:0 0 20px;">
  Hi <strong>{booking.customer_name}</strong>! Your vehicle service is complete and verified.
</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f8f8;border-radius:12px;padding:20px;margin-bottom:20px;">
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Booking Ref</td>
      <td align="right" style="font-size:14px;font-weight:bold;color:{BRAND_BLUE};">{booking.reference}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Service</td>
      <td align="right" style="font-size:14px;font-weight:bold;">{svc_name}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Garage</td>
      <td align="right" style="font-size:14px;">{garage}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:8px 0;">
    <table width="100%"><tr>
      <td style="font-size:13px;color:#777;">Amount Charged</td>
      <td align="right" style="font-size:16px;font-weight:bold;color:{BRAND_GREEN};">₹{amount:.0f}</td>
    </tr></table>
  </td></tr>
</table>
{tasks_html}
<div style="text-align:center;margin:24px 0 0;">
  <a href="{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}/booking/{booking.reference}/rate/"
     style="display:inline-block;padding:13px 30px;background:{BRAND_RED};color:#fff;
            text-decoration:none;border-radius:10px;font-weight:bold;font-size:14px;">
    ⭐ Rate Your Service →
  </a>
</div>"""

    _send(
        to=booking.customer_email or booking.customer.email,
        subject=f'Service Complete — {booking.reference} — {svc_name}',
        html=_base_html(f'Service Complete — {booking.reference}', customer_content),
        plain=f'Your {svc_name} service is complete!\nRef: {booking.reference}\nGarage: {garage}\nAmount: ₹{amount:.0f}\n\nPlease rate your experience at: {getattr(settings, "SITE_URL", "http://127.0.0.1:8000")}/booking/{booking.reference}/rate/\n\neGarage Team'
    )

    # ── Manager email ──
    if booking.garage and booking.garage.manager and booking.garage.email:
        tasks_summary = ''
        if job:
            tasks_done = job.tasks.filter(is_done=True).select_related('mechanic')
            if tasks_done.exists():
                for t in tasks_done:
                    mech = t.mechanic.name if t.mechanic else 'Mechanic'
                    tasks_summary += f'\n• {t.task_name} (by {mech})'

        manager_plain = (
            f'Job Completed — {booking.reference}\n'
            f'Customer: {booking.customer_name}\n'
            f'Service: {svc_name}\n'
            f'Amount: ₹{amount:.0f}\n'
            f'Mechanic: {job.mechanic.name if job and job.mechanic else "—"}\n'
            f'Tasks Done:{tasks_summary or " (no tasks logged)"}\n\n'
            f'Login to verify the job and release payment to your garage wallet.\n'
            f'{getattr(settings, "SITE_URL", "http://127.0.0.1:8000")}/team/\n\neGarage'
        )
        _send(
            to=booking.garage.email or booking.garage.manager.email,
            subject=f'Job Complete — {booking.reference} — Verify to Release ₹{amount:.0f}',
            html=_base_html(f'Job Complete — {booking.reference}', f'<p style="font-size:15px;color:#555;line-height:1.8;">{manager_plain.replace(chr(10),"<br>")}</p>'),
            plain=manager_plain
        )


def _send(to: str, subject: str, html: str, plain: str):
    """Sends an email. Logs but doesn't crash if it fails."""
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'eGarage <noreply@egarage.in>')
        msg = EmailMultiAlternatives(subject, plain, from_email, [to])
        msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=False)
        logger.info(f'Email sent: {subject} → {to}')
    except Exception as e:
        logger.error(f'Email failed: {subject} → {to} | Error: {e}')