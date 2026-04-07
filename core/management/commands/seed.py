"""
core/management/commands/seed.py
──────────────────────────────────
Seeds ONLY real platform data:
  - Service categories and types
  - Discount coupons

Does NOT create:
  - Fake users
  - Fake vehicles
  - Fake bookings
  - Fake mechanics
  - Fake notifications

Usage:
  python manage.py seed           # seed services + coupons
  python manage.py seed --clear   # clear services/coupons then reseed
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed eGarage with real service data only (no fake users or vehicles)'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Clear existing services and coupons first')

    def handle(self, *args, **options):
        from core.models import Service, Coupon

        if options['clear']:
            self.stdout.write('🗑️  Clearing services and coupons...')
            Service.objects.all().delete()
            Coupon.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✅ Cleared'))

        # ── SERVICES ────────────────────────────────────────────
        self.stdout.write('🔧 Creating services...')

        services = [
            {
                'name':          'Standard Car Service',
                'slug':          'car-service',
                'icon_emoji':    '🔧',
                'description':   'Complete engine oil change, oil filter, air filter check, brake inspection, tyre pressure check and 30-point safety report.',
                'category':      'car',
                'price_basic':   1999,
                'price_standard':3999,
                'price_premium': 6999,
                'duration_hours':3,
                'warranty_days': 1000,
                'order':         1,
            },
            {
                'name':          'Comprehensive Car Service',
                'slug':          'comprehensive-service',
                'icon_emoji':    '⚙️',
                'description':   'Deep service including engine flush, transmission check, coolant top-up, AC check and all filters.',
                'category':      'car',
                'price_basic':   4999,
                'price_standard':6999,
                'price_premium': 9999,
                'duration_hours':4,
                'warranty_days': 1000,
                'order':         2,
            },
            {
                'name':          'AC Full Service',
                'slug':          'ac-service',
                'icon_emoji':    '❄️',
                'description':   'AC pressure check, refrigerant gas refill (R134a), condenser cleaning, cabin filter replacement and vent sanitization.',
                'category':      'both',
                'price_basic':   999,
                'price_standard':1499,
                'price_premium': 1999,
                'duration_hours':2,
                'warranty_days': 180,
                'order':         3,
            },
            {
                'name':          'AC Gas Refill',
                'slug':          'ac-gas-refill',
                'icon_emoji':    '🌡️',
                'description':   'Top up R134a refrigerant gas with leak detection test.',
                'category':      'both',
                'price_basic':   599,
                'price_standard':799,
                'price_premium': 999,
                'duration_hours':1,
                'warranty_days': 90,
                'order':         4,
            },
            {
                'name':          'Denting & Painting',
                'slug':          'denting-painting',
                'icon_emoji':    '🎨',
                'description':   'Minor dent removal, scratch repair and OEM colour matching with professional finish.',
                'category':      'both',
                'price_basic':   2999,
                'price_standard':4999,
                'price_premium': 7999,
                'duration_hours':5,
                'warranty_days': 365,
                'order':         5,
            },
            {
                'name':          'Wheel Balancing & Alignment',
                'slug':          'wheel-alignment',
                'icon_emoji':    '🔵',
                'description':   'Computer-assisted 4-wheel alignment and dynamic balancing with nitrogen tyre inflation.',
                'category':      'both',
                'price_basic':   799,
                'price_standard':999,
                'price_premium': 1299,
                'duration_hours':1,
                'warranty_days': 90,
                'order':         6,
            },
            {
                'name':          'Tyre Replacement',
                'slug':          'tyre-replacement',
                'icon_emoji':    '🔄',
                'description':   'Tyre fitting, balancing and nitrogen inflation. Price per tyre varies by size.',
                'category':      'both',
                'price_basic':   2499,
                'price_standard':3499,
                'price_premium': 4999,
                'duration_hours':1,
                'warranty_days': 365,
                'order':         7,
            },
            {
                'name':          'Battery Replacement',
                'slug':          'battery-replacement',
                'icon_emoji':    '🔋',
                'description':   'Battery health test, terminal cleaning and OEM battery fitment with 1-year warranty.',
                'category':      'both',
                'price_basic':   3499,
                'price_standard':4999,
                'price_premium': 6499,
                'duration_hours':1,
                'warranty_days': 365,
                'order':         8,
            },
            {
                'name':          'Brake Service',
                'slug':          'brake-service',
                'icon_emoji':    '🛑',
                'description':   'Brake pad replacement, disc inspection, brake fluid check and caliper cleaning.',
                'category':      'both',
                'price_basic':   1499,
                'price_standard':1999,
                'price_premium': 2999,
                'duration_hours':2,
                'warranty_days': 180,
                'order':         9,
            },
            {
                'name':          'Car Detailing & Cleaning',
                'slug':          'car-detailing',
                'icon_emoji':    '✨',
                'description':   'Machine polish, ceramic coating, leather conditioning, engine bay cleaning and tyre dressing.',
                'category':      'both',
                'price_basic':   1499,
                'price_standard':2499,
                'price_premium': 3999,
                'duration_hours':4,
                'warranty_days': 30,
                'order':         10,
            },
            {
                'name':          'Windscreen Replacement',
                'slug':          'windscreen',
                'icon_emoji':    '🪟',
                'description':   'Crack filling, chip repair or full windscreen replacement with OEM glass.',
                'category':      'both',
                'price_basic':   3999,
                'price_standard':5999,
                'price_premium': 7999,
                'duration_hours':2,
                'warranty_days': 180,
                'order':         11,
            },
            {
                'name':          'Suspension & Steering',
                'slug':          'suspension',
                'icon_emoji':    '🛞',
                'description':   'Shock absorber check, steering alignment, bushing inspection and suspension repair.',
                'category':      'both',
                'price_basic':   1999,
                'price_standard':2999,
                'price_premium': 5999,
                'duration_hours':3,
                'warranty_days': 365,
                'order':         12,
            },
            {
                'name':          'Pre-purchase Inspection',
                'slug':          'inspection',
                'icon_emoji':    '🔍',
                'description':   '100-point inspection report for used car buyers. Full mechanical and body check with detailed report.',
                'category':      'both',
                'price_basic':   799,
                'price_standard':1299,
                'price_premium': 2499,
                'duration_hours':2,
                'warranty_days': 0,
                'order':         13,
            },
            {
                'name':          'Bike Service',
                'slug':          'bike-service',
                'icon_emoji':    '🏍️',
                'description':   'Complete two-wheeler service including engine oil, chain lubrication, brake check and electrical inspection.',
                'category':      'bike',
                'price_basic':   499,
                'price_standard':799,
                'price_premium': 1299,
                'duration_hours':2,
                'warranty_days': 90,
                'order':         14,
            },
        ]

        created_count = 0
        for svc in services:
            _, created = Service.objects.get_or_create(
                slug=svc['slug'],
                defaults={**svc, 'is_active': True}
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'  ✅ {created_count} new services created ({len(services)} total)'
        ))

        # ── COUPONS ──────────────────────────────────────────────
        self.stdout.write('🏷️  Creating coupons...')

        coupons = [
            {
                'code':          'WELCOME500',
                'discount_type': 'flat',
                'amount':        500,
                'min_order':     2000,
                'max_discount':  500,
            },
            {
                'code':          'EGARAGE10',
                'discount_type': 'percent',
                'amount':        10,
                'min_order':     1500,
                'max_discount':  750,
            },
            {
                'code':          'FIRST15',
                'discount_type': 'percent',
                'amount':        15,
                'min_order':     3000,
                'max_discount':  1000,
            },
            {
                'code':          'SAVE200',
                'discount_type': 'flat',
                'amount':        200,
                'min_order':     1000,
                'max_discount':  200,
            },
        ]

        coupon_count = 0
        for cd in coupons:
            _, created = Coupon.objects.get_or_create(
                code=cd['code'],
                defaults={**cd, 'is_active': True}
            )
            if created:
                coupon_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'  ✅ {coupon_count} new coupons created ({len(coupons)} total)'
        ))

        # ── SUMMARY ──────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('══════════════════════════════════════'))
        self.stdout.write(self.style.SUCCESS('  ✅ SEED COMPLETE — No fake data'))
        self.stdout.write(self.style.SUCCESS('══════════════════════════════════════'))
        self.stdout.write('')
        self.stdout.write('  Services available:  ' + str(Service.objects.count()))
        self.stdout.write('  Coupons available:   ' + str(Coupon.objects.count()))
        self.stdout.write('')
        self.stdout.write('  ℹ️  All users, garages, mechanics must be added')
        self.stdout.write('     through the platform — no fake accounts created.')
        self.stdout.write('')
        self.stdout.write('  Next steps:')
        self.stdout.write('  1. Login as Super Admin at /login/')
        self.stdout.write('  2. Managers sign up → approve them at /admin-panel/')
        self.stdout.write('  3. Managers add garage → approve at /admin-panel/')
        self.stdout.write('  4. Managers add mechanics at /team/')
        self.stdout.write('')