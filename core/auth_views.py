"""
core/auth_views.py  — Complete fixed authentication system
"""

import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout as auth_logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from .models import User, Notification
from .otp_utils import (
    store_otp, verify_otp, is_on_cooldown,
    send_signup_otp, send_login_otp,
    send_password_reset_otp, send_welcome_email,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _mask_email(email: str) -> str:
    try:
        user_part, domain = email.split('@')
        masked_user  = user_part[0] + '•' * min(len(user_part) - 1, 4)
        domain_parts = domain.split('.')
        masked_dom   = domain_parts[0][0] + '•' * min(len(domain_parts[0]) - 1, 4)
        return f'{masked_user}@{masked_dom}.{".".join(domain_parts[1:])}'
    except Exception:
        return email[:3] + '•••@•••'


def _create_welcome_notification(user):
    role_msg = {
        'owner':    'Book your first service and enjoy free pickup & drop. 🚗',
        'mechanic': 'Check your job queue and start earning. 🔧',
        'manager':  'Set up your garage hours, services and team. 🏢',
        'admin':    'Full platform access granted. 🛡️',
    }.get(user.role, 'Welcome aboard!')
    Notification.objects.create(
        user    = user,
        title   = f'Welcome to eGarage, {user.name}! 🎉',
        message = role_msg,
        type    = 'account',
    )


# ─────────────────────────────────────────────────────────────
# SIGN UP  Step 1 — collect details
# ─────────────────────────────────────────────────────────────

@never_cache
@require_http_methods(['GET', 'POST'])
def signupView(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None

    if request.method == 'POST':
        name     = request.POST.get('name',     '').strip()
        email    = request.POST.get('email',    '').strip().lower()
        phone    = request.POST.get('phone',    '').strip()
        role     = request.POST.get('role',     'owner').strip()
        city     = request.POST.get('city',     '').strip()
        password = request.POST.get('password', '')
        confirm  = request.POST.get('confirm',  '')

        # ── debug print (remove after testing) ──
        logger.debug(f"SIGNUP: name={name} email={email} role={role} passlen={len(password)}")

        # ── validation ──
        if not name:
            error = 'Please enter your full name.'
        elif not email or '@' not in email:
            error = 'Please enter a valid email address.'
        elif not phone:
            error = 'Please enter your phone number.'
        elif not password:
            error = 'Please enter a password.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != confirm:
            error = 'Passwords do not match. Please try again.'
        elif role not in ('owner', 'mechanic', 'manager', 'individual'):
            error = 'Please select a valid role.'
        elif User.objects.filter(email=email).exists():
            error = 'An account with this email already exists. Please log in.'
        else:
            # ── store in session and send OTP ──
            request.session['pending_signup'] = {
                'name':     name,
                'phone':    phone,
                'email':    email,
                'role':     role,
                'city':     city,
                'password': password,
            }

            if is_on_cooldown('signup', email):
                error = 'Please wait 60 seconds before requesting another OTP.'
            else:
                try:
                    otp = store_otp('signup', email)
                    send_signup_otp(email=email, name=name, otp=otp)
                    return redirect('signup_verify')
                except Exception as e:
                    logger.error(f"OTP send failed: {e}")
                    error = f'Could not send OTP email. Error: {str(e)}'

    return render(request, 'core/auth/signup.html', {'error': error})


# ─────────────────────────────────────────────────────────────
# SIGN UP  Step 2 — verify OTP
# ─────────────────────────────────────────────────────────────

@never_cache
@require_http_methods(['GET', 'POST'])
def signupVerifyView(request):
    pending = request.session.get('pending_signup')
    if not pending:
        return redirect('signup')

    email    = pending['email']
    error    = None
    cooldown = is_on_cooldown('signup', email)

    if request.method == 'POST':
        submitted = request.POST.get('otp', '').strip()
        result    = verify_otp('signup', email, submitted)

        if result['valid']:
            # ── create user ──
            # Handle individual mechanic role
            actual_role = pending['role']
            is_individual = False
            if actual_role == 'individual':
                actual_role = 'mechanic'
                is_individual = True

            user = User.objects.create_user(
                email         = pending['email'],
                name          = pending['name'],
                password      = pending['password'],
                phone         = pending['phone'],
                role          = actual_role,
                city          = pending.get('city', ''),
                is_individual = is_individual,
            )

            del request.session['pending_signup']

            login(request, user, backend='core.backends.EmailBackend')

            _create_welcome_notification(user)

            # ── Notify admins if Individual Mechanic signed up ──
            if is_individual:
                try:
                    super_admins = User.objects.filter(is_super_admin=True)
                    for admin in super_admins:
                        Notification.objects.create(
                            user=admin,
                            title=f'🛠️ Individual Mechanic Signup: {user.name}',
                            message=f'{user.name} ({user.email}) signed up as an Individual Mechanic from {user.city}. Review and approve in the admin panel.',
                            type='system'
                        )
                except Exception as e:
                    logger.error(f'Individual mech notify failed: {e}')

            # ── Notify admins if a Manager signed up (needs approval) ──
            if user.role == 'manager':
                try:
                    from .models import Notification
                    super_admins = User.objects.filter(is_super_admin=True)
                    for admin in super_admins:
                        Notification.objects.create(
                            user=admin,
                            title=f'👤 New Manager Signup: {user.name}',
                            message=f'{user.name} ({user.email}) signed up as Manager from {user.city}. Approve to let them set up a garage.',
                            type='system'
                        )
                except Exception as e:
                    logger.error(f'Manager notify failed: {e}')

            # send welcome email (don't crash if it fails)
            try:
                send_welcome_email(
                    email=user.email,
                    name=user.name,
                    role=user.role
                )
            except Exception as e:
                logger.error(f"Welcome email failed: {e}")

            messages.success(
                request,
                f'🎉 Welcome to eGarage, {user.name}! Your account is ready.'
            )
            return redirect('dashboard')

        else:
            error = result['reason']
            if 'Too many' in result['reason']:
                del request.session['pending_signup']
                messages.error(request, result['reason'] + ' Please sign up again.')
                return redirect('signup')

    return render(request, 'core/auth/verify_otp.html', {
        'purpose':  'signup',
        'email':    _mask_email(email),
        'error':    error,
        'cooldown': cooldown,
    })


# ─────────────────────────────────────────────────────────────
# LOGIN  Step 1 — email + password
# ─────────────────────────────────────────────────────────────

@never_cache
@require_http_methods(['GET', 'POST'])
def loginView(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None

    if request.method == 'POST':
        email    = request.POST.get('email',    '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            error = 'Please enter your email and password.'
        else:
            user = authenticate(request, username=email, password=password)

            if user is None:
                error = 'Invalid email or password. Please try again.'
            elif not user.is_active:
                error = 'Your account has been suspended. Please contact support.'
            else:
                # ── SUPER ADMIN — skip OTP completely ──────────
                if getattr(user, 'is_super_admin', False):
                    login(request, user, backend='core.backends.EmailBackend')
                    messages.success(request, f'Welcome back, {user.name}! Super Admin access granted.')
                    return redirect('admin_panel')

                # ── REGULAR ADMIN — must be approved, then OTP ──
                if user.role == 'admin' and not getattr(user, 'is_super_admin', False):
                    if not getattr(user, 'admin_approved', False):
                        error = 'Your admin access is pending Super Admin approval. Please wait.'
                        return render(request, 'core/auth/login.html', {'error': error})
                    # approved admin → fall through to OTP

                # ── MANAGER — must be approved by admin ──────────
                if user.role == 'manager' and not getattr(user, 'manager_approved', False):
                    error = 'Your manager account is pending Admin approval. You will be notified when approved.'
                    return render(request, 'core/auth/login.html', {'error': error})

                # ── INDIVIDUAL MECHANIC — check admin approval ────
                if user.role == 'mechanic' and getattr(user, 'is_individual', False):
                    try:
                        ind_profile = user.individual_profile
                        if ind_profile.status != 'approved':
                            error = 'Your individual mechanic application is pending Admin approval.'
                            return render(request, 'core/auth/login.html', {'error': error})
                    except Exception:
                        # No profile yet — redirect to apply
                        error = 'Your individual mechanic application is pending Admin approval.'
                        return render(request, 'core/auth/login.html', {'error': error})

                # ── MECHANIC — check if approved by manager ──────
                elif user.role == 'mechanic' and not getattr(user, 'is_individual', False):
                    try:
                        profile = user.mechanic_profile
                        if profile.status != 'approved':
                            error = 'Your mechanic account is pending manager approval.'
                            return render(request, 'core/auth/login.html', {'error': error})
                    except Exception:
                        pass
                    # ── Manager-created mechanic: skip OTP, login directly ──
                    if getattr(user, 'manager_created', False):
                        login(request, user, backend='core.backends.EmailBackend')
                        return redirect('dashboard')

                # Everyone else — require OTP
                request.session['pending_login_email'] = email
                request.session['pending_login_uid']   = user.pk

                if is_on_cooldown('login', email):
                    error = 'Please wait 60 seconds before requesting another OTP.'
                else:
                    try:
                        otp = store_otp('login', email)
                        send_login_otp(email=email, name=user.name, otp=otp)
                        return redirect('login_verify')
                    except Exception as e:
                        logger.error(f"Login OTP send failed: {e}")
                        error = f'Could not send OTP email. Error: {str(e)}'

    return render(request, 'core/auth/login.html', {'error': error})


# ─────────────────────────────────────────────────────────────
# LOGIN  Step 2 — verify OTP
# ─────────────────────────────────────────────────────────────

@never_cache
@require_http_methods(['GET', 'POST'])
def loginVerifyView(request):
    email = request.session.get('pending_login_email')
    uid   = request.session.get('pending_login_uid')

    if not email or not uid:
        return redirect('login')

    error    = None
    cooldown = is_on_cooldown('login', email)

    if request.method == 'POST':
        submitted = request.POST.get('otp', '').strip()
        result    = verify_otp('login', email, submitted)

        if result['valid']:
            try:
                user = User.objects.get(pk=uid, email=email, is_active=True)
            except User.DoesNotExist:
                messages.error(request, 'Account not found. Please log in again.')
                return redirect('login')

            del request.session['pending_login_email']
            del request.session['pending_login_uid']

            login(request, user, backend='core.backends.EmailBackend')

            greetings = {
                'owner':    f'Welcome back, {user.name}! Ready to book a service?',
                'mechanic': f'Welcome back, {user.name}! Your jobs are waiting.',
                'manager':  f'Welcome back, {user.name}! Check today\'s reports.',
                'admin':    f'Admin session started, {user.name}.',
            }
            messages.success(request, greetings.get(user.role, f'Welcome back, {user.name}!'))

            next_url = request.GET.get('next') or '/dashboard/'
            return redirect(next_url)

        else:
            error = result['reason']
            if 'Too many' in result['reason']:
                del request.session['pending_login_email']
                del request.session['pending_login_uid']
                messages.error(request, result['reason'])
                return redirect('login')

    return render(request, 'core/auth/verify_otp.html', {
        'purpose':  'login',
        'email':    _mask_email(email),
        'error':    error,
        'cooldown': cooldown,
    })


# ─────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────

def logoutView(request):
    name = request.user.name if request.user.is_authenticated else ''
    auth_logout(request)
    if name:
        messages.info(request, f'👋 See you soon, {name.split()[0]}!')
    return redirect('home')


# ─────────────────────────────────────────────────────────────
# RESEND OTP
# ─────────────────────────────────────────────────────────────

@require_http_methods(['POST'])
def resendOtpView(request):
    purpose = request.POST.get('purpose', 'login')

    if purpose == 'signup':
        pending = request.session.get('pending_signup')
        if not pending:
            return redirect('signup')
        email = pending['email']
        name  = pending['name']
        if is_on_cooldown('signup', email):
            messages.warning(request, 'Please wait 60 seconds before requesting another OTP.')
            return redirect('signup_verify')
        try:
            otp = store_otp('signup', email)
            send_signup_otp(email=email, name=name, otp=otp)
            messages.success(request, f'New OTP sent to {_mask_email(email)}.')
        except Exception as e:
            messages.error(request, f'Could not send OTP: {str(e)}')
        return redirect('signup_verify')

    elif purpose == 'login':
        email = request.session.get('pending_login_email')
        uid   = request.session.get('pending_login_uid')
        if not email or not uid:
            return redirect('login')
        try:
            user = User.objects.get(pk=uid, email=email)
        except User.DoesNotExist:
            return redirect('login')
        if is_on_cooldown('login', email):
            messages.warning(request, 'Please wait 60 seconds before requesting another OTP.')
            return redirect('login_verify')
        try:
            otp = store_otp('login', email)
            send_login_otp(email=email, name=user.name, otp=otp)
            messages.success(request, f'New OTP sent to {_mask_email(email)}.')
        except Exception as e:
            messages.error(request, f'Could not send OTP: {str(e)}')
        return redirect('login_verify')

    elif purpose == 'reset':
        email = request.session.get('pending_reset_email')
        if not email:
            return redirect('forgot_password')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return redirect('forgot_password')
        if is_on_cooldown('reset', email):
            messages.warning(request, 'Please wait 60 seconds.')
            return redirect('reset_password')
        try:
            otp = store_otp('reset', email)
            send_password_reset_otp(email=email, name=user.name, otp=otp)
            messages.success(request, f'New OTP sent to {_mask_email(email)}.')
        except Exception as e:
            messages.error(request, f'Could not send OTP: {str(e)}')
        return redirect('reset_password')

    return redirect('home')


# ─────────────────────────────────────────────────────────────
# FORGOT PASSWORD  Step 1 — enter email
# ─────────────────────────────────────────────────────────────

@never_cache
@require_http_methods(['GET', 'POST'])
def forgotPasswordView(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if not email:
            error = 'Please enter your email address.'
        else:
            # Don't reveal if email exists for security
            request.session['pending_reset_email'] = email
            try:
                user = User.objects.get(email=email, is_active=True)
                if not is_on_cooldown('reset', email):
                    otp = store_otp('reset', email)
                    send_password_reset_otp(email=email, name=user.name, otp=otp)
            except User.DoesNotExist:
                pass  # silent — don't reveal
            except Exception as e:
                logger.error(f"Reset OTP send failed: {e}")

            return redirect('reset_password')

    return render(request, 'core/auth/forgot_password.html', {'error': error})


# ─────────────────────────────────────────────────────────────
# RESET PASSWORD  Step 2 — OTP + new password
# ─────────────────────────────────────────────────────────────

@never_cache
@require_http_methods(['GET', 'POST'])
def resetPasswordView(request):
    email = request.session.get('pending_reset_email')
    if not email:
        return redirect('forgot_password')

    error    = None
    cooldown = is_on_cooldown('reset', email)
    step     = request.POST.get('step', 'otp')

    if request.method == 'POST':
        if step == 'otp':
            submitted = request.POST.get('otp', '').strip()
            result    = verify_otp('reset', email, submitted)
            if result['valid']:
                request.session['reset_otp_verified'] = True
                return render(request, 'core/auth/reset_password.html', {
                    'email':            _mask_email(email),
                    'show_new_password': True,
                    'cooldown':         False,
                })
            else:
                error = result['reason']

        elif step == 'newpass':
            if not request.session.get('reset_otp_verified'):
                return redirect('forgot_password')
            new_pass = request.POST.get('password', '')
            confirm  = request.POST.get('confirm', '')
            if len(new_pass) < 8:
                error = 'Password must be at least 8 characters.'
                return render(request, 'core/auth/reset_password.html', {
                    'email': _mask_email(email),
                    'show_new_password': True,
                    'error': error
                })
            if new_pass != confirm:
                error = 'Passwords do not match.'
                return render(request, 'core/auth/reset_password.html', {
                    'email': _mask_email(email),
                    'show_new_password': True,
                    'error': error
                })
            try:
                user = User.objects.get(email=email, is_active=True)
                user.set_password(new_pass)
                user.save()
                del request.session['pending_reset_email']
                del request.session['reset_otp_verified']
                messages.success(request, '✅ Password reset successfully! Please log in.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'Account not found.')
                return redirect('forgot_password')

    return render(request, 'core/auth/reset_password.html', {
        'purpose':           'reset',
        'email':             _mask_email(email),
        'error':             error,
        'cooldown':          cooldown,
        'show_new_password': False,
    })