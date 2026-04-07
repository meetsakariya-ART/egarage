"""
core/signals.py
────────────────
Django signals for eGarage.
Auto-creates notifications when booking/job status changes.

Registered in core/apps.py — no manual wiring needed.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


# ── LAZY IMPORTS (avoid circular imports) ────────────────────
def get_models():
    from .models import Booking, Job, Review, Notification, User
    return Booking, Job, Review, Notification, User


def create_notif(user, title, message, notif_type='booking'):
    """Helper to safely create a notification."""
    try:
        from .models import Notification
        Notification.objects.create(
            user=user, title=title, message=message, type=notif_type
        )
    except Exception:
        pass


# ── BOOKING STATUS CHANGE ─────────────────────────────────────
_booking_prev_status = {}

@receiver(pre_save, sender='core.Booking')
def booking_pre_save(sender, instance, **kwargs):
    """Store previous status before save."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            _booking_prev_status[instance.pk] = old.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.Booking')
def booking_post_save(sender, instance, created, **kwargs):
    """Send notification when booking is created or status changes."""

    if created:
        # New booking — notify customer
        create_notif(
            instance.customer,
            f'Booking {instance.reference} confirmed ✅',
            f'Your {instance.service.name if instance.service else "service"} '
            f'is booked for {instance.scheduled_date}.',
            'booking'
        )
        # Notify manager
        if instance.garage and instance.garage.manager:
            create_notif(
                instance.garage.manager,
                f'New booking: {instance.reference}',
                f'{instance.customer_name} booked {instance.service.name if instance.service else "a service"} '
                f'for {instance.scheduled_date}.',
                'booking'
            )
        return

    # Status changed
    prev = _booking_prev_status.pop(instance.pk, None)
    if prev and prev != instance.status:

        msg_map = {
            'picked_up':     ('🚗 Vehicle picked up!', 'Your vehicle has been picked up by our team.'),
            'at_garage':     ('🏢 Vehicle at garage', 'Your vehicle has arrived at the garage.'),
            'in_progress':   ('🔧 Service started', 'Our mechanic has started working on your vehicle.'),
            'quality_check': ('🔍 Quality check', 'Service done! Final quality check in progress.'),
            'delivered':     ('🎉 Vehicle delivered!', 'Your vehicle is ready. Thank you for choosing eGarage!'),
            'cancelled':     ('❌ Booking cancelled', f'Your booking {instance.reference} has been cancelled.'),
        }

        if instance.status in msg_map:
            title, message = msg_map[instance.status]
            create_notif(instance.customer, title, message, 'booking')


# ── JOB STATUS CHANGE ─────────────────────────────────────────
_job_prev_status = {}

@receiver(pre_save, sender='core.Job')
def job_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            _job_prev_status[instance.pk] = old.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.Job')
def job_post_save(sender, instance, created, **kwargs):
    prev = _job_prev_status.pop(instance.pk, None)
    if not created and prev and prev != instance.status:

        if instance.status == 'in_progress' and instance.mechanic:
            # Notify customer that mechanic started
            try:
                booking = instance.booking
                create_notif(
                    booking.customer,
                    f'🔧 {instance.mechanic.name} started your service',
                    f'Mechanic {instance.mechanic.name} has started working on '
                    f'your {booking.vehicle.brand if booking.vehicle else "vehicle"}.',
                    'service'
                )
            except Exception:
                pass

        if instance.status == 'completed':
            try:
                booking = instance.booking
                # Update booking status
                if booking.status == 'in_progress':
                    booking.status = 'quality_check'
                    booking.save(update_fields=['status'])
                # Notify customer
                create_notif(
                    booking.customer,
                    '✅ Job completed! Quality check in progress.',
                    f'Your {booking.service.name if booking.service else "service"} '
                    f'is done. Final inspection underway.',
                    'service'
                )
            except Exception:
                pass


# ── REVIEW CREATED ────────────────────────────────────────────
@receiver(post_save, sender='core.Review')
def review_post_save(sender, instance, created, **kwargs):
    if created:
        try:
            booking = instance.booking
            if booking.mechanic:
                stars = '★' * instance.rating + '☆' * (5 - instance.rating)
                create_notif(
                    booking.mechanic,
                    f'New review: {stars} from {booking.customer_name}',
                    instance.text[:120] if instance.text else 'Customer left a rating.',
                    'service'
                )
        except Exception:
            pass