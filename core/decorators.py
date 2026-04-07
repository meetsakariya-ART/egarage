"""
core/decorators.py
──────────────────
Role-based access control decorators.
Usage:

    @owner_required
    def bookingView(request): ...

    @mechanic_required
    def mechanicJobsView(request): ...

    @manager_required
    def reportsView(request): ...

    @roles_required('owner', 'admin')
    def someView(request): ...
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib   import messages
from django.contrib.auth.decorators import login_required


def roles_required(*roles):
    """
    Decorator that checks user is authenticated AND has one of the given roles.
    Redirects with a clear error message if not.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Superuser always passes
            if user.is_superuser or user.is_admin:
                return view_func(request, *args, **kwargs)

            if user.role not in roles:
                _deny(request, roles)
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _deny(request, allowed_roles):
    role_labels = {
        'owner':    'Vehicle Owner',
        'mechanic': 'Mechanic',
        'manager':  'Garage Manager',
        'admin':    'Administrator',
    }
    allowed = ', '.join(role_labels.get(r, r) for r in allowed_roles)
    messages.error(
        request,
        f'🚫 Access denied. This page is only available to: {allowed}.'
    )


# ── Shorthand decorators ──────────────────────────────────────

def owner_required(view_func):
    return roles_required('owner', 'admin')(view_func)

def mechanic_required(view_func):
    return roles_required('mechanic', 'admin')(view_func)

def manager_required(view_func):
    return roles_required('manager', 'admin')(view_func)

def admin_required(view_func):
    return roles_required('admin')(view_func)

def staff_or_manager(view_func):
    """Allows both admin and manager."""
    return roles_required('manager', 'admin')(view_func)

def any_staff(view_func):
    """Allows mechanic, manager, or admin — anyone who isn't a regular owner."""
    return roles_required('mechanic', 'manager', 'admin')(view_func)