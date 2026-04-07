"""
core/templatetags/egarage_tags.py
──────────────────────────────────
Custom template filters and tags for eGarage.

USAGE in templates:
  {% load egarage_tags %}
  {{ my_dict|dict_get:key }}
  {{ price|currency }}
  {{ booking.status|status_color }}
"""

from django import template
from django.utils import timezone

register = template.Library()


# ── DICT ACCESS ──────────────────────────────────────────────
@register.filter
def dict_get(d, key):
    """Get a dict value by variable key.
    Usage: {{ garage_hours|dict_get:day_num }}
    """
    if isinstance(d, dict):
        return d.get(key)
    try:
        return d[key]
    except (KeyError, IndexError, TypeError):
        return None


# ── CURRENCY ─────────────────────────────────────────────────
@register.filter
def currency(value):
    """Format number as Indian currency.
    Usage: {{ price|currency }}  → ₹3,999
    """
    try:
        val = float(value)
        if val >= 100000:
            return f'₹{val/100000:.1f}L'
        elif val >= 1000:
            # Indian comma format: 1,00,000
            s = f'{val:,.0f}'
            return f'₹{s}'
        return f'₹{val:.0f}'
    except (ValueError, TypeError):
        return f'₹0'


# ── STATUS COLOR ──────────────────────────────────────────────
@register.filter
def status_color(status):
    """Return CSS color class for booking status.
    Usage: {{ booking.status|status_color }}
    """
    mapping = {
        'confirmed':     'blue',
        'picked_up':     'purple',
        'at_garage':     'orange',
        'in_progress':   'yellow',
        'quality_check': 'teal',
        'delivered':     'green',
        'cancelled':     'red',
    }
    return mapping.get(status, 'grey')


# ── STATUS ICON ───────────────────────────────────────────────
@register.filter
def status_icon(status):
    icons = {
        'confirmed':     '✅',
        'picked_up':     '🚗',
        'at_garage':     '🏢',
        'in_progress':   '🔧',
        'quality_check': '🔍',
        'delivered':     '🎉',
        'cancelled':     '❌',
    }
    return icons.get(status, '📋')


# ── RATING STARS ──────────────────────────────────────────────
@register.filter
def stars(rating):
    """Convert rating number to star string.
    Usage: {{ review.rating|stars }}  → ★★★★☆
    """
    try:
        r = int(rating)
        return '★' * r + '☆' * (5 - r)
    except (ValueError, TypeError):
        return '☆☆☆☆☆'


# ── PHONE MASK ────────────────────────────────────────────────
@register.filter
def mask_phone(phone):
    """Mask middle digits of phone number.
    Usage: {{ user.phone|mask_phone }}  → +91 98***43210
    """
    s = str(phone or '')
    if len(s) >= 10:
        return s[:4] + '***' + s[-5:]
    return s


# ── TIME SINCE SHORT ──────────────────────────────────────────
@register.filter
def short_timesince(dt):
    """Short human-readable time since.
    Usage: {{ notif.created_at|short_timesince }}  → 2h ago
    """
    if not dt:
        return ''
    now   = timezone.now()
    diff  = now - dt
    secs  = int(diff.total_seconds())
    if secs < 60:
        return 'just now'
    elif secs < 3600:
        return f'{secs // 60}m ago'
    elif secs < 86400:
        return f'{secs // 3600}h ago'
    elif secs < 604800:
        return f'{secs // 86400}d ago'
    return dt.strftime('%d %b')


# ── MULTIPLY ──────────────────────────────────────────────────
@register.filter
def multiply(value, arg):
    """Multiply value by arg.
    Usage: {{ price|multiply:1.18 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


# ── PERCENTAGE ────────────────────────────────────────────────
@register.filter
def percentage(value, total):
    """Calculate percentage.
    Usage: {{ done|percentage:total }}
    """
    try:
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


# ── SUBTRACT ──────────────────────────────────────────────────
@register.filter
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value


# ── GST CALC ──────────────────────────────────────────────────
@register.filter
def add_gst(value, rate=18):
    """Add GST to a price.
    Usage: {{ price|add_gst }}  or  {{ price|add_gst:5 }}
    """
    try:
        return round(float(value) * (1 + float(rate) / 100), 2)
    except (ValueError, TypeError):
        return value


# ── RANGE TAG ─────────────────────────────────────────────────
@register.simple_tag
def make_range(n):
    """Generate range in template.
    Usage: {% make_range 5 as star_range %}
    """
    return range(int(n))


# ── IS_OWNER / IS_MECHANIC / IS_MANAGER ───────────────────────
@register.filter
def is_role(user, role):
    """Check user role.
    Usage: {% if request.user|is_role:'owner' %}
    """
    return getattr(user, 'role', '') == role


# ── INITIALS ──────────────────────────────────────────────────
@register.filter
def initials(name):
    """Get initials from full name.
    Usage: {{ user.name|initials }}  → MS
    """
    parts = str(name or '').split()
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# ── BOOKING STATUS DISPLAY ────────────────────────────────────
@register.filter
def booking_status_display(status):
    labels = {
        'confirmed':     'Confirmed',
        'picked_up':     'Picked Up',
        'at_garage':     'At Garage',
        'in_progress':   'In Progress',
        'quality_check': 'Quality Check',
        'delivered':     'Delivered',
        'cancelled':     'Cancelled',
    }
    return labels.get(status, status.replace('_', ' ').title())