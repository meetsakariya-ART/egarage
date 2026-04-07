"""
core/views.py  —  eGarage Complete Views
==========================================
All views for the full platform.
"""
import logging
logger = logging.getLogger(__name__)

import json
import hmac
import hashlib

from django.shortcuts       import render, redirect, get_object_or_404
from django.contrib.auth    import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http            import JsonResponse, HttpResponse
from django.conf            import settings
from django.utils           import timezone
from django.db.models       import Count, Sum, Avg, Q
from django.contrib         import messages

from .models import (
    User, AdminRequest, Garage, GarageHours, Service, Vehicle,
    GarageService, GarageCustomService,
    Booking, Job, JobChecklistItem, JobPhoto, JobPart, JobTask, JobDecline,
    Coupon, Notification, Review, LiveLocation, EmergencyRequest,
    MechanicProfile, MechanicRequest, IndividualMechanicProfile,
    MechanicLeaveRequest, MechanicShift, GarageTransaction,
    BookingMessage, MechanicEarning,
)


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _build_service_rows(garage, all_services):
    """Build list of {svc, offered, basic, standard, premium, notes} for templates."""
    gs_map = {}
    if garage:
        for gs in GarageService.objects.filter(garage=garage).select_related('service'):
            gs_map[gs.service.pk] = gs
    rows = []
    for svc in all_services:
        gs = gs_map.get(svc.pk)
        rows.append({
            'svc':      svc,
            'offered':  gs.is_offered if gs else True,
            'basic':    gs.price_basic    if gs and gs.price_basic    else '',
            'standard': gs.price_standard if gs and gs.price_standard else '',
            'premium':  gs.price_premium  if gs and gs.price_premium  else '',
            'notes':    gs.notes          if gs else '',
        })
    return rows


def create_notification(user, title, message, notif_type='booking', booking=None):
    try:
        Notification.objects.create(
            user=user, title=title, message=message, type=notif_type,
            **({'ref_booking': booking} if booking else {})
        )
    except Exception:
        pass


SERVICES_DATA = {
    'car-service': {'name':'Standard Car Service','icon':'🔧','duration':'3h',
        'packages':{'basic':1999,'standard':3999,'premium':6999},'checklist_key':'car_service'},
    'ac-service':  {'name':'AC Full Service','icon':'❄️','duration':'2h',
        'packages':{'basic':999,'standard':1999,'premium':3499},'checklist_key':'ac_service'},
    'denting':     {'name':'Denting & Painting','icon':'🎨','duration':'4h',
        'packages':{'basic':1499,'standard':2999,'premium':7999},'checklist_key':'default'},
    'tyres':       {'name':'Tyre & Wheel Service','icon':'⚙️','duration':'1.5h',
        'packages':{'basic':799,'standard':1299,'premium':2499},'checklist_key':'default'},
    'battery':     {'name':'Battery Replacement','icon':'🔋','duration':'1h',
        'packages':{'basic':1999,'standard':2999,'premium':4999},'checklist_key':'default'},
    'detailing':   {'name':'Car Detailing','icon':'✨','duration':'5h',
        'packages':{'basic':2999,'standard':4999,'premium':9999},'checklist_key':'default'},
    'inspection':  {'name':'Pre-purchase Inspection','icon':'🔍','duration':'2h',
        'packages':{'basic':799,'standard':1299,'premium':2499},'checklist_key':'default'},
}

DEFAULT_CHECKLIST = {
    'car_service': ['Initial inspection & OBD scan','Engine oil drain & refill',
        'Oil filter replacement','Air filter cleaning','Brake pads & disc inspection',
        'Tyre pressure check & N₂ inflation','Battery health test','30-point safety report'],
    'ac_service':  ['AC pressure check','Refrigerant gas top-up (R134a)','Condenser cleaning',
        'Cabin filter change','AC vent sanitization','Post-service cooling test'],
    'default':     ['Initial inspection','Main service task','Quality check','Final report'],
}


# ═══════════════════════════════════════════════════════════════
#  PUBLIC
# ═══════════════════════════════════════════════════════════════

def homeView(request):
    garages  = Garage.objects.filter(is_active=True, approval_status='approved').order_by('-wallet_balance')[:6]
    services = Service.objects.filter(is_active=True).order_by('order')[:8]
    total_garages   = Garage.objects.filter(is_active=True, approval_status='approved').count()
    total_bookings  = Booking.objects.filter(payment_status='paid').count()
    total_mechanics = User.objects.filter(role='mechanic').count()
    top_reviews     = Review.objects.select_related('booking__garage','booking__customer').order_by('-rating','-created_at')[:6]

    # Dynamic advance fee range across all active garages
    from django.db.models import Min, Max
    fee_range = Garage.objects.filter(
        is_active=True, approval_status='approved'
    ).aggregate(min_fee=Min('advance_fee'), max_fee=Max('advance_fee'))
    min_fee = int(fee_range['min_fee'] or 600)
    max_fee = int(fee_range['max_fee'] or 600)
    if min_fee == max_fee:
        advance_fee_display = f'₹{min_fee}'
    else:
        advance_fee_display = f'₹{min_fee}–₹{max_fee}'

    return render(request, 'core/home.html', {
        'garages':              garages,
        'services':             services,
        'total_garages':        total_garages,
        'total_bookings':       total_bookings,
        'total_mechanics':      total_mechanics,
        'top_reviews':          top_reviews,
        'advance_fee_display':  advance_fee_display,
        'min_fee':              min_fee,
        'max_fee':              max_fee,
    })


def testEmailView(request):
    """Visit /test-email/ while logged in to test if email is working."""
    if not request.user.is_authenticated:
        return redirect('login')
    from django.core.mail import send_mail
    from django.conf import settings
    to = request.user.email
    try:
        send_mail(
            subject='eGarage — Email Test ✅',
            message=f'Hello {request.user.name},\n\nYour eGarage email is working correctly!\n\nIf you received this, emails will work for booking confirmations too.\n\neGarage Team',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
        from django.http import HttpResponse
        return HttpResponse(f'<h2 style="font-family:sans-serif;padding:40px;">✅ Test email sent to <strong>{to}</strong>! Check your inbox (and spam folder).<br><br><a href="/">← Home</a></h2>')
    except Exception as e:
        from django.http import HttpResponse
        return HttpResponse(f'<h2 style="font-family:sans-serif;padding:40px;color:red;">❌ Email failed: {e}<br><br>Check your Gmail App Password in settings.py.<br><br><a href="/">← Home</a></h2>')


def serviceDetailView(request, slug):
    svc = SERVICES_DATA.get(slug)
    if not svc:
        return redirect('home')
    return render(request, 'core/public/service_detail.html', {'svc': svc, 'slug': slug})


def garageFinderView(request):
    city = request.GET.get('city', '').strip()
    garages = Garage.objects.filter(is_active=True, approval_status='approved')
    if city:
        garages = garages.filter(city__icontains=city)
    individual_mechanics = IndividualMechanicProfile.objects.filter(
        status='approved'
    ).select_related('mechanic')
    cities = Garage.objects.filter(
        is_active=True, approval_status='approved'
    ).values_list('city', flat=True).distinct()
    return render(request, 'core/public/garage_finder.html', {
        'garages': garages,
        'individual_mechanics': individual_mechanics,
        'cities': cities,
        'selected_city': city,
    })


def checkEmailView(request):
    email  = request.GET.get('email', '')
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD (role router)
# ═══════════════════════════════════════════════════════════════

@login_required
def dashboardView(request):
    user = request.user

    if user.is_super_admin or (user.role == 'admin' and user.admin_approved):
        return redirect('admin_panel')

    if user.role == 'owner' or not user.role:
        today    = timezone.now().date()
        bookings = Booking.objects.filter(customer=user).order_by('-created_at')
        vehicles = Vehicle.objects.filter(owner=user)
        active   = bookings.filter(
            status__in=['confirmed','picked_up','at_garage','in_progress','quality_check']
        ).select_related('service','garage','job').first()

        upcoming = bookings.filter(
            scheduled_date__gte=today,
            status__in=['confirmed','picked_up']
        ).select_related('service','garage','mechanic').order_by('scheduled_date','scheduled_slot')

        from django.db.models import Q as _Q2
        total_spent = bookings.filter(
            _Q2(payment_status='paid') | _Q2(final_paid=True)
        ).aggregate(t=Sum('final_bill'))['t'] or             bookings.filter(payment_status='paid').aggregate(t=Sum('advance_amount'))['t'] or 0

        # Unreviewed completed bookings
        needs_rating = bookings.filter(
            status='delivered', final_paid=True
        ).exclude(review__isnull=False).count()

        return render(request, 'core/owner/dashboard.html', {
            'recent_bookings':  bookings.select_related('service','garage','job')[:5],
            'upcoming_bookings':upcoming[:3],
            'total_bookings':   bookings.count(),
            'total_vehicles':   vehicles.count(),
            'vehicles':         vehicles[:3],
            'active_booking':   active,
            'total_spent':      float(total_spent),
            'needs_rating':     needs_rating,
            'unread_notifs':    Notification.objects.filter(user=user, is_read=False).count(),
        })

    elif user.role == 'mechanic':
        today       = timezone.now().date()
        week_start  = today - timezone.timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        try:
            profile = user.mechanic_profile
        except Exception:
            profile = None
        try:
            ind_profile = user.individual_profile
        except Exception:
            ind_profile = None

        jobs = Job.objects.filter(mechanic=user).select_related(
            'booking','booking__service','booking__vehicle','booking__customer'
        )

        # Real earnings from MechanicEarning
        earnings    = MechanicEarning.objects.filter(mechanic=user)
        week_earn   = float(earnings.filter(credited_at__date__gte=week_start
                        ).aggregate(t=Sum('earning_amount'))['t'] or 0)
        month_earn  = float(earnings.filter(credited_at__date__gte=month_start
                        ).aggregate(t=Sum('earning_amount'))['t'] or 0)
        today_earn  = float(earnings.filter(credited_at__date=today
                        ).aggregate(t=Sum('earning_amount'))['t'] or 0)

        # Jobs needing action (assigned but not accepted)
        pending_accept = jobs.filter(status='assigned').count()

        return render(request, 'core/mechanic/dashboard.html', {
            'today_jobs':       jobs.filter(booking__scheduled_date=today).order_by('booking__scheduled_slot'),
            'upcoming_jobs':    jobs.filter(booking__scheduled_date__gt=today,
                                    status__in=['assigned','accepted']).order_by('booking__scheduled_date')[:3],
            'pending_jobs':     jobs.filter(status__in=['assigned','in_progress']).count(),
            'pending_accept':   pending_accept,
            'done_today':       jobs.filter(status__in=['completed','verified'], completed_at__date=today).count(),
            'rating':           Review.objects.filter(booking__mechanic=user).aggregate(avg=Avg('rating'))['avg'],
            'week_earn':        week_earn,
            'month_earn':       month_earn,
            'today_earn':       today_earn,
            'mechanic_profile': profile,
            'individual_profile': ind_profile,
        })

    elif user.role == 'manager':
        garage = Garage.objects.filter(manager=user).first()
        today  = timezone.now().date()

        # Pending mechanic requests for this garage
        pending_mechanic_requests = 0
        if garage:
            pending_mechanic_requests = MechanicRequest.objects.filter(
                garage=garage, status='pending'
            ).count()

        return render(request, 'core/manager/dashboard.html', {
            'garage':          garage,
            'garage_approved': garage.approval_status == 'approved' if garage else False,
            'today_bookings':  Booking.objects.filter(
                garage=garage, scheduled_date=today
            ).count() if garage else 0,
            'month_revenue':   Booking.objects.filter(
                garage=garage,
                scheduled_date__month=today.month,
                scheduled_date__year=today.year,
                status='delivered'
            ).aggregate(total=Sum('final_price'))['total'] or 0 if garage else 0,
            'team_count':      MechanicProfile.objects.filter(
                garage=garage
            ).count() if garage else 0,
            'mechanics':       MechanicProfile.objects.filter(
                garage=garage
            ).select_related('mechanic')[:5] if garage else [],
            'pending_mechanic_requests': pending_mechanic_requests,
            'recent_bookings': Booking.objects.filter(garage=garage).select_related(
                'customer','service','mechanic','vehicle'
            ).order_by('-created_at')[:8] if garage else [],
            'jobs_to_verify':  Job.objects.filter(
                booking__garage=garage, status='completed', manager_verified=False
            ).select_related('booking','booking__service','booking__customer','mechanic'
            ).order_by('-completed_at') if garage else [],
            'pending_leaves':  MechanicLeaveRequest.objects.filter(
                garage=garage, status='pending'
            ).select_related('mechanic').order_by('from_date') if garage else [],
            'wallet_balance':  garage.wallet_balance if garage else 0,
            'recent_transactions': GarageTransaction.objects.filter(
                garage=garage
            ).order_by('-created_at')[:5] if garage else [],
        })

    return redirect('home')


# ═══════════════════════════════════════════════════════════════
#  BOOKING FLOW
# ═══════════════════════════════════════════════════════════════

@login_required
def garageServicesApiView(request, garage_id):
    """Returns services + prices for a specific garage — called by booking form."""
    try:
        garage = Garage.objects.get(pk=garage_id, is_active=True, approval_status='approved')
    except Garage.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Garage not found'}, status=404)

    services = []

    # 1. Global services with garage-specific overrides
    for gs in GarageService.objects.filter(
        garage=garage, is_offered=True
    ).select_related('service').order_by('service__order'):
        svc = gs.service
        services.append({
            'id':           svc.pk,
            'slug':         svc.slug,
            'name':         svc.name,
            'description':  svc.description,
            'icon':         svc.icon_emoji,
            'category':     svc.category,
            'duration':     float(gs.duration_hours or svc.duration_hours),
            'price_basic':    float(gs.price_basic    or svc.price_basic),
            'price_standard': float(gs.price_standard or svc.price_standard),
            'price_premium':  float(gs.price_premium  or svc.price_premium),
            'notes':        gs.notes,
            'is_custom':    False,
        })

    # 2. If no garage-specific overrides, fall back to all active global services
    if not services:
        for svc in Service.objects.filter(is_active=True).order_by('order'):
            services.append({
                'id':           svc.pk,
                'slug':         svc.slug,
                'name':         svc.name,
                'description':  svc.description,
                'icon':         svc.icon_emoji,
                'category':     svc.category,
                'duration':     float(svc.duration_hours),
                'price_basic':    float(svc.price_basic),
                'price_standard': float(svc.price_standard),
                'price_premium':  float(svc.price_premium),
                'notes':        '',
                'is_custom':    False,
            })

    # 3. Custom services this garage created
    for cs in GarageCustomService.objects.filter(garage=garage, is_active=True):
        services.append({
            'id':           f'custom_{cs.pk}',
            'slug':         f'custom-{cs.pk}',
            'name':         cs.name,
            'description':  cs.description,
            'icon':         cs.icon_emoji,
            'category':     cs.category,
            'duration':     float(cs.duration_hours),
            'price_basic':    float(cs.price_basic),
            'price_standard': float(cs.price_standard),
            'price_premium':  float(cs.price_premium),
            'notes':        '',
            'is_custom':    True,
        })

    return JsonResponse({
        'ok':          True,
        'garage_id':   garage.pk,
        'garage_name': garage.name,
        'advance_fee': float(garage.advance_fee),
        'services':    services,
    })


@login_required
def bookingView(request):
    city     = request.GET.get('city', request.user.city or '')
    garages  = Garage.objects.filter(is_active=True, approval_status='approved')
    if city:
        garages = garages.filter(city__icontains=city)
    services = Service.objects.filter(is_active=True).order_by('order')
    vehicles = Vehicle.objects.filter(owner=request.user)
    ind_mechs = IndividualMechanicProfile.objects.filter(status='approved').select_related('mechanic')
    if city:
        ind_mechs = [m for m in ind_mechs if city.lower() in m.service_cities.lower()]

    return render(request, 'core/owner/booking.html', {
        'garages':      garages,
        'services':     services,
        'vehicles':     vehicles,
        'ind_mechanics': ind_mechs,
        'razorpay_key': settings.RAZORPAY_KEY_ID,
        'selected_city': city,
        'cities': Garage.objects.filter(
            is_active=True, approval_status='approved'
        ).values_list('city', flat=True).distinct(),
    })


@login_required
@require_POST
def bookingConfirmView(request):
    user = request.user
    data = request.POST

    service_slug = data.get('service_slug', 'car-service')
    service_id   = data.get('service_id', '')
    package      = data.get('package', 'standard')
    service_type = data.get('service_type', 'garage')

    # Try to get real DB service and price (garage-specific first, then global)
    db_service   = None
    base_price   = 0
    garage_id    = data.get('garage_id')

    # Try by service_id (from dynamic API selection)
    if service_id:
        try:
            db_service = Service.objects.get(pk=int(service_id))
        except (Service.DoesNotExist, ValueError):
            pass

    # Fallback: try by slug
    if not db_service:
        db_service = Service.objects.filter(slug=service_slug).first()

    if db_service:
        # Try garage-specific price first
        if garage_id:
            try:
                from .models import GarageService as GS
                gs_obj = GS.objects.get(garage_id=garage_id, service=db_service)
                price_map = {
                    'basic':    float(gs_obj.price_basic    or db_service.price_basic),
                    'standard': float(gs_obj.price_standard or db_service.price_standard),
                    'premium':  float(gs_obj.price_premium  or db_service.price_premium),
                }
                base_price = price_map.get(package, price_map['standard'])
            except Exception:
                base_price = float(db_service.get_price(package))
        else:
            base_price = float(db_service.get_price(package))

        # Also try custom service
        if not base_price:
            try:
                from .models import GarageCustomService as GCS
                cs = GCS.objects.get(pk=int(service_id), garage_id=garage_id)
                base_price = float(cs.get_price(package))
                db_service = None  # Custom service, not global
            except Exception:
                pass

    # Always define svc_data for use in notifications/emails
    svc_data = SERVICES_DATA.get(service_slug, SERVICES_DATA.get('car-service', {
        'name': db_service.name if db_service else service_slug,
        'packages': {'standard': 999}
    }))
    # If db_service exists, override the name
    if db_service:
        svc_data = dict(svc_data)
        svc_data['name'] = db_service.name

    # Final fallback to SERVICES_DATA price
    if not base_price:
        base_price = svc_data['packages'].get(package, 999)

    # Pickup/home visit charge
    pickup_charge = 0
    if service_type == 'home' or package == 'premium':
        pickup_charge = float(data.get('pickup_charge', 0) or 0)

    # Coupon
    discount = 0
    coupon   = None
    coupon_code = data.get('coupon_code', '').strip().upper()
    if coupon_code:
        try:
            coupon_obj = Coupon.objects.get(code=coupon_code, is_active=True)
            discount   = float(coupon_obj.calculate_discount(base_price))
            coupon     = coupon_obj
        except Coupon.DoesNotExist:
            pass

    # Vehicle
    vehicle = None
    vid = data.get('vehicle_id')
    if vid:
        try:
            vehicle = Vehicle.objects.get(pk=vid, owner=user)
        except Vehicle.DoesNotExist:
            pass

    # Garage
    garage = None
    gid = data.get('garage_id')
    if gid:
        try:
            garage = Garage.objects.get(pk=gid, is_active=True, approval_status='approved')
        except Garage.DoesNotExist:
            pass
    if not garage and service_type == 'garage':
        garage = Garage.objects.filter(is_active=True, approval_status='approved').first()

    # Individual mechanic
    ind_mechanic = None
    imid = data.get('individual_mechanic_id')
    if imid:
        try:
            ind_mechanic = IndividualMechanicProfile.objects.get(pk=imid, status='approved')
        except IndividualMechanicProfile.DoesNotExist:
            pass

    # Convert slot from "9:00 AM" → "09:00" format Django expects
    raw_slot = data.get('slot', '09:00')
    try:
        from datetime import datetime as _dt
        # Try 12-hour format first (e.g. "9:00 AM", "2:30 PM")
        slot_parsed = _dt.strptime(raw_slot.strip(), '%I:%M %p')
        scheduled_slot = slot_parsed.strftime('%H:%M')
    except (ValueError, AttributeError):
        try:
            # Already in 24-hour format (e.g. "09:00", "14:30")
            _dt.strptime(raw_slot.strip(), '%H:%M')
            scheduled_slot = raw_slot.strip()[:5]
        except (ValueError, AttributeError):
            scheduled_slot = '09:00'

    booking = Booking.objects.create(
        customer        = user,
        garage          = garage,
        service         = db_service or Service.objects.filter(slug=service_slug).first(),
        vehicle         = vehicle,
        individual_mechanic = ind_mechanic,
        package         = package,
        service_type    = service_type,
        base_price      = base_price,
        discount_amount = discount,
        pickup_charge   = pickup_charge,
        coupon          = coupon,
        scheduled_date  = data.get('date', timezone.now().date()),
        scheduled_slot  = scheduled_slot,
        customer_name   = data.get('name', user.name),
        customer_phone  = data.get('phone', user.phone or ''),
        customer_email  = data.get('email', user.email),
        pickup_address  = data.get('address', ''),
        pickup_lat      = data.get('pickup_lat') or None,
        pickup_lng      = data.get('pickup_lng') or None,
        pickup_required = service_type == 'home' or package == 'premium',
        notes           = data.get('notes', ''),
        status          = 'confirmed',
        payment_status  = 'pending',
        payment_method  = data.get('payment_method', 'cash'),
        # Use garage's configured advance fee, fallback to ₹600
        advance_amount  = garage.advance_fee if garage and hasattr(garage, 'advance_fee') else 600,
    )

    if coupon:
        Coupon.objects.filter(pk=coupon.pk).update(usage_count=coupon.usage_count + 1)

    create_notification(
        booking.customer,
        f'Booking {booking.reference} confirmed ✅',
        f'Your {svc_data["name"]} is booked for {booking.scheduled_date} at '
        f'{str(booking.scheduled_slot)[:5]}.',
        'booking', booking
    )

    # Notify garage manager
    if garage and garage.manager:
        create_notification(
            garage.manager,
            f'New booking: {booking.reference}',
            f'{booking.customer_name} booked {svc_data["name"]} for {booking.scheduled_date}.',
            'booking', booking
        )

    try:
        from .otp_utils import send_booking_confirmation
        send_booking_confirmation(booking)
    except Exception as e:
        logger.error(f'Booking confirmation email failed for {booking.reference}: {e}')

    # ── Auto-create Job and assign to an available mechanic ──
    try:
        assigned_mech = None
        if garage:
            # Find an available mechanic at this garage
            assigned_mech = User.objects.filter(
                mechanic_profile__garage=garage,
                mechanic_profile__status='approved',
                is_available=True,
                role='mechanic',
            ).first()

        job = Job.objects.create(
            booking  = booking,
            mechanic = assigned_mech,
            status   = 'assigned',
        )

        # Update booking.mechanic field too
        if assigned_mech:
            booking.mechanic = assigned_mech
            booking.save(update_fields=['mechanic'])
            create_notification(
                assigned_mech,
                f'🔧 New Job Assigned — {booking.reference}',
                f'{booking.customer_name} booked {booking.service.name if booking.service else "a service"} '
                f'for {booking.scheduled_date} at {str(booking.scheduled_slot)[:5]}. '
                f'Check your jobs dashboard.',
                'booking', booking
            )
            logger.info(f'Job #{job.pk} created and assigned to {assigned_mech.name} for {booking.reference}')
        else:
            logger.info(f'Job #{job.pk} created for {booking.reference} — no mechanic assigned yet')
    except Exception as e:
        logger.error(f'Job auto-create failed for {booking.reference}: {e}')

    request.session['pending_booking_ref'] = booking.reference

    # Payment type: 'full' = pay total now online, 'advance' = pay advance now, 'cash' = pay all at garage
    payment_type = data.get('payment_type', 'advance')

    if payment_type == 'cash':
        # Cash booking — mark confirmed, no advance required online
        booking.payment_method  = 'cash'
        booking.payment_type    = 'cash'
        booking.payment_status  = 'pending'  # will be marked paid when job completes
        booking.advance_paid    = False
        booking.save(update_fields=['payment_method', 'payment_type', 'payment_status', 'advance_paid'])
        return redirect(f'/booking/confirmed/?ref={booking.reference}&type=cash')
    elif payment_type == 'full':
        booking.payment_type = 'full'
        booking.save(update_fields=['payment_type'])
    else:
        booking.payment_type = 'advance'
        booking.save(update_fields=['payment_type'])

    return redirect("/booking/payment/")


@login_required
def bookingConfirmedView(request):
    ref = request.session.pop('pending_booking_ref', None) or request.GET.get('ref')
    if not ref:
        return redirect('bookings')
    booking = get_object_or_404(Booking, reference=ref, customer=request.user)
    # Cash booking — show confirmed without payment redirect
    is_cash = (booking.payment_method == 'cash' and getattr(booking, 'payment_type', '') == 'cash')
    if not is_cash and not booking.advance_paid and booking.payment_status == 'pending':
        request.session['pending_booking_ref'] = ref
        return redirect('payment')
    request.session['last_booking_ref'] = ref
    # Get job info for mechanic status
    job = None
    try:
        job = booking.job
    except Exception:
        pass
    return render(request, 'core/owner/booking_confirmed.html', {
        'booking': booking,
        'job':     job,
    })


@login_required
def paymentView(request):
    ref = request.session.get('pending_booking_ref')
    if not ref:
        return redirect('booking')
    booking = get_object_or_404(Booking, reference=ref, customer=request.user)
    return render(request, 'core/owner/payment.html', {
        'booking': booking,
    })


@login_required
@require_POST
def dummyPaymentSuccessView(request):
    """Handles advance ₹600 payment — marks advance paid, notifies everyone."""
    ref    = request.POST.get('ref') or request.session.get('pending_booking_ref', '')
    method = request.POST.get('method', 'upi')

    booking = get_object_or_404(Booking, reference=ref, customer=request.user)

    # Full pay vs advance pay
    is_full_pay = getattr(booking, 'payment_type', 'advance') == 'full'
    advance = float(booking.advance_amount)
    total   = float(booking.final_price) if booking.final_price else float(booking.base_price or 0) - float(booking.discount_amount or 0)

    booking.advance_paid    = True
    booking.advance_method  = method
    booking.advance_paid_at = timezone.now()
    booking.payment_status  = 'paid'
    booking.payment_method  = method
    if booking.status in ('pending', 'confirmed'):
        booking.status = 'confirmed'

    if is_full_pay:
        # Full payment — also mark final paid so no balance screen
        booking.final_paid    = True
        booking.final_paid_at = timezone.now()
        booking.final_method  = method
        booking.final_bill    = total
        booking.balance_due   = 0
        booking.save(update_fields=['advance_paid','advance_method','advance_paid_at',
                                     'payment_status','payment_method','status',
                                     'final_paid','final_paid_at','final_method',
                                     'final_bill','balance_due'])
    else:
        booking.save(update_fields=['advance_paid','advance_method','advance_paid_at',
                                     'payment_status','payment_method','status'])

    method_display = {'upi':'UPI','card':'Card','cash':'Cash'}.get(method, method.upper())

    # Record advance in garage transactions + credit wallet
    if booking.garage:
        from django.db.models import F
        Garage.objects.filter(pk=booking.garage.pk).update(
            wallet_balance=F('wallet_balance') + booking.advance_amount
        )
        GarageTransaction.objects.create(
            garage      = booking.garage,
            booking     = booking,
            type        = 'credit',
            amount      = booking.advance_amount,
            description = f'Advance ₹{advance:.0f} for {booking.reference} via {method_display}',
        )

    # Notify customer
    create_notification(
        booking.customer,
        f'✅ Advance ₹{advance:.0f} paid — {booking.reference}',
        f'Booking confirmed! Advance of ₹{advance:.0f} paid via {method_display}. '
        f'You will pay the remaining balance at the garage after service.',
        'booking', booking
    )

    # Notify manager
    if booking.garage and booking.garage.manager:
        create_notification(
            booking.garage.manager,
            f'💳 Advance received — {booking.reference}',
            f'{booking.customer_name} paid ₹{advance:.0f} advance for '
            f'{booking.service.name if booking.service else "service"} on {booking.scheduled_date}.',
            'booking', booking
        )

    # Notify mechanic
    if booking.mechanic:
        create_notification(
            booking.mechanic,
            f'🔧 New Job — {booking.reference}',
            f'{booking.customer_name} confirmed booking. '
            f'Service: {booking.service.name if booking.service else "—"} on {booking.scheduled_date}.',
            'booking', booking
        )

    # Send booking confirmation email
    try:
        from .otp_utils import send_booking_confirmation
        send_booking_confirmation(booking)
        logger.info(f'Confirmation email sent for {booking.reference}')
    except Exception as e:
        logger.error(f'Email failed for {booking.reference}: {e}')

    # Send payment receipt email
    try:
        from .otp_utils import send_payment_confirmation
        send_payment_confirmation(booking)
        logger.info(f'Payment receipt email sent for {booking.reference}')
    except Exception as e:
        logger.error(f'Payment email failed for {booking.reference}: {e}')

    request.session['pending_booking_ref'] = booking.reference
    return redirect(f'/booking/confirmed/?ref={booking.reference}')


@login_required
@require_POST
def paymentSuccessView(request):
    ref     = request.session.get('pending_booking_ref', '')
    booking = get_object_or_404(Booking, reference=ref, customer=request.user)
    razorpay_order_id   = request.POST.get('razorpay_order_id', '')
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_signature  = request.POST.get('razorpay_signature', '')
    key_secret = settings.RAZORPAY_KEY_SECRET.encode()
    msg        = f'{razorpay_order_id}|{razorpay_payment_id}'.encode()
    gen_sig    = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()
    if gen_sig == razorpay_signature:
        booking.razorpay_payment_id = razorpay_payment_id
        booking.razorpay_signature  = razorpay_signature
        booking.payment_status      = 'paid'
        booking.status              = 'confirmed'
        booking.save(update_fields=['razorpay_payment_id','razorpay_signature','payment_status','status'])
        request.session.pop('pending_booking_ref', None)
        request.session['pending_booking_ref'] = booking.reference
        return redirect('booking_confirmed')
    else:
        booking.payment_status = 'failed'
        booking.save(update_fields=['payment_status'])
        return redirect('payment_failed')


@login_required
def paymentFailedView(request):
    return render(request, 'core/owner/payment_failed.html')


@login_required
def balancePaymentView(request, ref):
    """Shows the remaining balance payment page for customer after service is done."""
    booking = get_object_or_404(Booking, reference=ref, customer=request.user)

    # Only show if job is completed/quality_check and balance not yet paid
    allowed = booking.status in ('quality_check', 'delivered') or (
        hasattr(booking, 'job') and booking.job.status in ('completed', 'verified', 'quality_check')
    )
    if booking.final_paid:
        return redirect(f'/bookings/{ref}/')

    return render(request, 'core/owner/pay_balance.html', {
        'booking': booking,
    })


@login_required
@require_POST
def balancePaymentDoneView(request, ref):
    """Dummy final balance payment — marks booking fully paid, releases wallet."""
    booking = get_object_or_404(Booking, reference=ref, customer=request.user)
    method  = request.POST.get('method', 'cash')

    if booking.final_paid:
        return redirect(f'/bookings/{ref}/')

    booking.final_paid      = True
    booking.final_paid_at   = timezone.now()
    booking.final_method    = method
    booking.status          = 'delivered'
    booking.payment_status  = 'paid'   # Mark fully paid so total_spent includes it
    booking.save(update_fields=['final_paid', 'final_paid_at', 'final_method', 'status', 'payment_status'])

    # Always record final payment as garage transaction (cash or online)
    if booking.garage:
        try:
            from django.db.models import F
            balance = float(booking.balance_due) if booking.balance_due else 0
            if balance > 0:
                GarageTransaction.objects.create(
                    garage=booking.garage, booking=booking, type='credit',
                    amount=balance,
                    description=f'Balance ₹{balance:.0f} paid via {method} — {booking.reference}',
                )
        except Exception as e:
            logger.error(f'Balance transaction record failed: {e}')

    # Release wallet
    try:
        job = booking.job
        if not job.wallet_released:
            from django.db.models import F
            Garage.objects.filter(pk=booking.garage.pk).update(
                wallet_balance=F('wallet_balance') + booking.final_bill
            )
            GarageTransaction.objects.create(
                garage=booking.garage, booking=booking, type='credit',
                amount=booking.final_bill,
                description=f'Final settlement — {booking.reference}',
            )
            job.wallet_released    = True
            job.wallet_released_at = timezone.now()
            job.save(update_fields=['wallet_released', 'wallet_released_at'])

            # Credit mechanic earnings
            if job.mechanic:
                try:
                    profile = job.mechanic.mechanic_profile
                    pct     = float(profile.commission_pct) if profile.salary_type == 'commission' else 40
                except Exception:
                    pct = 40
                earning = round(float(booking.final_bill) * pct / 100, 2)
                MechanicEarning.objects.get_or_create(
                    job=job,
                    defaults={
                        'mechanic':       job.mechanic,
                        'garage':         booking.garage,
                        'gross_amount':   booking.final_bill,
                        'commission_pct': pct,
                        'earning_amount': earning,
                    }
                )
                create_notification(job.mechanic,
                    f'💰 ₹{earning:.0f} credited — {booking.reference}',
                    f'Job complete and payment received. ₹{earning:.0f} added to your earnings.',
                    'account')
    except Exception as e:
        logger.error(f'Wallet release failed for {booking.reference}: {e}')

    # Notify manager
    if booking.garage and booking.garage.manager:
        create_notification(
            booking.garage.manager,
            f'💳 Final payment received — {booking.reference}',
            f'{booking.customer_name} paid ₹{float(booking.balance_due):.0f} balance '
            f'via {method}. Total: ₹{float(booking.final_bill):.0f}.',
            'booking', booking
        )

    # Notify customer
    create_notification(
        booking.customer,
        f'🎉 Service complete! — {booking.reference}',
        f'Thank you! Your service is complete. '
        f'Total paid: ₹{float(booking.final_bill):.0f}. Rate your experience!',
        'service', booking
    )

    # Send final invoice email
    try:
        from .otp_utils import send_service_completed_email
        send_service_completed_email(booking, booking.job if hasattr(booking, 'job') else None)
    except Exception as e:
        logger.error(f'Final invoice email failed: {e}')

    return redirect(f'/bookings/{ref}/')


@login_required
def downloadInvoiceView(request, ref):
    booking = get_object_or_404(Booking, reference=ref)
    if booking.customer != request.user and not request.user.is_staff:
        if request.user.role not in ('mechanic','manager','admin'):
            return redirect('bookings')
    try:
        from .invoice import generate_invoice_pdf
        pdf_bytes = generate_invoice_pdf(booking)
        response  = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="eGarage-Invoice-{ref}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f'Could not generate invoice: {e}')
        return redirect('bookings')


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER — BOOKINGS, TRACK, RATE
# ═══════════════════════════════════════════════════════════════

@login_required
def bookingsView(request):
    user = request.user

    if user.role == 'manager':
        # Manager sees all bookings for their garage
        garage = Garage.objects.filter(manager=user).first()
        if garage:
            bookings = Booking.objects.filter(garage=garage).select_related(
                'service', 'garage', 'vehicle', 'mechanic', 'customer'
            ).order_by('-created_at')
        else:
            bookings = Booking.objects.none()
        return render(request, 'core/owner/bookings.html', {
            'bookings': bookings,
            'is_manager_view': True,
            'garage': garage,
        })

    elif user.role in ('admin',) or user.is_super_admin:
        # Admin sees all bookings
        bookings = Booking.objects.all().select_related(
            'service', 'garage', 'vehicle', 'mechanic', 'customer'
        ).order_by('-created_at')
        return render(request, 'core/owner/bookings.html', {
            'bookings': bookings,
            'is_admin_view': True,
        })

    elif user.role == 'mechanic':
        # Mechanic sees all bookings assigned to them
        bookings = Booking.objects.filter(mechanic=user).select_related(
            'service', 'garage', 'vehicle', 'customer', 'job'
        ).order_by('-created_at')
        return render(request, 'core/owner/bookings.html', {
            'bookings': bookings,
            'is_mechanic_view': True,
        })

    else:
        # Customer sees their own bookings
        bookings = Booking.objects.filter(customer=user).select_related(
            'service', 'garage', 'vehicle', 'mechanic', 'job'
        ).order_by('-created_at')

        # Search + filter
        q      = request.GET.get('q', '').strip()
        status = request.GET.get('status', '').strip()
        if q:
            from django.db.models import Q
            bookings = bookings.filter(
                Q(reference__icontains=q) |
                Q(service__name__icontains=q) |
                Q(garage__name__icontains=q)
            )
        if status:
            bookings = bookings.filter(status=status)

        from django.db.models import Q
        # Include both online-paid and cash-completed bookings in total spent
        total_spent = Booking.objects.filter(
            customer=user
        ).filter(
            Q(payment_status='paid') | Q(final_paid=True) | Q(status='delivered')
        ).aggregate(
            t=Sum('final_bill')
        )['t'] or Booking.objects.filter(
            customer=user, payment_status='paid'
        ).aggregate(t=Sum('advance_amount'))['t'] or 0

        upcoming = bookings.filter(status__in=['confirmed','picked_up']).count()
        active   = bookings.filter(status__in=['in_progress','at_garage','quality_check']).count()
        completed= bookings.filter(status='delivered').count()

        return render(request, 'core/owner/bookings.html', {
            'bookings':    bookings,
            'total_spent': float(total_spent),
            'upcoming_count':  upcoming,
            'active_count':    active,
            'completed_count': completed,
            'q':           q,
            'status':      status,
        })


@login_required
def bookingDetailView(request, ref):
    user = request.user
    if user.role == 'manager':
        garage = Garage.objects.filter(manager=user).first()
        booking = get_object_or_404(
            Booking.objects.select_related('service','garage','vehicle','mechanic','coupon'),
            reference=ref, garage=garage
        )
    elif user.role in ('admin',) or getattr(user, 'is_super_admin', False):
        booking = get_object_or_404(
            Booking.objects.select_related('service','garage','vehicle','mechanic','coupon'),
            reference=ref
        )
    else:
        booking = get_object_or_404(
            Booking.objects.select_related('service','garage','vehicle','mechanic','coupon'),
            reference=ref, customer=user
        )
    return render(request, 'core/owner/track.html', {
        'booking': booking,
        'status_steps': [
            ('confirmed',     'Confirmed',   '✅'),
            ('picked_up',     'Picked Up',   '🚗'),
            ('at_garage',     'At Garage',   '🏢'),
            ('in_progress',   'In Progress', '🔧'),
            ('quality_check', 'QC',          '🔍'),
            ('delivered',     'Delivered',   '🎉'),
        ],
        'current_step': ['confirmed','picked_up','at_garage','in_progress','quality_check','delivered'].index(booking.status) if booking.status in ['confirmed','picked_up','at_garage','in_progress','quality_check','delivered'] else 0,
    })


@login_required
def trackView(request):
    ref     = request.GET.get('ref')
    booking = None
    live_loc = None

    if ref:
        try:
            booking = Booking.objects.select_related(
                'service','garage','vehicle','mechanic','live_location'
            ).get(reference=ref, customer=request.user)
        except Booking.DoesNotExist:
            pass

    if not booking:
        booking = Booking.objects.filter(
            customer=request.user,
            status__in=['confirmed','picked_up','at_garage','in_progress','quality_check']
        ).select_related('service','garage','vehicle','mechanic').first()

    if booking:
        try:
            live_loc = booking.live_location
        except Exception:
            pass

    status_steps = [
        ('confirmed',     'Booking Confirmed', '✅'),
        ('picked_up',     'Vehicle Picked Up', '🚗'),
        ('at_garage',     'At Garage', '🏢'),
        ('in_progress',   'Service In Progress', '🔧'),
        ('quality_check', 'Quality Check', '🔍'),
        ('delivered',     'Delivered', '🎉'),
    ]
    current_step = 0
    if booking:
        for i, (k, _, _) in enumerate(status_steps):
            if booking.status == k:
                current_step = i
                break

    return render(request, 'core/owner/track.html', {
        'booking':      booking,
        'live_location': live_loc,
        'status_steps': status_steps,
        'current_step': current_step,
    })


@login_required
def bookingStatusView(request, ref):
    booking  = get_object_or_404(Booking, reference=ref, customer=request.user)
    job_data = {}
    live_data = {}
    try:
        job  = booking.job
        done, total = job.checklist_progress
        job_data = {'status': job.status, 'checklist': {'done': done, 'total': total,
                    'pct': int(done/total*100) if total else 0}}
    except Exception:
        pass
    try:
        loc = booking.live_location
        live_data = {'lat': float(loc.lat), 'lng': float(loc.lng),
                     'speed': float(loc.speed_kmh), 'heading': loc.heading}
    except Exception:
        pass

    return JsonResponse({
        'ref':      booking.reference,
        'status':   booking.status,
        'mechanic': booking.mechanic.name if booking.mechanic else None,
        'mechanic_phone': booking.mechanic.phone if booking.mechanic else None,
        'job':      job_data,
        'live':     live_data,
    })


@login_required
def rateServiceView(request, ref):
    booking = get_object_or_404(Booking, reference=ref, customer=request.user)
    if booking.status != 'delivered':
        messages.info(request, 'You can rate after service is delivered.')
        return redirect('bookings')
    if Review.objects.filter(booking=booking).exists():
        messages.info(request, 'Already rated.')
        return redirect('bookings')
    if request.method == 'POST':
        rating = int(request.POST.get('rating', 0))
        text   = request.POST.get('text', '').strip()
        if 1 <= rating <= 5:
            Review.objects.create(
                booking=booking, rating=rating, text=text,
                mechanic_rating = int(request.POST.get('mechanic_rating', rating)),
                service_rating  = int(request.POST.get('service_rating', rating)),
                punctuality     = int(request.POST.get('punctuality', rating)),
                cleanliness     = int(request.POST.get('cleanliness', rating)),
            )
            if booking.mechanic:
                create_notification(booking.mechanic,
                    f'New {rating}★ review', text[:100] or 'Rated.', 'service', booking)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True})
            messages.success(request, '🌟 Thank you for your review!')
            return redirect('bookings')
    return render(request, 'core/owner/rate_service.html', {'booking': booking})


# ═══════════════════════════════════════════════════════════════
#  EMERGENCY
# ═══════════════════════════════════════════════════════════════

@login_required
def emergencyView(request):
    vehicles = Vehicle.objects.filter(owner=request.user)
    active = EmergencyRequest.objects.filter(
        customer=request.user
    ).exclude(status='resolved').exclude(status='cancelled').first()

    if request.method == 'POST' and not active:
        issue    = request.POST.get('issue_type', 'breakdown')
        desc     = request.POST.get('description', '')
        address  = request.POST.get('location_address', '')
        lat      = request.POST.get('lat') or None
        lng      = request.POST.get('lng') or None
        city     = request.POST.get('city', request.user.city)
        vehicle_id = request.POST.get('vehicle_id')
        vehicle  = None
        if vehicle_id:
            try:
                vehicle = Vehicle.objects.get(pk=vehicle_id, owner=request.user)
            except Vehicle.DoesNotExist:
                pass

        er = EmergencyRequest.objects.create(
            customer=request.user,
            vehicle=vehicle,
            issue_type=issue,
            description=desc,
            location_address=address,
            lat=lat, lng=lng, city=city,
        )

        # Notify available mechanics in area
        mechs = User.objects.filter(role='mechanic', is_available=True, city__icontains=city)
        for m in mechs[:10]:
            create_notification(m,
                f'🚨 Emergency Request — {er.get_issue_type_display()}',
                f'{address}. Customer: {request.user.name} · {request.user.phone}',
                'emergency')

        messages.success(request, '🚨 Emergency request sent! A mechanic will contact you shortly.')
        return redirect('emergency')

    recent_requests = EmergencyRequest.objects.filter(
        customer=request.user
    ).order_by('-created_at')[:5]

    return render(request, 'core/owner/emergency.html', {
        'vehicles':        vehicles,
        'active_request':  active,
        'recent_requests': recent_requests,
    })


@login_required
@require_POST
def acceptEmergencyView(request, pk):
    """Mechanic accepts an emergency request."""
    if request.user.role != 'mechanic' and not request.user.is_individual:
        return JsonResponse({'ok': False, 'error': 'Only mechanics can accept.'})
    try:
        er = EmergencyRequest.objects.get(pk=pk, status='open')
        er.assigned_mechanic = request.user
        er.status = 'assigned'
        er.save(update_fields=['assigned_mechanic','status'])
        create_notification(er.customer,
            f'🔧 Mechanic assigned: {request.user.name}',
            f'{request.user.name} ({request.user.phone}) is on the way to help you.',
            'emergency')
        return JsonResponse({'ok': True, 'mechanic': request.user.name})
    except EmergencyRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Request not available.'})


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER — VEHICLES
# ═══════════════════════════════════════════════════════════════

@login_required
def vehiclesView(request):
    vehicles = Vehicle.objects.filter(owner=request.user)
    return render(request, 'core/owner/vehicles.html', {'vehicles': vehicles})


@login_required
@require_POST
def addVehicleView(request):
    try:
        data = json.loads(request.body)
        is_json = True
    except Exception:
        data = request.POST
        is_json = False
    v = Vehicle.objects.create(
        owner               = request.user,
        type                = data.get('type', 'car'),
        brand               = data.get('brand', '').strip(),
        model_name          = data.get('model', '').strip(),
        variant             = data.get('variant', '').strip(),
        registration_number = data.get('reg', '').strip().upper(),
        year                = data.get('year') or None,
        fuel_type           = data.get('fuel', 'petrol'),
        colour              = data.get('colour', '').strip(),
        odometer            = data.get('odometer', 0) or 0,
        is_primary          = not Vehicle.objects.filter(owner=request.user).exists(),
    )
    if is_json:
        return JsonResponse({'success': True, 'id': v.pk, 'name': f'{v.brand} {v.model_name}'})
    messages.success(request, f'✅ {v.brand} {v.model_name} added successfully!')
    return redirect('vehicles')


@login_required
@require_POST
def deleteVehicleView(request, pk):
    v = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    name = f'{v.brand} {v.model_name}'
    v.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
        return JsonResponse({'success': True})
    messages.success(request, f'✅ {name} removed.')
    return redirect('vehicles')


@login_required
@require_POST
def setPrimaryVehicle(request, pk):
    Vehicle.objects.filter(owner=request.user).update(is_primary=False)
    v = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    v.is_primary = True
    v.save(update_fields=['is_primary'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
        return JsonResponse({'success': True})
    messages.success(request, f'✅ {v.brand} {v.model_name} set as primary vehicle.')
    return redirect('vehicles')


@login_required
def vehicleConditionView(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    next_url = request.GET.get('next') or request.POST.get('next') or 'vehicles'

    if request.method == 'POST':
        from django.core.files.storage import default_storage
        saved = 0
        photo_fields = ['plate','front','rear','left','right','dashboard','damage','tyres','extra']
        for field in photo_fields:
            photo_file = request.FILES.get(f'photo_{field}')
            if photo_file:
                ext  = photo_file.name.rsplit('.', 1)[-1].lower()
                path = f'vehicle_conditions/{vehicle.pk}/{field}.{ext}'
                if default_storage.exists(path):
                    default_storage.delete(path)
                default_storage.save(path, photo_file)
                saved += 1

        damage_notes = request.POST.get('damage_notes', '').strip()
        odometer     = request.POST.get('odometer', '').strip()
        if damage_notes:
            vehicle.damage_notes = damage_notes
        if odometer:
            try:
                vehicle.odometer = int(odometer)
            except ValueError:
                pass
        vehicle.condition_submitted = True
        vehicle.save()

        create_notification(
            request.user,
            'Vehicle condition report submitted ✅',
            f'{vehicle.brand} {vehicle.model_name} condition report saved with {saved} photo(s). '
            f'Your mechanic will review before service.',
            'service'
        )
        messages.success(request, f'✅ Condition report with {saved} photo(s) saved!')

        # Redirect to next URL (e.g. /booking/payment/) or vehicles page
        if next_url.startswith('/'):
            return redirect(next_url)
        return redirect(next_url)

    from django.core.files.storage import default_storage
    existing = {}
    for field in ['plate','front','rear','left','right','dashboard','damage','tyres']:
        for ext in ['jpg','jpeg','png','webp']:
            path = f'vehicle_conditions/{vehicle.pk}/{field}.{ext}'
            if default_storage.exists(path):
                existing[field] = default_storage.url(path)
                break

    default_condition_parts = [
        ('exterior','Exterior Body'), ('glass','Glass & Mirrors'),
        ('tyres','Tyres & Wheels'), ('interior','Interior'),
        ('engine','Engine Bay'), ('lights','Lights'),
        ('brakes','Brakes'), ('ac','AC System'), ('fuel','Fuel Level'),
    ]

    return render(request, 'core/owner/vehicle_condition.html', {
        'vehicle':         vehicle,
        'existing':        existing,
        'next_url':        next_url,
        'condition_parts': [],          # empty → template uses default_parts
        'default_parts':   default_condition_parts,
    })


# ═══════════════════════════════════════════════════════════════
#  PROFILE & PASSWORD
# ═══════════════════════════════════════════════════════════════

@login_required
def profileView(request):
    user = request.user
    if request.method == 'POST':
        if 'profile_photo' in request.FILES:
            user.profile_photo = request.FILES['profile_photo']
            user.save()
            messages.success(request, '✅ Profile photo updated!')
            return redirect('profile')
        if request.POST.get('action') == 'change_password':
            return changePasswordView(request)
        name  = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        city  = request.POST.get('city', '').strip()
        if name:
            user.name = name; user.phone = phone; user.city = city
            user.save()
            messages.success(request, '✅ Profile updated!')
        return redirect('profile')

    bookings = Booking.objects.filter(customer=user).select_related('service','garage')
    vehicles = Vehicle.objects.filter(owner=user)
    # For manager: pass garage info instead of vehicles
    garage = Garage.objects.filter(manager=user).first() if user.role == 'manager' else None
    mechanic_profile = None
    if user.role in ('mechanic',) or user.is_individual:
        try:
            mechanic_profile = user.mechanic_profile
        except Exception:
            pass
    return render(request, 'core/owner/profile.html', {
        'user':            user,
        'recent_bookings': bookings.order_by('-created_at')[:3],
        'all_bookings':    bookings.order_by('-created_at'),
        'vehicles':        vehicles,
        'total_bookings':  bookings.count(),
        'total_vehicles':  vehicles.count(),
        'garage':          garage,
        'mechanic_profile': mechanic_profile,
    })


@login_required
def changePasswordView(request):
    if request.method == 'POST':
        current  = request.POST.get('current_password', '')
        new_pass = request.POST.get('new_password', '')
        confirm  = request.POST.get('confirm_password', '')
        if not request.user.check_password(current):
            messages.error(request, '❌ Current password incorrect.')
        elif len(new_pass) < 8:
            messages.error(request, '❌ Minimum 8 characters.')
        elif new_pass != confirm:
            messages.error(request, '❌ Passwords do not match.')
        else:
            request.user.set_password(new_pass)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, '✅ Password changed!')
    return redirect('profile')


# ═══════════════════════════════════════════════════════════════
#  NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

@login_required
def notificationsView(request):
    # Handle clear all — permanently delete
    if request.method == 'POST' and request.POST.get('action') == 'clear_all':
        Notification.objects.filter(user=request.user).delete()
        messages.success(request, 'All notifications cleared.')
        return redirect('notifications')

    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread = notifs.filter(is_read=False).count()
    # Mark all as read when page is opened
    notifs.filter(is_read=False).update(is_read=True)
    today     = timezone.now().date()
    yesterday = today - timezone.timedelta(days=1)
    return render(request, 'core/shared/notifications.html', {
        'notifications': notifs,
        'unread_count':  unread,
        'today':         today,
        'yesterday':     yesterday,
    })


@login_required
@require_POST
def markNotificationRead(request):
    try:
        data = json.loads(request.body)
        if data.get('all'):
            # delete_all = permanently remove
            if data.get('delete'):
                Notification.objects.filter(user=request.user).delete()
            else:
                Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        elif data.get('id'):
            if data.get('delete'):
                Notification.objects.filter(pk=data['id'], user=request.user).delete()
            else:
                Notification.objects.filter(pk=data['id'], user=request.user).update(is_read=True)
    except Exception:
        pass
    return JsonResponse({'success': True})


# ═══════════════════════════════════════════════════════════════
#  COUPON VALIDATION
# ═══════════════════════════════════════════════════════════════

def validateCouponView(request):
    code  = request.GET.get('code', request.POST.get('code', '')).strip().upper()
    total = float(request.GET.get('total', request.POST.get('base_price', 0)) or 0)
    try:
        coupon = Coupon.objects.get(code=code, is_active=True)
        today  = timezone.now().date()
        if coupon.valid_from and coupon.valid_from > today:
            return JsonResponse({'valid': False, 'error': 'Coupon not active yet.'})
        if coupon.valid_till and coupon.valid_till < today:
            return JsonResponse({'valid': False, 'error': 'Coupon expired.'})
        if coupon.max_usage and coupon.usage_count >= coupon.max_usage:
            return JsonResponse({'valid': False, 'error': 'Usage limit reached.'})
        if total < float(coupon.min_order):
            return JsonResponse({'valid': False, 'error': f'Min order ₹{coupon.min_order:.0f} required.'})
        discount = float(coupon.calculate_discount(total))
        return JsonResponse({'valid': True, 'discount': round(discount, 2),
                             'final': round(max(0, total - discount), 2),
                             'message': f'🎉 ₹{discount:.0f} discount applied!'})
    except Coupon.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Invalid coupon code.'})


# ═══════════════════════════════════════════════════════════════
#  MECHANIC — JOBS, EARNINGS, SCHEDULE
# ═══════════════════════════════════════════════════════════════

@login_required
def mechanicJobsView(request):
    if request.user.role not in ('mechanic', 'admin') and not request.user.is_individual:
        return redirect('dashboard')
    today = timezone.now().date()
    jobs  = Job.objects.filter(mechanic=request.user).select_related(
        'booking','booking__service','booking__vehicle','booking__customer','booking__garage'
    ).order_by('booking__scheduled_date','booking__scheduled_slot')

    # Emergency requests for this mechanic's city
    emergency_requests = EmergencyRequest.objects.filter(
        status='open', city__icontains=request.user.city or ''
    ).order_by('-created_at')[:5]

    # ACTIVE = any job not done, regardless of scheduled date
    # (covers overdue / delayed jobs that are accepted or in progress)
    active_statuses = ['accepted','on_way','arrived','in_progress','on_hold','quality_check','issue_reported']
    active_jobs   = jobs.filter(status__in=active_statuses).order_by('booking__scheduled_date','booking__scheduled_slot')

    # TODAY = scheduled today, any non-completed status
    today_jobs    = jobs.filter(booking__scheduled_date=today).exclude(status__in=['completed','verified','declined'])

    # UPCOMING = future dates, not yet started  
    upcoming_jobs = jobs.filter(booking__scheduled_date__gt=today, status__in=['assigned','accepted']).order_by('booking__scheduled_date')

    # HISTORY = completed OR verified jobs
    past_jobs     = jobs.filter(status__in=['completed','verified']).order_by('-booking__scheduled_date')

    # PENDING = assigned but not accepted yet
    pending_accept = jobs.filter(status='assigned')

    return render(request, 'core/mechanic/jobs.html', {
        'active_jobs':     active_jobs,
        'today_jobs':      today_jobs,
        'upcoming_jobs':   upcoming_jobs,
        'past_jobs':       past_jobs,
        'all_jobs':        jobs,
        'pending_accept':  pending_accept,
        'pending_count':   pending_accept.count(),
        'active_count':    active_jobs.count(),
        'today':           today,
        'emergency_requests': emergency_requests,
    })


@login_required
def jobDetailView(request, job_id):
    if request.user.role not in ('mechanic', 'admin'):
        return redirect('dashboard')
    try:
        job = Job.objects.get(pk=int(job_id), mechanic=request.user)
    except (ValueError, Job.DoesNotExist):
        job = get_object_or_404(Job, booking__reference=job_id, mechanic=request.user)
    parts = job.parts.all()
    parts_total = sum((p.unit_cost or 0) * (p.quantity or 1) for p in parts)
    return render(request, 'core/mechanic/job_detail.html', {
        'job':         job,
        'booking':     job.booking,
        'checklist':   job.checklist_items.all().order_by('order'),
        'photos':      job.photos.all().order_by('category','uploaded_at'),
        'parts':           parts,
        'parts_total':     parts_total,
        'photo_categories': [('before','Before'),('during','During'),('after','After')],
    })


@login_required
@require_POST
def updateJobStatus(request, pk):
    job    = get_object_or_404(Job, pk=pk, mechanic=request.user)
    data   = json.loads(request.body)
    status = data.get('status')
    valid  = ['assigned','accepted','on_way','arrived','in_progress','on_hold',
               'quality_check','completed','issue_reported']
    if status not in valid:
        return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)

    job.status = status
    booking    = job.booking

    if status == 'accepted':
        booking.status = 'confirmed'
        booking.save(update_fields=['status'])
        create_notification(booking.customer,
            f'🔧 Mechanic accepted your job — {booking.reference}',
            f'{request.user.name} has accepted your service request and will be in touch soon.',
            'service', booking)

    elif status == 'on_way':
        booking.status = 'picked_up'
        booking.save(update_fields=['status'])
        create_notification(booking.customer,
            f'🚗 Mechanic is on the way — {booking.reference}',
            f'{request.user.name} is heading to you. They should arrive soon.',
            'service', booking)

    elif status == 'arrived':
        job.arrived_at = timezone.now()
        booking.status = 'at_garage'
        booking.save(update_fields=['status'])
        create_notification(booking.customer,
            f'🏢 Vehicle at garage — {booking.reference}',
            f'Your vehicle has arrived at {booking.garage.name if booking.garage else "the garage"}. Service will begin shortly.',
            'service', booking)

    elif status == 'in_progress':
        if not job.started_at:
            job.started_at = timezone.now()
        booking.status = 'in_progress'
        booking.save(update_fields=['status'])
        create_notification(booking.customer,
            f'🔧 Service started — {booking.reference}',
            f'{request.user.name} has begun working on your vehicle. You can track progress live.',
            'service', booking)

    elif status == 'quality_check':
        booking.status = 'quality_check'
        booking.save(update_fields=['status'])
        create_notification(booking.customer,
            f'🔍 Quality check in progress — {booking.reference}',
            f'Work is done! A senior technician is reviewing all tasks before handover.',
            'service', booking)

    elif status == 'completed':
        job.completed_at = timezone.now()
        booking.status = 'quality_check'
        booking.save(update_fields=['status'])
        # Notify customer
        create_notification(booking.customer,
            f'✅ Service complete — {booking.reference}',
            f'Your {booking.service.name if booking.service else "service"} is done! '
            f'Waiting for manager verification before delivery.',
            'service', booking)
        # Notify manager to verify and release payment
        if booking.garage and booking.garage.manager:
            create_notification(
                booking.garage.manager,
                f'⚡ Job completed — Verify to release payment — {booking.reference}',
                f'{request.user.name} marked job #{job.pk} as complete. '
                f'Review and verify to release ₹{float(booking.final_price):.0f} from escrow to your garage account.',
                'booking', booking)
        # Send completion email to customer
        try:
            from .otp_utils import send_service_completed_email
            send_service_completed_email(booking, job)
        except Exception as e:
            logger.error(f'Completion email failed for {booking.reference}: {e}')

    job.save()
    return JsonResponse({'success': True, 'status': job.status,
                         'booking_status': booking.status})


@login_required
@require_POST
def managerVerifyJobView(request, pk):
    """Manager verifies completed job → releases escrow payment to garage wallet."""
    if request.user.role not in ('manager', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    garage = Garage.objects.filter(manager=request.user).first()
    if not garage:
        return JsonResponse({'ok': False, 'error': 'No garage found'}, status=400)

    try:
        job     = Job.objects.get(pk=pk, booking__garage=garage, status='completed')
        booking = job.booking

        # Mark job verified
        job.manager_verified    = True
        job.manager_verified_at = timezone.now()
        job.verified_by         = request.user
        job.status              = 'verified'
        job.save()

        # Update booking to delivered
        booking.status = 'delivered'
        # If cash booking, mark as paid now (cash collected at service)
        if booking.payment_method == 'cash' and not booking.final_paid:
            booking.final_paid      = True
            booking.final_paid_at   = timezone.now()
            booking.final_method    = 'cash'
            booking.payment_status  = 'paid'
            booking.save(update_fields=['status', 'final_paid', 'final_paid_at', 'final_method', 'payment_status'])
            # Record cash transaction
            try:
                from django.db.models import F as _F
                GarageTransaction.objects.create(
                    garage=booking.garage, booking=booking, type='credit',
                    amount=booking.final_price,
                    description=f'Cash collected — {booking.reference} (₹{float(booking.final_price):.0f})',
                )
            except Exception as _e:
                logger.error(f'Cash transaction record failed: {_e}')
        else:
            booking.save(update_fields=['status'])

        # Release escrow — credit garage wallet
        if not job.wallet_released:
            from django.db.models import F
            Garage.objects.filter(pk=garage.pk).update(
                wallet_balance=F('wallet_balance') + booking.final_price
            )
            GarageTransaction.objects.create(
                garage      = garage,
                booking     = booking,
                type        = 'credit',
                amount      = booking.final_price,
                description = f'Escrow released — {booking.reference} verified by {request.user.name}',
            )
            job.wallet_released    = True
            job.wallet_released_at = timezone.now()
            job.save(update_fields=['wallet_released', 'wallet_released_at'])

            # ── Credit mechanic earnings ──
            if job.mechanic:
                try:
                    profile = job.mechanic.mechanic_profile
                    gross = float(booking.final_price)
                    if profile.salary_type == 'commission':
                        pct = float(profile.commission_pct) or 40
                    else:
                        pct = 40  # default 40%
                    earning = round(gross * pct / 100, 2)
                    MechanicEarning.objects.get_or_create(
                        job     = job,
                        defaults={
                            'mechanic':       job.mechanic,
                            'garage':         garage,
                            'gross_amount':   gross,
                            'commission_pct': pct,
                            'earning_amount': earning,
                        }
                    )
                    create_notification(job.mechanic,
                        f'💰 ₹{earning:.0f} credited to your earnings',
                        f'Job {booking.reference} verified. ₹{earning:.0f} ({pct:.0f}% commission) '
                        f'added to your earnings dashboard.',
                        'account')
                except Exception as e:
                    logger.error(f'Mechanic earning credit failed: {e}')

        # Notify customer — service delivered
        create_notification(booking.customer,
            f'🎉 Service delivered — {booking.reference}',
            f'Your vehicle is ready! ₹{float(booking.final_price):.0f} has been processed. '
            f'Please rate your experience.',
            'service', booking)

        # Notify mechanic — payment credited
        if job.mechanic:
            create_notification(job.mechanic,
                f'💰 Payment released for job #{job.pk}',
                f'Manager {request.user.name} verified your work on {booking.reference}. '
                f'₹{float(booking.final_price):.0f} credited to garage account.',
                'account')

        # Send completion emails
        try:
            from .otp_utils import send_service_completed_email
            send_service_completed_email(booking, job)
        except Exception as e:
            logger.error(f'Verified completion email failed: {e}')

        return JsonResponse({
            'ok': True,
            'reference': booking.reference,
            'amount': float(booking.final_price),
            'message': f'Job verified! ₹{float(booking.final_price):.0f} released to garage wallet.'
        })
    except Job.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Job not found or not completed'}, status=404)


@login_required
@require_POST
def addJobTaskView(request, pk):
    """Add a task to a job (supports multiple mechanics)."""
    job = get_object_or_404(Job, pk=pk)
    if request.user.role not in ('mechanic', 'manager', 'admin'):
        return JsonResponse({'ok': False}, status=403)
    data      = json.loads(request.body)
    task_name = data.get('task_name', '').strip()
    if not task_name:
        return JsonResponse({'ok': False, 'error': 'Task name required'}, status=400)
    task = JobTask.objects.create(
        job       = job,
        mechanic  = request.user,
        task_name = task_name,
        description = data.get('description', ''),
    )
    return JsonResponse({'ok': True, 'id': task.pk, 'task': task_name,
                         'mechanic': request.user.name})


@login_required
@require_POST
def completeJobTaskView(request, task_pk):
    """Mark a specific task as done."""
    task = get_object_or_404(JobTask, pk=task_pk, mechanic=request.user)
    task.is_done = True
    task.done_at = timezone.now()
    task.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def declineJobView(request, pk):
    """Mechanic declines a job → manager gets notified to reassign."""
    job = get_object_or_404(Job, pk=pk, mechanic=request.user, status='assigned')
    data   = json.loads(request.body) if request.body else {}
    reason = data.get('reason', 'No reason provided')

    # Log the decline
    JobDecline.objects.create(job=job, mechanic=request.user, reason=reason)

    # Remove mechanic from job
    prev_mech_name = request.user.name
    job.mechanic = None
    job.status   = 'assigned'
    job.save(update_fields=['mechanic', 'status'])

    # Also remove from booking
    job.booking.mechanic = None
    job.booking.save(update_fields=['mechanic'])

    # Notify manager to reassign
    if job.booking.garage and job.booking.garage.manager:
        create_notification(
            job.booking.garage.manager,
            f'⚠️ Job Declined — {job.booking.reference}',
            f'{prev_mech_name} declined booking {job.booking.reference}. '
            f'Reason: {reason}. Please reassign to another mechanic.',
            'booking', job.booking
        )

    return JsonResponse({'ok': True, 'message': f'Job declined. Manager notified to reassign.'})


@login_required
@require_POST
def reassignJobView(request, pk):
    """Manager reassigns a job to a different mechanic."""
    if request.user.role not in ('manager', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    garage = Garage.objects.filter(manager=request.user).first()
    job    = get_object_or_404(Job, pk=pk, booking__garage=garage)
    data   = json.loads(request.body)
    mech_id = data.get('mechanic_id')

    try:
        mech = User.objects.get(pk=mech_id, role='mechanic',
                                mechanic_profile__garage=garage)
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Mechanic not found'}, status=404)

    job.mechanic = mech
    job.status   = 'assigned'
    job.save(update_fields=['mechanic', 'status'])

    job.booking.mechanic = mech
    job.booking.save(update_fields=['mechanic'])

    create_notification(mech,
        f'🔧 Job Assigned — {job.booking.reference}',
        f'Manager {request.user.name} assigned you to booking {job.booking.reference}. '
        f'{job.booking.service.name if job.booking.service else "Service"} on {job.booking.scheduled_date}.',
        'booking', job.booking)

    create_notification(job.booking.customer,
        f'🔄 Mechanic Updated — {job.booking.reference}',
        f'Your booking has been assigned to {mech.name}. They will be in touch soon.',
        'service', job.booking)

    return JsonResponse({'ok': True, 'mechanic': mech.name})


@login_required
@require_POST
def assignBookingView(request, ref):
    """
    Manager assigns a mechanic to a booking.
    Creates a Job if one doesn't exist yet.
    """
    if request.user.role not in ('manager', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    garage = Garage.objects.filter(manager=request.user).first()
    if not garage:
        return JsonResponse({'ok': False, 'error': 'No garage found'}, status=404)

    booking = get_object_or_404(Booking, reference=ref, garage=garage)

    data = json.loads(request.body)
    mech_id = data.get('mechanic_id')

    try:
        mech = User.objects.get(pk=mech_id, role='mechanic', mechanic_profile__garage=garage)
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Mechanic not in your garage'}, status=404)

    # Create job if it doesn't exist
    job = getattr(booking, 'job', None)
    if job is None:
        try:
            job = booking.job
        except Exception:
            job = None

    if job:
        job.mechanic = mech
        job.status = 'assigned'
        job.save(update_fields=['mechanic', 'status'])
    else:
        job = Job.objects.create(booking=booking, mechanic=mech, status='assigned')

    # Update booking.mechanic field
    booking.mechanic = mech
    booking.save(update_fields=['mechanic'])

    # Notify mechanic
    create_notification(mech,
        f'🔧 Job Assigned — {booking.reference}',
        f'You have been assigned booking {booking.reference}. '
        f'{booking.service.name if booking.service else "Service"} on {booking.scheduled_date} at {str(booking.scheduled_slot)[:5]}.',
        'booking', booking)

    # Notify customer
    create_notification(booking.customer,
        f'✅ Mechanic Assigned — {booking.reference}',
        f'Great news! {mech.name} has been assigned to your booking {booking.reference} '
        f'and will be handling your {booking.service.name if booking.service else "service"} on {booking.scheduled_date}.',
        'service', booking)

    return JsonResponse({'ok': True, 'mechanic': mech.name, 'mechanic_id': mech.pk})


# ─── BOOKING MESSAGES ───────────────────────────────────────────

@login_required
def bookingMessagesView(request, ref):
    """Get + send messages for a booking (customer ↔ mechanic)."""
    booking = get_object_or_404(Booking, reference=ref)

    # Permission: customer, mechanic, or garage manager
    is_customer = booking.customer == request.user
    is_mechanic = booking.mechanic == request.user
    is_manager  = (booking.garage and booking.garage.manager == request.user)
    if not (is_customer or is_mechanic or is_manager):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    if request.method == 'POST':
        data = json.loads(request.body)
        text = data.get('message', '').strip()
        if not text:
            return JsonResponse({'ok': False, 'error': 'Empty message'}, status=400)

        msg = BookingMessage.objects.create(
            booking=booking, sender=request.user, message=text
        )

        # Notify the other party
        if is_customer and booking.mechanic:
            create_notification(booking.mechanic,
                f'💬 Message from customer — {ref}',
                f'{request.user.name}: {text[:80]}', 'service', booking)
        elif is_mechanic:
            create_notification(booking.customer,
                f'💬 Update from mechanic — {ref}',
                f'{request.user.name}: {text[:80]}', 'service', booking)

        return JsonResponse({
            'ok': True,
            'id': msg.pk,
            'sender': request.user.name,
            'sender_role': request.user.role,
            'message': msg.message,
            'time': msg.created_at.strftime('%d %b, %I:%M %p'),
        })

    # GET — return all messages, mark unread as read
    msgs = booking.messages.select_related('sender').all()
    BookingMessage.objects.filter(booking=booking, is_read=False
        ).exclude(sender=request.user).update(is_read=True)

    return JsonResponse({
        'ok': True,
        'booking_ref': ref,
        'messages': [{
            'id': m.pk,
            'sender': m.sender.name,
            'sender_role': m.sender.role,
            'mine': m.sender == request.user,
            'message': m.message,
            'time': m.created_at.strftime('%d %b, %I:%M %p'),
        } for m in msgs]
    })


@login_required
def managerMasterView(request):
    """Manager's master view — all bookings, mechanics, revenue, declines."""
    if request.user.role not in ('manager', 'admin'):
        return redirect('dashboard')

    garage = Garage.objects.filter(manager=request.user).first()
    if not garage:
        return redirect('garage_settings')

    today = timezone.now().date()
    bookings = Booking.objects.filter(garage=garage).select_related(
        'customer', 'service', 'mechanic', 'vehicle'
    ).order_by('-created_at')

    # Filter
    status_filter = request.GET.get('status', '')
    mech_filter   = request.GET.get('mechanic', '')
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    if mech_filter:
        bookings = bookings.filter(mechanic__pk=mech_filter)

    mechanics = MechanicProfile.objects.filter(
        garage=garage, status='approved'
    ).select_related('mechanic')

    # Per-mechanic stats
    mech_stats = []
    for mp in mechanics:
        mech = mp.mechanic
        jobs = Job.objects.filter(mechanic=mech, booking__garage=garage)
        earned = Booking.objects.filter(
            mechanic=mech, garage=garage,
            job__wallet_released=True
        ).aggregate(total=Sum('final_price'))['total'] or 0
        mech_stats.append({
            'mechanic': mech,
            'profile':  mp,
            'total_jobs':     jobs.count(),
            'done_jobs':      jobs.filter(status='verified').count(),
            'active_jobs':    jobs.filter(status__in=['accepted','in_progress','quality_check']).count(),
            'declined_jobs':  JobDecline.objects.filter(mechanic=mech, job__booking__garage=garage).count(),
            'earned':         earned,
        })

    # Revenue
    total_revenue   = Booking.objects.filter(garage=garage, payment_status='paid').aggregate(
        t=Sum('final_price'))['t'] or 0
    released_amount = Booking.objects.filter(
        garage=garage, job__wallet_released=True
    ).aggregate(t=Sum('final_price'))['t'] or 0
    escrow_amount   = float(total_revenue) - float(released_amount)

    # Recent declines
    declines = JobDecline.objects.filter(
        job__booking__garage=garage
    ).select_related('mechanic', 'job__booking').order_by('-created_at')[:10]

    return render(request, 'core/manager/bookings.html', {
        'garage':          garage,
        'bookings':        bookings,
        'mechanics':       mechanics,
        'mech_stats':      mech_stats,
        'status_filter':   status_filter,
        'mech_filter':     mech_filter,
        'total_revenue':   total_revenue,
        'released_amount': released_amount,
        'escrow_amount':   escrow_amount,
        'today_bookings':  bookings.filter(scheduled_date=today).count(),
        'declines':        declines,
        'status_choices':  Booking.STATUS_CHOICES,
    })


@login_required
@require_POST
def updateChecklist(request, pk):
    job     = get_object_or_404(Job, pk=pk, mechanic=request.user)
    data    = json.loads(request.body)
    item    = get_object_or_404(JobChecklistItem, pk=data.get('item_id'), job=job)
    item.is_done      = data.get('is_done', False)
    item.completed_at = timezone.now() if item.is_done else None
    item.save(update_fields=['is_done','completed_at'])
    done, total = job.checklist_progress
    return JsonResponse({'success': True, 'done': done, 'total': total})


@login_required
@require_POST
def addChecklistItem(request, pk):
    """Mechanic adds a custom task to the job checklist."""
    job  = get_object_or_404(Job, pk=pk, mechanic=request.user)
    data = json.loads(request.body)
    label = data.get('label','').strip()
    if not label:
        return JsonResponse({'ok': False, 'error': 'Task name required'}, status=400)
    create_kwargs = {'job': job, 'label': label, 'is_done': False}
    # Add optional fields only if they exist on the model
    try:
        from django.db import models as _m
        field_names = [f.name for f in JobChecklistItem._meta.get_fields()]
        if 'notes' in field_names:
            create_kwargs['notes'] = data.get('notes', '')
        if 'description' in field_names:
            create_kwargs['description'] = data.get('notes', '')
        if 'sub' in field_names:
            create_kwargs['sub'] = data.get('notes', '')
        if 'order' in field_names:
            create_kwargs['order'] = job.checklist_items.count() + 1
    except Exception:
        pass
    item = JobChecklistItem.objects.create(**create_kwargs)
    notes_val = getattr(item, 'notes', '') or getattr(item, 'description', '') or getattr(item, 'sub', '') or ''
    return JsonResponse({'ok': True, 'pk': item.pk, 'label': item.label, 'notes': notes_val})


@login_required
@require_POST
def uploadJobPhoto(request, pk):
    job  = get_object_or_404(Job, pk=pk, mechanic=request.user)
    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'success': False, 'error': 'No photo'}, status=400)
    JobPhoto.objects.create(
        job=job, photo=photo,
        category=request.POST.get('category','during'),
        caption=request.POST.get('caption','')
    )
    return JsonResponse({'success': True})


@login_required
@require_POST
def addJobPartView(request, pk):
    """Mechanic adds a part/cost line item to the live invoice."""
    job = get_object_or_404(Job, pk=pk)
    if request.user.role not in ('mechanic', 'manager', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    data      = json.loads(request.body)
    name      = data.get('name', '').strip()
    qty       = int(data.get('quantity', 1) or 1)
    unit_cost = float(data.get('unit_cost', 0) or 0)

    if not name or unit_cost <= 0:
        return JsonResponse({'ok': False, 'error': 'Name and cost required'}, status=400)

    part = JobPart.objects.create(
        job       = job,
        name      = name,
        detail    = data.get('detail', ''),
        quantity  = qty,
        unit_cost = unit_cost,
        cost      = qty * unit_cost,
        added_by  = request.user,
    )

    # Recalculate booking parts_total
    booking = job.booking
    parts_total = float(JobPart.objects.filter(job=job).aggregate(
        total=Sum('cost'))['total'] or 0)
    booking.parts_total = parts_total
    booking.save(update_fields=['parts_total','final_bill','balance_due'])

    # Notify customer — live invoice updated
    create_notification(
        booking.customer,
        f'📋 Invoice updated — {booking.reference}',
        f'{request.user.name} added "{name}" (₹{unit_cost:.0f} × {qty}) to your service bill. '
        f'Updated balance: ₹{float(booking.balance_due):.0f}',
        'service', booking
    )

    # Notify manager
    if booking.garage and booking.garage.manager and booking.garage.manager != request.user:
        create_notification(
            booking.garage.manager,
            f'🔧 Part added by {request.user.name} — {booking.reference}',
            f'"{name}" × {qty} @ ₹{unit_cost:.0f} = ₹{qty*unit_cost:.0f}. '
            f'New balance: ₹{float(booking.balance_due):.0f}',
            'booking', booking
        )

    return JsonResponse({
        'ok': True,
        'part': {
            'id': part.pk,
            'name': name,
            'quantity': qty,
            'unit_cost': unit_cost,
            'cost': part.cost,
            'added_by': request.user.name,
        },
        'parts_total': parts_total,
        'balance_due': float(booking.balance_due),
        'final_bill':  float(booking.final_bill),
    })


@login_required
@require_POST
def removeJobPartView(request, part_pk):
    """Manager or the mechanic who added it can remove a part."""
    part = get_object_or_404(JobPart, pk=part_pk)
    if request.user.role not in ('manager', 'admin') and part.added_by != request.user:
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    job     = part.job
    booking = job.booking
    part.delete()

    parts_total = float(JobPart.objects.filter(job=job).aggregate(
        total=Sum('cost'))['total'] or 0)
    booking.parts_total = parts_total
    booking.save(update_fields=['parts_total','final_bill','balance_due'])

    return JsonResponse({
        'ok': True,
        'parts_total': parts_total,
        'balance_due': float(booking.balance_due),
        'final_bill':  float(booking.final_bill),
    })


@login_required
def liveInvoiceView(request, ref):
    """Returns live invoice JSON — customer sees real-time cost updates."""
    booking = get_object_or_404(Booking, reference=ref)

    # Permission: customer, mechanic, or manager
    if not (booking.customer == request.user or
            booking.mechanic == request.user or
            (booking.garage and booking.garage.manager == request.user)):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    parts = []
    try:
        for p in booking.job.parts.select_related('added_by').all():
            parts.append({
                'id':        p.pk,
                'name':      p.name,
                'detail':    p.detail,
                'quantity':  p.quantity,
                'unit_cost': float(p.unit_cost),
                'cost':      float(p.cost),
                'added_by':  p.added_by.name if p.added_by else '—',
                'is_approved': p.is_approved,
            })
    except Exception:
        pass

    return JsonResponse({
        'ok':           True,
        'reference':    booking.reference,
        'service':      booking.service.name if booking.service else '—',
        'base_price':   float(booking.base_price),
        'discount':     float(booking.discount_amount),
        'advance_paid': float(booking.advance_amount) if booking.advance_paid else 0,
        'parts_total':  float(booking.parts_total),
        'labour_charge':float(booking.labour_charge),
        'final_bill':   float(booking.final_bill),
        'balance_due':  float(booking.balance_due),
        'final_paid':   booking.final_paid,
        'parts':        parts,
        'status':       booking.status,
        'job_status':   booking.job.status if hasattr(booking, 'job') else None,
    })


@login_required
@require_POST
def finalSettlementView(request, ref):
    """Manager marks final balance as paid → releases full escrow to wallet."""
    booking = get_object_or_404(Booking, reference=ref)
    if not (booking.garage and booking.garage.manager == request.user):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    data   = json.loads(request.body)
    method = data.get('method', 'cash')

    booking.final_paid    = True
    booking.final_paid_at = timezone.now()
    booking.final_method  = method
    booking.status        = 'delivered'
    booking.save(update_fields=['final_paid','final_paid_at','final_method','status'])

    # Release full amount to garage wallet
    if hasattr(booking, 'job') and not booking.job.wallet_released:
        from django.db.models import F
        Garage.objects.filter(pk=booking.garage.pk).update(
            wallet_balance=F('wallet_balance') + booking.final_bill
        )
        GarageTransaction.objects.create(
            garage      = booking.garage,
            booking     = booking,
            type        = 'credit',
            amount      = booking.final_bill,
            description = f'Final settlement — {booking.reference} (₹{float(booking.advance_amount):.0f} advance + ₹{float(booking.balance_due):.0f} balance)',
        )
        booking.job.wallet_released    = True
        booking.job.wallet_released_at = timezone.now()
        booking.job.save(update_fields=['wallet_released','wallet_released_at'])

    # Notify customer
    create_notification(
        booking.customer,
        f'🎉 Service complete — {booking.reference}',
        f'Final bill: ₹{float(booking.final_bill):.0f} '
        f'(Advance ₹{float(booking.advance_amount):.0f} + Balance ₹{float(booking.balance_due):.0f}). '
        f'Please rate your experience!',
        'service', booking
    )

    # Send final invoice email
    try:
        from .otp_utils import send_service_completed_email
        send_service_completed_email(booking, booking.job if hasattr(booking, 'job') else None)
    except Exception as e:
        logger.error(f'Final invoice email failed: {e}')

    return JsonResponse({
        'ok':        True,
        'final_bill': float(booking.final_bill),
        'balance':   float(booking.balance_due),
        'reference': booking.reference,
    })


@login_required
@require_POST
def updateLiveLocation(request):
    """Mechanic updates their GPS location."""
    if request.user.role != 'mechanic' and not request.user.is_individual:
        return JsonResponse({'ok': False})
    try:
        data = json.loads(request.body)
        lat  = data.get('lat')
        lng  = data.get('lng')
        # Update user location
        User.objects.filter(pk=request.user.pk).update(
            current_lat=lat, current_lng=lng, last_seen=timezone.now()
        )
        # Update live location for active booking
        ref = data.get('booking_ref')
        if ref:
            try:
                booking = Booking.objects.get(reference=ref, mechanic=request.user)
                LiveLocation.objects.update_or_create(
                    booking=booking,
                    defaults={'mechanic': request.user, 'lat': lat, 'lng': lng,
                              'speed_kmh': data.get('speed', 0),
                              'heading': data.get('heading', 0)}
                )
            except Booking.DoesNotExist:
                pass
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


@login_required
def earningsView(request):
    if request.user.role not in ('mechanic', 'admin') and not request.user.is_individual:
        return redirect('dashboard')

    user  = request.user
    today = timezone.now().date()
    week_start  = today - timezone.timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Jobs this mechanic has completed
    jobs = Job.objects.filter(
        mechanic=user, status__in=['completed','verified']
    ).select_related('booking','booking__service','booking__garage','earning').order_by('-completed_at')

    # Earnings from MechanicEarning records
    earnings = MechanicEarning.objects.filter(mechanic=user).order_by('-credited_at')

    today_earning  = earnings.filter(credited_at__date=today).aggregate(t=Sum('earning_amount'))['t'] or 0
    week_earning   = earnings.filter(credited_at__date__gte=week_start).aggregate(t=Sum('earning_amount'))['t'] or 0
    month_earning  = earnings.filter(credited_at__date__gte=month_start).aggregate(t=Sum('earning_amount'))['t'] or 0
    total_earning  = earnings.aggregate(t=Sum('earning_amount'))['t'] or 0
    today_jobs     = jobs.filter(completed_at__date=today).count()
    month_jobs     = jobs.filter(completed_at__date__gte=month_start).count()
    total_jobs     = jobs.count()
    avg_rating     = Review.objects.filter(booking__mechanic=user).aggregate(avg=Avg('rating'))['avg']

    # Commission rate
    commission_pct = 40
    try:
        profile = user.mechanic_profile
        if profile.salary_type == 'commission':
            commission_pct = float(profile.commission_pct) or 40
    except Exception:
        pass

    return render(request, 'core/mechanic/earnings.html', {
        'today_earning':   round(float(today_earning), 2),
        'week_earning':    round(float(week_earning), 2),
        'month_earning':   round(float(month_earning), 2),
        'total_earning':   round(float(total_earning), 2),
        'today_jobs':      today_jobs,
        'month_jobs':      month_jobs,
        'total_jobs':      total_jobs,
        'avg_rating':      avg_rating,
        'commission_pct':  commission_pct,
        'recent_earnings': earnings[:15],
        'recent_jobs':     jobs[:10],
        'today':           today,
    })


@login_required
def scheduleView(request):
    if request.user.role not in ('mechanic', 'admin') and not request.user.is_individual:
        return redirect('dashboard')

    user = request.user

    # Handle leave request submission
    if request.method == 'POST' and request.POST.get('action') == 'leave_request':
        from_date  = request.POST.get('from_date', '').strip()
        to_date    = request.POST.get('to_date', '').strip()
        leave_type = request.POST.get('leave_type', 'casual').strip()
        reason     = request.POST.get('reason', '').strip()

        if not from_date or not to_date:
            messages.error(request, '❌ Please select from and to dates.')
            return redirect('schedule')

        # Find mechanic's garage — try multiple paths
        garage = None
        try:
            garage = user.mechanic_profile.garage
        except Exception:
            pass
        if not garage:
            # Fallback: find via MechanicProfile queryset
            mp = MechanicProfile.objects.filter(mechanic=user).select_related('garage').first()
            if mp:
                garage = mp.garage

        if not garage:
            messages.error(request, '❌ You are not assigned to a garage. Contact your manager.')
            return redirect('schedule')

        leave = MechanicLeaveRequest.objects.create(
            mechanic   = user,
            garage     = garage,
            leave_type = leave_type,
            from_date  = from_date,
            to_date    = to_date,
            reason     = reason,
            status     = 'pending',
        )

        # Notify garage manager
        if garage.manager:
            create_notification(
                garage.manager,
                f'📅 Leave Request — {user.name}',
                f'{user.name} has requested {leave.get_leave_type_display()} '
                f'from {leave.from_date} to {leave.to_date}. '
                f'Reason: {reason or "Not provided"}. Approve or reject from Team → Leave Requests.',
                'system'
            )

        messages.success(request, f'✅ Leave request submitted for {from_date} to {to_date}. Waiting for manager approval.')
        return redirect('schedule')

    jobs = Job.objects.filter(mechanic=user).select_related(
        'booking','booking__service','booking__vehicle','booking__customer'
    ).order_by('booking__scheduled_date','booking__scheduled_slot')

    # Pass leave requests for this mechanic
    my_leaves = MechanicLeaveRequest.objects.filter(mechanic=user).order_by('-created_at')[:10]

    return render(request, 'core/mechanic/schedule.html', {
        'jobs': jobs,
        'my_leaves': my_leaves,
    })


@login_required
@require_POST
def toggleAvailabilityView(request):
    user = request.user
    user.is_available = not getattr(user, 'is_available', True)
    user.save(update_fields=['is_available'])
    return JsonResponse({'status': 'ok', 'is_available': user.is_available})


# ═══════════════════════════════════════════════════════════════
#  MECHANIC — APPLY AS INDIVIDUAL
# ═══════════════════════════════════════════════════════════════

@login_required
def applyIndividualMechanicView(request):
    """Mechanic applies to work as individual (admin approves)."""
    try:
        profile = request.user.individual_profile
        existing = profile
    except IndividualMechanicProfile.DoesNotExist:
        existing = None

    if request.method == 'POST' and not existing:
        profile = IndividualMechanicProfile.objects.create(
            mechanic         = request.user,
            apply_reason     = request.POST.get('reason', ''),
            service_cities   = request.POST.get('cities', ''),
            service_radius_km = int(request.POST.get('radius', 20) or 20),
            experience_years = int(request.POST.get('experience', 0) or 0),
            hourly_rate      = float(request.POST.get('rate', 0) or 0),
            home_visit       = request.POST.get('home_visit') == 'on',
            home_visit_charge = float(request.POST.get('visit_charge', 0) or 0),
            specializations  = request.POST.getlist('skills'),
        )
        request.user.is_individual = True
        request.user.save(update_fields=['is_individual'])

        # Notify admins
        for admin in User.objects.filter(is_super_admin=True):
            create_notification(admin,
                f'🔧 Individual Mechanic Application: {request.user.name}',
                f'{request.user.name} applied to work as an individual mechanic in '
                f'{profile.service_cities}.', 'system')

        messages.success(request, '✅ Application submitted! Admin will review it.')
        return redirect('dashboard')

    return render(request, 'core/individual/apply.html', {'existing': existing})


# ═══════════════════════════════════════════════════════════════
#  MANAGER — GARAGE, TEAM, REPORTS
# ═══════════════════════════════════════════════════════════════

@login_required
def garageServicesView(request):
    """Manager sets which services they offer and at what price + advance fee."""
    if request.user.role not in ('manager', 'admin'):
        return redirect('dashboard')

    garage = Garage.objects.filter(manager=request.user).first()
    if not garage:
        messages.error(request, 'Set up your garage first.')
        return redirect('garage_settings')

    all_services = Service.objects.filter(is_active=True).order_by('order', 'name')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Update advance fee ──
        if action == 'set_advance':
            fee = request.POST.get('advance_fee', '').strip()
            try:
                fee = float(fee)
                if fee < 0:
                    raise ValueError
                garage.advance_fee = fee
                garage.save(update_fields=['advance_fee'])
                messages.success(request, f'✅ Advance fee set to ₹{fee:.0f}')
            except (ValueError, TypeError):
                messages.error(request, '❌ Invalid amount. Enter a number like 500.')
            return redirect('garage_services')

        # ── Save service offerings + prices ──
        if action == 'save_services':
            for svc in all_services:
                offered = request.POST.get(f'offered_{svc.pk}') == 'on'
                basic    = request.POST.get(f'price_basic_{svc.pk}', '').strip()
                standard = request.POST.get(f'price_standard_{svc.pk}', '').strip()
                premium  = request.POST.get(f'price_premium_{svc.pk}', '').strip()
                notes    = request.POST.get(f'notes_{svc.pk}', '').strip()

                def to_dec(v):
                    try: return float(v) if v else None
                    except: return None

                GarageService.objects.update_or_create(
                    garage=garage, service=svc,
                    defaults={
                        'is_offered':    offered,
                        'price_basic':   to_dec(basic),
                        'price_standard':to_dec(standard),
                        'price_premium': to_dec(premium),
                        'notes':         notes,
                    }
                )
            messages.success(request, '✅ Services updated! Customers will see your prices.')
            return redirect('garage_services')

    # Build merged list: service + garage override if exists
    garage_svc_map = {gs.service_id: gs for gs in GarageService.objects.filter(garage=garage)}
    service_list = []
    for svc in all_services:
        gs = garage_svc_map.get(svc.pk)
        service_list.append({
            'service':        svc,
            'garage_service': gs,
            'is_offered':     gs.is_offered if gs else False,
            'price_basic':    gs.price_basic    if gs and gs.price_basic    else svc.price_basic,
            'price_standard': gs.price_standard if gs and gs.price_standard else svc.price_standard,
            'price_premium':  gs.price_premium  if gs and gs.price_premium  else svc.price_premium,
            'notes':          gs.notes if gs else '',
        })

    return render(request, 'core/manager/garage_services.html', {
        'garage':       garage,
        'service_list': service_list,
        'advance_fee':  float(garage.advance_fee),
    })


@login_required
@login_required
def garagePricingView(request):
    """Manager sets per-service prices, advance fee, and adds custom services."""
    if request.user.role not in ('manager', 'admin'):
        return redirect('dashboard')

    garage = Garage.objects.filter(manager=request.user).first()
    if not garage:
        messages.error(request, 'Set up your garage first.')
        return redirect('garage_settings')

    all_services = Service.objects.filter(is_active=True).order_by('order')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Update advance fee ──
        if action == 'update_advance':
            fee = request.POST.get('advance_fee', '').strip()
            try:
                garage.advance_fee = max(0, float(fee))
                garage.save(update_fields=['advance_fee'])
                messages.success(request, f'✅ Advance fee updated to ₹{garage.advance_fee:.0f}')
            except ValueError:
                messages.error(request, 'Invalid fee amount.')
            return redirect('garage_pricing')

        # ── Update service prices ──
        if action == 'update_prices':
            for svc in all_services:
                offered = request.POST.get(f'offered_{svc.pk}') == 'on'
                p_basic    = request.POST.get(f'basic_{svc.pk}', '').strip()
                p_standard = request.POST.get(f'standard_{svc.pk}', '').strip()
                p_premium  = request.POST.get(f'premium_{svc.pk}', '').strip()
                notes      = request.POST.get(f'notes_{svc.pk}', '').strip()
                duration   = request.POST.get(f'duration_{svc.pk}', '').strip()

                GarageService.objects.update_or_create(
                    garage=garage, service=svc,
                    defaults={
                        'is_offered':    offered,
                        'price_basic':   float(p_basic)    if p_basic    else None,
                        'price_standard':float(p_standard) if p_standard else None,
                        'price_premium': float(p_premium)  if p_premium  else None,
                        'notes':         notes,
                        'duration_hours':float(duration)   if duration   else None,
                    }
                )
            messages.success(request, '✅ Service pricing updated!')
            return redirect('garage_pricing')

        # ── Add custom service ──
        if action == 'add_custom':
            name = request.POST.get('custom_name', '').strip()
            if name:
                GarageCustomService.objects.create(
                    garage       = garage,
                    name         = name,
                    description  = request.POST.get('custom_desc', ''),
                    icon_emoji   = request.POST.get('custom_icon', '🔧'),
                    category     = request.POST.get('custom_category', 'both'),
                    price_basic  = float(request.POST.get('custom_basic',  0) or 0),
                    price_standard = float(request.POST.get('custom_standard', 0) or 0),
                    price_premium  = float(request.POST.get('custom_premium', 0) or 0),
                    duration_hours = float(request.POST.get('custom_duration', 2) or 2),
                )
                messages.success(request, f'✅ "{name}" added to your service menu!')
            return redirect('garage_pricing')

        # ── Delete custom service ──
        if action == 'delete_custom':
            cs_id = request.POST.get('custom_id')
            GarageCustomService.objects.filter(pk=cs_id, garage=garage).delete()
            messages.success(request, '✅ Custom service removed.')
            return redirect('garage_pricing')

    # Build current pricing data using shared helper
    service_rows    = _build_service_rows(garage, all_services)
    custom_services = GarageCustomService.objects.filter(garage=garage).order_by('name')

    return render(request, 'core/manager/garage_pricing.html', {
        'garage':        garage,
        'service_rows':  service_rows,
        'custom_services': custom_services,
    })


def garageSettingsView(request):
    if request.user.role not in ('manager', 'admin'):
        return redirect('dashboard')

    garage = Garage.objects.filter(manager=request.user).first()
    all_services    = Service.objects.filter(is_active=True).order_by('order')
    garage_services = list(garage.services.all()) if garage and hasattr(garage, 'services') else []
    days = [(0,'Monday'),(1,'Tuesday'),(2,'Wednesday'),(3,'Thursday'),
            (4,'Friday'),(5,'Saturday'),(6,'Sunday')]
    garage_hours = {}
    if garage:
        for h in garage.hours.all():
            garage_hours[h.day] = h

    success = error = None

    if request.method == 'POST':
        from .geocode import geocode_address
        import re
        name    = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        city    = request.POST.get('city', '').strip()
        if not name or not address or not city:
            error = 'Name, Address and City are required.'
        else:
            lat = request.POST.get('lat', '').strip()
            lng = request.POST.get('lng', '').strip()
            if not lat or not lng:
                result = geocode_address(address, city)
                if result:
                    lat, lng = result['lat'], result['lng']

            slug_base = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ','-'))[:50].strip('-')

            if garage:
                for field in ['name','address','area','city','state','pincode','phone','email','gst_number','description']:
                    val = request.POST.get(field, '')
                    if val:
                        setattr(garage, field, val)
                # Optional fields that may not exist in older migrations
                for opt_field in ['landmark', 'maps_link', 'website', 'whatsapp']:
                    val = request.POST.get(opt_field, '').strip()
                    if hasattr(garage, opt_field):
                        setattr(garage, opt_field, val)
                garage.capacity_per_day = int(request.POST.get('capacity_per_day', 20) or 20)
                try:
                    garage.advance_fee = float(request.POST.get('advance_fee', 600) or 600)
                except (ValueError, TypeError):
                    pass
                if lat: garage.lat = lat
                if lng: garage.lng = lng
                if 'logo' in request.FILES: garage.logo = request.FILES['logo']
                if 'cover_photo' in request.FILES: garage.cover_photo = request.FILES['cover_photo']
                garage.save()
            else:
                slug = slug_base
                n = 1
                while Garage.objects.filter(slug=slug).exists():
                    slug = f'{slug_base}-{n}'; n += 1

                garage = Garage.objects.create(
                    name=name, slug=slug, manager=request.user,
                    address=address,
                    area=request.POST.get('area',''),
                    city=city,
                    state=request.POST.get('state','Gujarat'),
                    pincode=request.POST.get('pincode',''),
                    phone=request.POST.get('phone',''),
                    email=request.POST.get('email',''),
                    gst_number=request.POST.get('gst_number',''),
                    description=request.POST.get('description',''),
                    capacity_per_day=int(request.POST.get('capacity_per_day', 20) or 20),
                    advance_fee=float(request.POST.get('advance_fee', 600) or 600),
                    lat=lat or None, lng=lng or None,
                    is_active=False,
                    approval_status='pending',
                )
                # Optional fields added in later migrations — set safely
                for opt_field in ['landmark', 'maps_link', 'website', 'whatsapp']:
                    val = request.POST.get(opt_field, '').strip()
                    if val and hasattr(garage, opt_field):
                        setattr(garage, opt_field, val)
                if 'logo' in request.FILES: garage.logo = request.FILES['logo']
                if 'cover_photo' in request.FILES: garage.cover_photo = request.FILES['cover_photo']
                garage.save()

                # Notify admins to approve
                for admin in User.objects.filter(is_super_admin=True):
                    create_notification(admin,
                        f'🏢 New Garage Submitted: {name}',
                        f'{request.user.name} submitted garage "{name}" in {city} for approval.',
                        'system')

            # Save hours — skip if times are empty (JS may not have synced)
            for day_num, _ in days:
                is_closed = request.POST.get(f'closed_{day_num}') == 'true'
                open_t    = request.POST.get(f'open_{day_num}', '').strip() or '09:00'
                close_t   = request.POST.get(f'close_{day_num}', '').strip() or '19:00'
                # Validate format — if still bad, use defaults
                import re
                time_re = re.compile(r'^\d{2}:\d{2}$')
                if not time_re.match(open_t):  open_t  = '09:00'
                if not time_re.match(close_t): close_t = '19:00'
                GarageHours.objects.update_or_create(
                    garage=garage, day=day_num,
                    defaults={'open_time': open_t, 'close_time': close_t, 'is_closed': is_closed}
                )

            success = f'✅ Garage "{garage.name}" saved! ' + \
                      ('Pending admin approval.' if garage.approval_status == 'pending' else 'Active on map.')
            garage_hours = {h.day: h for h in garage.hours.all()}

    return render(request, 'core/manager/garage_settings.html', {
        'garage':          garage,
        'days':            days,
        'garage_hours':    garage_hours,
        'all_services':    all_services,
        'garage_services': garage_services,
        'success':         success,
        'error':           error,
        'today_bookings':  Booking.objects.filter(garage=garage, scheduled_date=timezone.now().date()).count() if garage else 0,
        'month_bookings':  Booking.objects.filter(garage=garage, created_at__month=timezone.now().month).count() if garage else 0,
        'team_count':      MechanicProfile.objects.filter(garage=garage).count() if garage else 0,
        # For services tab
        'service_rows':    _build_service_rows(garage, all_services) if garage else [],
        'custom_services': GarageCustomService.objects.filter(garage=garage) if garage else [],
    })


@login_required
@login_required
@require_POST
def approveLeaveView(request, pk):
    """Manager approves a mechanic leave request."""
    if request.user.role not in ('manager', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)
    try:
        leave = MechanicLeaveRequest.objects.get(
            pk=pk, garage__manager=request.user, status='pending'
        )
        leave.status      = 'approved'
        leave.reviewed_by = request.user
        leave.reviewed_at = timezone.now()
        leave.save()
        create_notification(leave.mechanic,
            f'✅ Leave Approved — {leave.from_date} to {leave.to_date}',
            f'Your {leave.get_leave_type_display()} request has been approved by {request.user.name}.',
            'account')
        return JsonResponse({'ok': True, 'name': leave.mechanic.name})
    except MechanicLeaveRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


@login_required
@require_POST
def rejectLeaveView(request, pk):
    """Manager rejects a mechanic leave request with reason."""
    if request.user.role not in ('manager', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)
    try:
        data   = json.loads(request.body)
        reason = data.get('reason', 'Not approved at this time.')
        leave  = MechanicLeaveRequest.objects.get(
            pk=pk, garage__manager=request.user, status='pending'
        )
        leave.status           = 'rejected'
        leave.reviewed_by      = request.user
        leave.reviewed_at      = timezone.now()
        leave.rejection_reason = reason
        leave.save()
        create_notification(leave.mechanic,
            f'❌ Leave Rejected — {leave.from_date} to {leave.to_date}',
            f'Reason: {reason}', 'account')
        return JsonResponse({'ok': True})
    except MechanicLeaveRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


@login_required
@require_POST
def saveShiftView(request, mechanic_id):
    """Manager sets weekly shift schedule for a mechanic."""
    if request.user.role not in ('manager', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)
    garage = Garage.objects.filter(manager=request.user).first()
    if not garage:
        return JsonResponse({'ok': False, 'error': 'No garage'}, status=400)
    try:
        data  = json.loads(request.body)   # {shifts: [{day:0, start:'09:00', end:'18:00', off:false}]}
        mech  = User.objects.get(pk=mechanic_id, mechanic_profile__garage=garage)
        for s in data.get('shifts', []):
            import re
            t_re = re.compile(r'^\d{2}:\d{2}$')
            start = s.get('start','09:00') if t_re.match(s.get('start','')) else '09:00'
            end   = s.get('end','18:00')   if t_re.match(s.get('end',''))   else '18:00'
            MechanicShift.objects.update_or_create(
                mechanic=mech, day=int(s['day']),
                defaults={
                    'garage':     garage,
                    'start_time': start,
                    'end_time':   end,
                    'is_off':     bool(s.get('off', False)),
                }
            )
        return JsonResponse({'ok': True})
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Mechanic not found'}, status=404)


def teamView(request):
    if request.user.role not in ('manager', 'admin'):
        return redirect('dashboard')

    garage    = Garage.objects.filter(manager=request.user).first()
    mechanics = MechanicProfile.objects.filter(garage=garage).select_related('mechanic') if garage else []
    pending_requests = MechanicRequest.objects.filter(
        garage=garage, status='pending'
    ).select_related('mechanic') if garage else []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_mechanic' and garage:
            name  = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            phone = request.POST.get('phone', '').strip()
            designation = request.POST.get('designation', 'Mechanic')
            salary = request.POST.get('salary', 0)
            skills = request.POST.getlist('skills')

            if not name or not email:
                messages.error(request, 'Name and email required.')
            elif User.objects.filter(email=email).exists():
                messages.error(request, 'A user with this email already exists. Use a different email.')
            else:
                # Use manager-provided password
                password = request.POST.get('password', '').strip()
                if len(password) < 6:
                    messages.error(request, 'Password must be at least 6 characters.')
                    return redirect('team')
                mech_user = User.objects.create_user(
                    email=email, name=name, phone=phone,
                    password=password, role='mechanic',
                    city=garage.city,
                    manager_created=True,  # skip OTP on login
                )
                MechanicProfile.objects.create(
                    mechanic=mech_user,
                    garage=garage,
                    added_by=request.user,
                    designation=request.POST.get('designation', 'Mechanic'),
                    salary_amount=request.POST.get('salary', 0) or 0,
                    salary_type=request.POST.get('salary_type', 'commission'),
                    status='approved',
                    joining_date=timezone.now().date(),
                    approved_at=timezone.now(),
                )
                create_notification(mech_user,
                    f'👋 Welcome to {garage.name}!',
                    f'Your mechanic account has been created by {request.user.name}. '
                    f'Login at eGarage with: {email}', 'account')
                messages.success(request, f'✅ {name} added! They can now login with email: {email} and the password you set.')
            return redirect('team')

        elif action == 'approve_request' and garage:
            req_id = request.POST.get('request_id')
            try:
                mr = MechanicRequest.objects.get(pk=req_id, garage=garage, status='pending')
                mr.status = 'approved'
                mr.reviewed_at = timezone.now()
                mr.reviewed_by = request.user
                mr.save()
                MechanicProfile.objects.get_or_create(
                    mechanic=mr.mechanic, garage=garage,
                    defaults={'added_by': request.user, 'status': 'approved',
                              'joining_date': timezone.now().date(), 'approved_at': timezone.now()}
                )
                mr.mechanic.is_available = True
                mr.mechanic.save(update_fields=['is_available'])
                create_notification(mr.mechanic,
                    f'✅ Request approved by {garage.name}!',
                    f'You can now login and start accepting jobs at {garage.name}.',
                    'account')
                messages.success(request, f'✅ {mr.mechanic.name} approved!')
            except MechanicRequest.DoesNotExist:
                messages.error(request, 'Request not found.')
            return redirect('team')

        elif action == 'reject_request' and garage:
            req_id = request.POST.get('request_id')
            reason = request.POST.get('reason', 'Not suitable at this time.')
            try:
                mr = MechanicRequest.objects.get(pk=req_id, garage=garage, status='pending')
                mr.status = 'rejected'
                mr.reviewed_at = timezone.now()
                mr.reviewed_by = request.user
                mr.reject_reason = reason
                mr.save()
                create_notification(mr.mechanic,
                    f'❌ Request rejected by {garage.name}',
                    f'Reason: {reason}', 'account')
                messages.info(request, 'Request rejected.')
            except MechanicRequest.DoesNotExist:
                messages.error(request, 'Request not found.')
            return redirect('team')

        elif action == 'remove_mechanic' and garage:
            mech_id = request.POST.get('mechanic_id')
            try:
                mp = MechanicProfile.objects.get(mechanic__pk=mech_id, garage=garage)
                name = mp.mechanic.name
                mp.delete()
                messages.success(request, f'✅ {name} removed from your garage.')
            except MechanicProfile.DoesNotExist:
                messages.error(request, 'Mechanic not found in your garage.')
            return redirect('team')

        elif action == 'update_mechanic':
            mp_id   = request.POST.get('mechanic_profile_id')
            try:
                mp = MechanicProfile.objects.get(pk=mp_id, garage=garage)
                mp.designation    = request.POST.get('designation', mp.designation)
                mp.salary_amount  = request.POST.get('salary', mp.salary_amount)
                mp.salary_type    = request.POST.get('salary_type', mp.salary_type)
                mp.commission_pct = request.POST.get('commission', mp.commission_pct)
                mp.skills         = request.POST.getlist('skills')
                mp.notes          = request.POST.get('notes', mp.notes)
                mp.save()
                messages.success(request, '✅ Mechanic profile updated!')
            except MechanicProfile.DoesNotExist:
                messages.error(request, 'Profile not found.')
            return redirect('team')

    # Leave requests for this garage
    pending_leaves = MechanicLeaveRequest.objects.filter(
        garage=garage, status='pending'
    ).select_related('mechanic').order_by('from_date') if garage else []

    recent_leaves = MechanicLeaveRequest.objects.filter(
        garage=garage
    ).select_related('mechanic', 'reviewed_by').order_by('-created_at')[:30] if garage else []

    # Shifts per mechanic — keyed by mechanic pk
    shifts_map = {}
    if garage:
        for s in MechanicShift.objects.filter(garage=garage).select_related('mechanic'):
            shifts_map.setdefault(s.mechanic_id, []).append(s)

    days_list = [(0,'Mon'),(1,'Tue'),(2,'Wed'),(3,'Thu'),(4,'Fri'),(5,'Sat'),(6,'Sun')]

    # ── Per-mechanic earnings for manager team view ──
    from django.db.models import Sum as _Sum, Count as _Count
    today_d = timezone.now().date()
    month_start_d = today_d.replace(day=1)
    mech_earnings = {}
    mech_job_counts = {}
    if garage:
        for mp in mechanics:
            muid = mp.mechanic_id
            me = MechanicEarning.objects.filter(mechanic_id=muid)
            mech_earnings[muid] = {
                'month': round(float(me.filter(credited_at__date__gte=month_start_d).aggregate(t=Sum('earning_amount'))['t'] or 0), 2),
                'total': round(float(me.aggregate(t=Sum('earning_amount'))['t'] or 0), 2),
            }
            mech_job_counts[muid] = Job.objects.filter(
                mechanic_id=muid, status__in=['completed','verified']
            ).count()

    team_month_total = sum(v['month'] for v in mech_earnings.values())
    team_total_total = sum(v['total'] for v in mech_earnings.values())

    return render(request, 'core/manager/team.html', {
        'garage':            garage,
        'mechanics':         mechanics,
        'pending_requests':  pending_requests,
        'pending_leaves':    pending_leaves,
        'recent_leaves':     recent_leaves,
        'shifts_map':        shifts_map,
        'days_list':         days_list,
        'mech_earnings':     mech_earnings,
        'mech_job_counts':   mech_job_counts,
        'team_month_total':  team_month_total,
        'team_total_total':  team_total_total,
    })


@login_required
def managerFinanceView(request):
    """Manager team view — total revenue, per-mechanic breakdown, daily summary."""
    if request.user.role not in ('manager', 'admin'):
        return redirect('dashboard')

    garage = Garage.objects.filter(manager=request.user).first()
    if not garage:
        return redirect('garage_settings')

    today       = timezone.now().date()
    week_start  = today - timezone.timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # ── SINGLE SOURCE OF TRUTH ──
    # Revenue = ALL delivered bookings (cash + online), using final_price
    all_bk       = Booking.objects.filter(garage=garage)
    delivered_bk = all_bk.filter(status='delivered')

    today_rev  = delivered_bk.filter(updated_at__date=today
                 ).aggregate(t=Sum('final_price'))['t'] or 0
    week_rev   = delivered_bk.filter(updated_at__date__gte=week_start
                 ).aggregate(t=Sum('final_price'))['t'] or 0
    month_rev  = delivered_bk.filter(updated_at__date__gte=month_start
                 ).aggregate(t=Sum('final_price'))['t'] or 0
    total_rev  = delivered_bk.aggregate(t=Sum('final_price'))['t'] or 0

    # Cash vs Online breakdown
    cash_month   = delivered_bk.filter(payment_method='cash', updated_at__date__gte=month_start
                   ).aggregate(t=Sum('final_price'))['t'] or 0
    online_month = delivered_bk.filter(updated_at__date__gte=month_start
                   ).exclude(payment_method='cash'
                   ).aggregate(t=Sum('final_price'))['t'] or 0

    cash_total   = delivered_bk.filter(payment_method='cash'
                   ).aggregate(t=Sum('final_price'))['t'] or 0
    online_total = delivered_bk.exclude(payment_method='cash'
                   ).aggregate(t=Sum('final_price'))['t'] or 0

    # Escrow = bookings currently in service
    escrow_rev   = all_bk.filter(
                       status__in=['in_progress','quality_check','at_garage']
                   ).aggregate(t=Sum('final_price'))['t'] or 0

    today_bookings = Booking.objects.filter(garage=garage, scheduled_date=today).count()
    today_jobs_done = Job.objects.filter(booking__garage=garage, status__in=['completed','verified'],
                                          completed_at__date=today).count()

    # Per-mechanic breakdown
    mechanics = MechanicProfile.objects.filter(
        garage=garage, status='approved'
    ).select_related('mechanic')

    mech_data = []
    for mp in mechanics:
        mech = mp.mechanic
        mearnings = MechanicEarning.objects.filter(mechanic=mech, garage=garage)
        mech_data.append({
            'mechanic':       mech,
            'profile':        mp,
            'today_earning':  float(mearnings.filter(credited_at__date=today
                                ).aggregate(t=Sum('earning_amount'))['t'] or 0),
            'week_earning':   float(mearnings.filter(credited_at__date__gte=week_start
                                ).aggregate(t=Sum('earning_amount'))['t'] or 0),
            'month_earning':  float(mearnings.filter(credited_at__date__gte=month_start
                                ).aggregate(t=Sum('earning_amount'))['t'] or 0),
            'total_jobs':     Job.objects.filter(mechanic=mech, booking__garage=garage,
                                status__in=['completed','verified']).count(),
            'today_jobs':     Job.objects.filter(mechanic=mech, booking__garage=garage,
                                status__in=['completed','verified'], completed_at__date=today).count(),
            'avg_rating':     Review.objects.filter(booking__mechanic=mech, booking__garage=garage
                                ).aggregate(avg=Avg('rating'))['avg'],
            'is_available':   mech.is_available,
        })

    # Sort by today's earning desc
    mech_data.sort(key=lambda x: x['today_earning'], reverse=True)

    # Recent transactions
    recent_txns = GarageTransaction.objects.filter(garage=garage).order_by('-created_at')[:20]

    return render(request, 'core/manager/finance.html', {
        'garage':         garage,
        'today':          today,
        'today_rev':      float(today_rev),
        'week_rev':       float(week_rev),
        'month_rev':      float(month_rev),
        'total_rev':      float(total_rev),
        'escrow_rev':     float(escrow_rev),
        'cash_month':     float(cash_month),
        'online_month':   float(online_month),
        'cash_total':     float(cash_total),
        'online_total':   float(online_total),
        'today_bookings': today_bookings,
        'today_jobs_done':today_jobs_done,
        'mech_data':      mech_data,
        'recent_txns':    recent_txns,
        'wallet_balance': float(garage.wallet_balance),
    })


@login_required
def reportsView(request):
    if request.user.role not in ('manager', 'admin'):
        return redirect('dashboard')
    garage = Garage.objects.filter(manager=request.user).first()
    today  = timezone.now().date()
    bookings = Booking.objects.filter(garage=garage) if garage else Booking.objects.none()
    # Extra context for enhanced reports page
    cancelled_count = bookings.filter(status='cancelled').count()
    completed_count = bookings.filter(status='delivered').count()
    return render(request, 'core/manager/reports.html', {
        'garage':               garage,
        'garage_approved':      garage.approval_status == 'approved' if garage else False,
        'today_bookings':       bookings.filter(scheduled_date=today).count(),
        'month_bookings':       bookings.filter(scheduled_date__month=today.month, scheduled_date__year=today.year).count(),
        'month_revenue':        bookings.filter(scheduled_date__month=today.month, scheduled_date__year=today.year, status='delivered').aggregate(t=Sum('final_price'))['t'] or 0,
        'total_revenue':        bookings.filter(status='delivered').aggregate(t=Sum('final_price'))['t'] or 0,
        'cash_revenue':         bookings.filter(status='delivered', payment_method='cash',
                                    scheduled_date__month=today.month,
                                    scheduled_date__year=today.year,
                                ).aggregate(t=Sum('final_price'))['t'] or 0,
        'online_revenue':       bookings.filter(status='delivered',
                                    scheduled_date__month=today.month,
                                    scheduled_date__year=today.year,
                                ).exclude(payment_method='cash').aggregate(t=Sum('final_price'))['t'] or 0,
        'avg_rating':           Review.objects.filter(booking__garage=garage).aggregate(avg=Avg('rating'))['avg'],
        'recent_bookings':      bookings.select_related('service', 'customer', 'vehicle', 'garage', 'mechanic', 'job').order_by('-created_at')[:50],
        'cancelled_count':      cancelled_count,
        'completed_count':      completed_count,
        'total_bookings_count': bookings.count(),
        'mechanics':            MechanicProfile.objects.filter(garage=garage).select_related('mechanic') if garage else [],
    })


# ═══════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ═══════════════════════════════════════════════════════════════

@login_required
def adminNetworkFinanceView(request):
    """Admin network view — all garages, revenue comparison, busiest garage."""
    if not (request.user.is_super_admin or
            (request.user.role == 'admin' and request.user.admin_approved)):
        return redirect('dashboard')

    today       = timezone.now().date()
    month_start = today.replace(day=1)

    garages = Garage.objects.filter(
        approval_status='approved'
    ).select_related('manager').order_by('-wallet_balance')

    garage_data = []
    for g in garages:
        bookings = Booking.objects.filter(garage=g, payment_status='paid')
        garage_data.append({
            'garage':        g,
            'today_rev':     float(bookings.filter(job__wallet_released=True,
                               job__completed_at__date=today
                             ).aggregate(t=Sum('final_price'))['t'] or 0),
            'month_rev':     float(bookings.filter(job__wallet_released=True,
                               job__completed_at__date__gte=month_start
                             ).aggregate(t=Sum('final_price'))['t'] or 0),
            'total_rev':     float(bookings.filter(job__wallet_released=True
                             ).aggregate(t=Sum('final_price'))['t'] or 0),
            'wallet':        float(g.wallet_balance),
            'total_bookings':bookings.count(),
            'today_bookings':Booking.objects.filter(garage=g, scheduled_date=today).count(),
            'mechanic_count':MechanicProfile.objects.filter(garage=g, status='approved').count(),
            'active_jobs':   Job.objects.filter(booking__garage=g,
                               status__in=['in_progress','accepted','on_way','arrived']).count(),
            'avg_rating':    Review.objects.filter(booking__garage=g
                             ).aggregate(avg=Avg('rating'))['avg'],
        })

    # Sort by total revenue
    garage_data.sort(key=lambda x: x['total_rev'], reverse=True)

    # Network totals
    net_today   = sum(g['today_rev'] for g in garage_data)
    net_month   = sum(g['month_rev'] for g in garage_data)
    net_total   = sum(g['total_rev'] for g in garage_data)
    net_wallets = sum(g['wallet'] for g in garage_data)

    return render(request, 'core/admin/finance.html', {
        'garage_data':   garage_data,
        'net_today':     net_today,
        'net_month':     net_month,
        'net_total':     net_total,
        'net_wallets':   net_wallets,
        'total_garages': len(garage_data),
        'total_bookings':Booking.objects.count(),
        'active_jobs':   Job.objects.filter(status__in=['in_progress','accepted']).count(),
        'today':         today,
    })


@login_required
def adminDashboardView(request):
    if not (request.user.is_super_admin or
            (request.user.role == 'admin' and request.user.admin_approved) or
            request.user.is_staff):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    is_super = request.user.is_super_admin
    is_sub   = (request.user.role == 'admin' and request.user.admin_approved
                and not request.user.is_super_admin)

    pending_admin_requests   = []
    pending_garages          = []
    pending_individual_mechs = []
    pending_managers         = []

    # ── SUPER ADMIN: sees and can approve everything ──
    if is_super:
        pending_admin_requests  = AdminRequest.objects.filter(
            status='pending').select_related('user').order_by('-created_at')
        pending_garages         = Garage.objects.filter(
            approval_status='pending').select_related('manager').order_by('-created_at')
        pending_individual_mechs = IndividualMechanicProfile.objects.filter(
            status='pending').select_related('mechanic').order_by('-created_at')
        pending_managers = User.objects.filter(
            role='manager', manager_approved=False, is_active=True
        ).order_by('-date_joined')

    # ── SUB ADMIN: can only approve managers + individual mechanics ──
    elif is_sub:
        pending_individual_mechs = IndividualMechanicProfile.objects.filter(
            status='pending').select_related('mechanic').order_by('-created_at')
        pending_managers = User.objects.filter(
            role='manager', manager_approved=False, is_active=True
        ).order_by('-date_joined')

    ctx = {
        'is_super':                is_super,
        'is_sub':                  is_sub,
        'pending_admin_requests':  pending_admin_requests,
        'pending_garages':         pending_garages,
        'pending_individual_mechs': pending_individual_mechs,
        'pending_count':           len(pending_admin_requests),
        'pending_garages_count':   len(pending_garages),
        'pending_mechs_count':     len(pending_individual_mechs),
        'pending_managers':        pending_managers,
        'pending_managers_count':  len(pending_managers),
        'total_users':             User.objects.count(),
        'total_garages':           Garage.objects.filter(approval_status='approved').count(),
        'total_bookings':          Booking.objects.count(),
        'total_mechanics':         User.objects.filter(role='mechanic').count(),
        'pending_bookings':        Booking.objects.filter(status='confirmed').count(),
        'active_jobs':             Job.objects.filter(status='in_progress').count(),
        'month_revenue':           Booking.objects.filter(
            payment_status='paid', created_at__month=timezone.now().month
        ).aggregate(total=Sum('final_price'))['total'] or 0,
        'recent_users':            User.objects.order_by('-date_joined')[:8],
        'recent_bookings':         Booking.objects.select_related(
            'customer','service','garage').order_by('-created_at')[:10],
        'garages':                 Garage.objects.select_related('manager').all(),
        'all_admins':              User.objects.filter(role='admin').order_by('-date_joined'),
    }
    return render(request, 'core/admin/panel.html', ctx)


@login_required
@require_POST
def addSubAdminView(request):
    """Only super admins can add sub-admins directly. Sub-admins get an email with login info."""
    if not request.user.is_super_admin:
        messages.error(request, 'Only Super Admins can add admins.')
        return redirect('admin_panel')

    name     = request.POST.get('name', '').strip()
    email    = request.POST.get('email', '').strip().lower()
    phone    = request.POST.get('phone', '').strip()
    password = request.POST.get('password', '').strip()

    if not name or not email or not password:
        messages.error(request, 'Name, email and password are all required.')
        return redirect('admin_panel')
    if len(password) < 6:
        messages.error(request, 'Password must be at least 6 characters.')
        return redirect('admin_panel')
    if User.objects.filter(email=email).exists():
        messages.error(request, f'A user with email {email} already exists.')
        return redirect('admin_panel')

    # Create the sub-admin user
    new_admin = User.objects.create_user(
        email=email,
        name=name,
        phone=phone,
        password=password,
        role='admin',
        admin_approved=True,
        is_staff=True,
        manager_created=False,
    )

    # Send welcome email with credentials
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    subject  = f'🎉 Welcome to eGarage Admin Panel — {name}'
    html_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:540px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08);">
      <div style="background:linear-gradient(135deg,#e8192c,#c0111f);padding:28px 32px;">
        <div style="font-family:'Segoe UI',Arial;font-size:22px;font-weight:900;color:#fff;letter-spacing:-0.5px;">eGarage Admin Access</div>
        <div style="font-size:13px;color:rgba(255,255,255,.7);margin-top:4px;">You've been added as a Sub-Admin</div>
      </div>
      <div style="padding:28px 32px;">
        <p style="font-size:15px;color:#111;margin-bottom:6px;">Hi <strong>{name}</strong>,</p>
        <p style="font-size:14px;color:#555;line-height:1.7;margin-bottom:20px;">
          <strong>{request.user.name}</strong> has added you as a <strong>Sub-Admin</strong> on eGarage.
          You now have access to the admin panel to manage garages, mechanics and managers.
        </p>

        <div style="background:#f8f9fa;border:1px solid #e0e0e0;border-radius:10px;padding:18px 20px;margin-bottom:22px;">
          <div style="font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#888;margin-bottom:12px;">Your Login Credentials</div>
          <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;font-size:14px;">
            <span style="color:#888;">Login URL</span>
            <a href="{site_url}/login/" style="color:#e8192c;font-weight:600;text-decoration:none;">{site_url}/login/</a>
          </div>
          <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;font-size:14px;">
            <span style="color:#888;">Email</span>
            <strong style="color:#111;">{email}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;padding:8px 0;font-size:14px;">
            <span style="color:#888;">Password</span>
            <strong style="color:#111;font-family:monospace;font-size:15px;">{password}</strong>
          </div>
        </div>

        <div style="background:#fff8f0;border:1px solid #fde68a;border-radius:9px;padding:13px 16px;margin-bottom:22px;font-size:13px;color:#92400e;">
          ⚠️ <strong>Important:</strong> Please change your password after first login via <strong>Profile → Change Password</strong>.
        </div>

        <div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;">What you can do as Sub-Admin:</div>
        <div style="font-size:13px;color:#555;line-height:1.8;">
          ✅ Approve or reject garage managers<br>
          ✅ Approve or reject garages<br>
          ✅ Approve individual mechanics<br>
          ✅ View all users, bookings and garages<br>
          ✅ Access Django admin panel
        </div>

        <div style="margin-top:24px;">
          <a href="{site_url}/login/" style="display:inline-block;padding:12px 28px;background:linear-gradient(135deg,#e8192c,#c0111f);color:#fff;text-decoration:none;border-radius:9px;font-size:14px;font-weight:700;box-shadow:0 4px 14px rgba(232,25,44,.3);">
            Login to Admin Panel →
          </a>
        </div>
      </div>
      <div style="background:#f8f9fa;padding:16px 32px;border-top:1px solid #e0e0e0;font-size:12px;color:#aaa;">
        This email was sent by <strong style="color:#e8192c;">eGarage</strong> because {request.user.name} added you as an admin. If this is a mistake, ignore this email.
      </div>
    </div>
    """

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=f'Hi {name}, you have been added as Sub-Admin on eGarage. Login: {site_url}/login/ | Email: {email} | Password: {password}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send()
        email_sent = True
    except Exception as e:
        logger.error(f'Sub-admin email failed: {e}')
        email_sent = False

    # Notify the new admin in-app too
    create_notification(new_admin,
        f'🎉 Welcome to eGarage Admin Panel!',
        f'You have been added as Sub-Admin by {request.user.name}. '
        f'Login with your email and the password shared with you.', 'account')

    msg_text = f'✅ Sub-Admin {name} created successfully!'
    if email_sent:
        msg_text += f' Welcome email sent to {email}.'
    else:
        msg_text += f' (Email could not be sent — share credentials manually.)'
    messages.success(request, msg_text)
    return redirect('admin_panel')


@login_required
def requestAdminView(request):
    if request.user.is_super_admin:
        return redirect('admin_panel')
    # Only managers and existing admins can request admin access
    if request.user.role not in ('manager', 'admin'):
        messages.error(request, 'Only Garage Managers and Admins can request admin access.')
        return redirect('dashboard')
    existing = AdminRequest.objects.filter(user=request.user).first()
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason.')
            return redirect('request_admin')
        if existing:
            if existing.status == 'pending':
                messages.info(request, 'Already pending.')
                return redirect('dashboard')
            elif existing.status == 'approved':
                messages.info(request, 'Already approved.')
                return redirect('dashboard')
            else:
                existing.reason = reason; existing.status = 'pending'
                existing.reviewed_at = None; existing.reject_reason = ''
                existing.save()
        else:
            AdminRequest.objects.create(user=request.user, reason=reason)
        for sa in User.objects.filter(is_super_admin=True):
            create_notification(sa, f'New Admin Request from {request.user.name}',
                f'{request.user.name} ({request.user.email}) requested admin access.', 'system')
        messages.success(request, '✅ Request submitted! Super Admin will review it.')
        return redirect('dashboard')
    return render(request, 'core/auth/request_admin.html', {'existing': existing})


# ── ADMIN AJAX APIs ─────────────────────────────────────────────

@login_required
@require_POST
def approveAdminRequest(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        req = AdminRequest.objects.select_related('user').get(pk=pk)
        req.status = 'approved'; req.reviewed_at = timezone.now(); req.reviewed_by = request.user
        req.save()
        req.user.role = 'admin'; req.user.admin_approved = True; req.user.is_staff = True
        req.user.save(update_fields=['role','admin_approved','is_staff'])
        create_notification(req.user, '🎉 Admin access approved!',
            f'Approved by {request.user.name}. Login as Admin.', 'system')
        return JsonResponse({'ok': True, 'name': req.user.name})
    except AdminRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def rejectAdminRequest(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        data   = json.loads(request.body)
        reason = data.get('reason', 'Rejected by Super Admin.')
        req    = AdminRequest.objects.select_related('user').get(pk=pk)
        req.status = 'rejected'; req.reviewed_at = timezone.now()
        req.reviewed_by = request.user; req.reject_reason = reason; req.save()
        create_notification(req.user, '❌ Admin request rejected', f'Reason: {reason}', 'system')
        return JsonResponse({'ok': True})
    except AdminRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def approveGarageView(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        garage = Garage.objects.select_related('manager').get(pk=pk)
        garage.approval_status = 'approved'
        garage.approved_by     = request.user
        garage.approved_at     = timezone.now()
        garage.is_active       = True
        garage.save(update_fields=['approval_status','approved_by','approved_at','is_active'])
        if garage.manager:
            create_notification(garage.manager,
                f'🏢 Garage "{garage.name}" approved!',
                f'Your garage is now live on the map. Customers can book services.',
                'system')
        return JsonResponse({'ok': True, 'name': garage.name})
    except Garage.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def rejectGarageView(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        data   = json.loads(request.body)
        reason = data.get('reason', 'Does not meet requirements.')
        garage = Garage.objects.select_related('manager').get(pk=pk)
        garage.approval_status  = 'rejected'
        garage.rejection_reason = reason
        garage.is_active        = False
        garage.save(update_fields=['approval_status','rejection_reason','is_active'])
        if garage.manager:
            create_notification(garage.manager,
                f'❌ Garage rejected: {garage.name}',
                f'Reason: {reason}. Please update details and resubmit.', 'system')
        return JsonResponse({'ok': True})
    except Garage.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def approveIndividualMechView(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        profile = IndividualMechanicProfile.objects.select_related('mechanic').get(pk=pk)
        profile.status      = 'approved'
        profile.approved_by = request.user
        profile.approved_at = timezone.now()
        profile.save()
        profile.mechanic.is_individual = True
        profile.mechanic.save(update_fields=['is_individual'])
        create_notification(profile.mechanic,
            '🎉 Individual Mechanic Application Approved!',
            f'You can now receive jobs in {profile.service_cities}.', 'account')
        return JsonResponse({'ok': True, 'name': profile.mechanic.name})
    except IndividualMechanicProfile.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def rejectIndividualMechView(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        data    = json.loads(request.body)
        reason  = data.get('reason', 'Does not meet requirements.')
        profile = IndividualMechanicProfile.objects.select_related('mechanic').get(pk=pk)
        profile.status           = 'rejected'
        profile.rejection_reason = reason
        profile.save()
        create_notification(profile.mechanic,
            '❌ Individual Mechanic Application Rejected',
            f'Reason: {reason}', 'account')
        return JsonResponse({'ok': True})
    except IndividualMechanicProfile.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def toggleUserActive(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        user = User.objects.get(pk=pk)
        if user == request.user:
            return JsonResponse({'ok': False, 'error': 'Cannot deactivate yourself.'})
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return JsonResponse({'ok': True, 'is_active': user.is_active, 'name': user.name})
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def makeSuperAdmin(request, pk):
    if not request.user.is_super_admin:
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        user = User.objects.get(pk=pk)
        user.is_super_admin = True; user.admin_approved = True
        user.is_staff = True; user.is_superuser = True; user.role = 'admin'
        user.save()
        create_notification(user, '⭐ You are now Super Admin!',
            f'Granted by {request.user.name}.', 'system')
        return JsonResponse({'ok': True, 'name': user.name})
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found.'}, status=404)


# ═══════════════════════════════════════════════════════════════
#  MANAGER APPROVAL
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def approveManagerView(request, pk):
    """Admin approves a manager account."""
    if not (request.user.is_super_admin or
            (request.user.role == 'admin' and request.user.admin_approved)):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        user = User.objects.get(pk=pk, role='manager')
        user.manager_approved = True
        user.save(update_fields=['manager_approved'])
        create_notification(
            user,
            '✅ Manager account approved!',
            f'Your manager account has been approved by {request.user.name}. '
            f'You can now login and set up your garage at eGarage.',
            'account'
        )
        return JsonResponse({'ok': True, 'name': user.name, 'email': user.email})
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Manager not found.'}, status=404)


@login_required
@require_POST
def rejectManagerView(request, pk):
    """Admin rejects a manager account."""
    if not (request.user.is_super_admin or
            (request.user.role == 'admin' and request.user.admin_approved)):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        data   = json.loads(request.body)
        reason = data.get('reason', 'Your manager request was not approved.')
        user   = User.objects.get(pk=pk, role='manager')
        user.is_active = False
        user.save(update_fields=['is_active'])
        create_notification(
            user,
            '❌ Manager request rejected',
            f'Reason: {reason}. Please contact support for more information.',
            'account'
        )
        return JsonResponse({'ok': True})
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Manager not found.'}, status=404)


# ═══════════════════════════════════════════════════════════════
#  MECHANIC — JOIN GARAGE REQUEST
# ═══════════════════════════════════════════════════════════════

@login_required
def requestJoinGarageView(request, pk):
    """Mechanic requests to join a specific garage."""
    garage = get_object_or_404(Garage, pk=pk, is_active=True, approval_status='approved')

    if MechanicRequest.objects.filter(mechanic=request.user, garage=garage).exists():
        messages.info(request, 'You already have a request for this garage.')
        return redirect('garage_finder')

    if request.method == 'POST':
        message = request.POST.get('message', '')
        MechanicRequest.objects.create(
            mechanic=request.user,
            garage=garage,
            message=message,
        )
        if garage.manager:
            create_notification(garage.manager,
                f'🔧 Mechanic {request.user.name} wants to join your garage',
                f'{request.user.name} ({request.user.city}) sent a join request. '
                f'Review in Team Management.', 'mechanic')
        messages.success(request, f'✅ Request sent to {garage.name}!')
        return redirect('dashboard')

    return render(request, 'core/individual/join_garage.html', {'garage': garage})


import datetime

@login_required
@require_POST
def cancelBookingView(request, ref):
    """
    Cancel a booking with refund policy:
      - Cancelled 6+ hours before slot  → 100% refund
      - Cancelled <6 hours before slot  → 50% refund
      - Service already started         → No refund
    """
    from django.utils import timezone as tz
    import json

    try:
        booking = Booking.objects.get(reference=ref, customer=request.user)
    except Booking.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Booking not found'}, status=404)

    if booking.status in ('in_progress', 'quality_check', 'at_garage', 'delivered', 'cancelled'):
        return JsonResponse({'ok': False, 'error': 'Cannot cancel at this stage'}, status=400)

    reason = request.POST.get('reason', '') or json.loads(request.body).get('reason', '')

    # ── REFUND POLICY ──
    now = tz.now()
    scheduled_dt = tz.make_aware(
        datetime.datetime.combine(booking.scheduled_date, booking.scheduled_slot)
    )
    hours_until = (scheduled_dt - now).total_seconds() / 3600

    if booking.status == 'in_progress':
        refund_pct  = 0
        refund_msg  = 'No refund — service already started.'
    elif hours_until >= 6:
        refund_pct  = 100
        refund_msg  = f'Full refund of ₹{booking.advance_amount:.0f} will be credited in 24 hours.'
    else:
        refund_pct  = 50
        refund_msg  = f'50% refund (₹{booking.advance_amount * 0.5:.0f}) credited in 24 hours (cancelled < 6 hrs before slot).'

    refund_amount = booking.advance_amount * (refund_pct / 100) if booking.advance_paid else 0

    # Save cancellation + refund amount
    booking.status = 'cancelled'
    booking.cancellation_reason = reason
    # Store refund info if model has these fields (graceful)
    try:
        booking.refund_amount = refund_amount
        booking.refund_pct    = refund_pct
        booking.save(update_fields=['status', 'cancellation_reason', 'refund_amount', 'refund_pct'])
    except Exception:
        booking.save(update_fields=['status', 'cancellation_reason'])

    # Rich notification for customer — shows on website
    website_msg = (
        f'❌ Your booking {booking.reference} for {booking.service.name if booking.service else "service"} '
        f'has been cancelled.\n\n'
        f'💰 Refund Policy: {refund_msg}\n\n'
        f'The refund will be credited to your original payment method within 24 hours.'
        if refund_amount > 0 else
        f'❌ Your booking {booking.reference} has been cancelled. {refund_msg}'
    )
    create_notification(
        request.user,
        'Booking Cancelled — Refund Initiated' if refund_amount > 0 else 'Booking Cancelled',
        website_msg,
        notif_type='payment',
        booking=booking
    )

    # Notify garage manager
    if booking.garage and booking.garage.manager:
        create_notification(
            booking.garage.manager,
            f'Booking Cancelled — {booking.reference}',
            f'{booking.customer_name} cancelled booking {booking.reference}. '
            f'Reason: {reason or "Not specified"}. '
            f'Refund: {refund_msg}',
            notif_type='booking',
            booking=booking
        )

    return JsonResponse({
        'ok': True,
        'refund_pct': refund_pct,
        'refund_amount': float(refund_amount),
        'refund_msg': refund_msg,
        'status': 'cancelled'
    })