"""
core/context_processors.py
────────────────────────────
Global context available in EVERY template.

Add to settings.py TEMPLATES[0]['OPTIONS']['context_processors']:
  'core.context_processors.global_context',
"""

from .models import Notification, Garage


def global_context(request):
    """
    Injects into every template:
      - unread_count    : number of unread notifications
      - unread_notifs   : latest 5 unread notifications (for nav dropdown)
      - user_garage     : garage object if user is a manager
      - site_name       : 'eGarage'
    """
    ctx = {
        'site_name':    'eGarage',
        'unread_count': 0,
        'unread_notifs': [],
        'user_garage':  None,
    }

    if request.user.is_authenticated:
        # Unread notification count (used in nav bell icon)
        try:
            unread = Notification.objects.filter(
                user=request.user, is_read=False
            ).order_by('-created_at')

            ctx['unread_count']  = unread.count()
            ctx['unread_notifs'] = unread[:5]
        except Exception:
            pass

        # Manager's garage (used in manager nav)
        if getattr(request.user, 'role', '') == 'manager':
            try:
                ctx['user_garage'] = Garage.objects.filter(
                    manager=request.user
                ).first()
            except Exception:
                pass

    return ctx