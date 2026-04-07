"""
core/models.py  —  eGarage Complete Models
==========================================
All models for the full platform.
After changes run:
  python manage.py makemigrations
  python manage.py migrate
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


# ═══════════════════════════════════════════════════════════════
#  USER
# ═══════════════════════════════════════════════════════════════

class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user  = self.model(email=email, name=name, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra):
        extra.setdefault('is_staff',       True)
        extra.setdefault('is_superuser',   True)
        extra.setdefault('is_super_admin', True)
        extra.setdefault('role',           'admin')
        return self.create_user(email, name, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('owner',    'Vehicle Owner'),
        ('mechanic', 'Mechanic'),
        ('manager',  'Garage Manager'),
        ('admin',    'Admin'),
    ]
    GENDER_CHOICES = [('M','Male'),('F','Female'),('O','Other')]
    BLOOD_CHOICES  = [('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),
                      ('O+','O+'),('O-','O-'),('AB+','AB+'),('AB-','AB-')]

    # Core
    email = models.EmailField(unique=True)
    name  = models.CharField(max_length=120)
    phone = models.CharField(max_length=15, blank=True)
    role  = models.CharField(max_length=10, choices=ROLE_CHOICES, default='owner')
    city  = models.CharField(max_length=60, blank=True)
    state = models.CharField(max_length=60, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    # Profile
    profile_photo     = models.ImageField(upload_to='profiles/', blank=True, null=True)
    whatsapp          = models.CharField(max_length=15, blank=True)
    address           = models.TextField(blank=True)
    date_of_birth     = models.DateField(null=True, blank=True)
    gender            = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    blood_group       = models.CharField(max_length=3, choices=BLOOD_CHOICES, blank=True)
    emergency_contact = models.CharField(max_length=120, blank=True)

    # Location (for mechanic GPS)
    current_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_seen   = models.DateTimeField(null=True, blank=True)

    # Flags
    is_active       = models.BooleanField(default=True)
    is_staff          = models.BooleanField(default=False)
    is_admin          = models.BooleanField(default=False)
    is_super_admin    = models.BooleanField(default=False)  # No OTP, full control
    admin_approved    = models.BooleanField(default=False)  # Approved by super admin
    manager_approved  = models.BooleanField(default=False)  # Manager approved by admin
    is_available      = models.BooleanField(default=True)   # Mechanic on/off duty
    is_individual     = models.BooleanField(default=False)  # Independent mechanic
    manager_created   = models.BooleanField(default=False)  # Created by manager — skip OTP on login

    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['name']
    objects = UserManager()

    class Meta:
        verbose_name = 'User'

    def __str__(self):
        return f'{self.name} ({self.email})'

    @property
    def initials(self):
        parts = self.name.split()
        return ''.join(p[0].upper() for p in parts[:2])

    @property
    def full_role(self):
        if self.is_super_admin:
            return 'Super Admin'
        if self.is_individual:
            return 'Individual Mechanic'
        return dict(self.ROLE_CHOICES).get(self.role, self.role)


# ═══════════════════════════════════════════════════════════════
#  ADMIN REQUEST  (request admin access → super admin approves)
# ═══════════════════════════════════════════════════════════════

class AdminRequest(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_request')
    reason        = models.TextField()
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at    = models.DateTimeField(auto_now_add=True)
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    reviewed_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='reviewed_admin_requests')
    reject_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.name} → {self.status}'


# ═══════════════════════════════════════════════════════════════
#  GARAGE
# ═══════════════════════════════════════════════════════════════

class Garage(models.Model):
    APPROVAL_CHOICES = [
        ('pending',  'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    name    = models.CharField(max_length=200)
    slug    = models.SlugField(unique=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='managed_garages',
                                limit_choices_to={'role': 'manager'})

    # Location
    address  = models.TextField()
    area     = models.CharField(max_length=120, blank=True)
    city     = models.CharField(max_length=80)
    state    = models.CharField(max_length=80, default='Gujarat')
    pincode  = models.CharField(max_length=10, blank=True)
    landmark = models.CharField(max_length=200, blank=True,
                                help_text='e.g. Opposite Punit Nagar Water Tank')
    maps_link = models.URLField(blank=True,
                                help_text='Paste your Google Maps share link here')
    lat      = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng      = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Contact
    phone   = models.CharField(max_length=15, blank=True)
    email   = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # Business
    gst_number           = models.CharField(max_length=20, blank=True)
    capacity_per_day     = models.PositiveIntegerField(default=20)
    free_pickup_radius_km = models.PositiveIntegerField(default=15)
    pickup_charge_per_km  = models.DecimalField(max_digits=6, decimal_places=2, default=25)
    opening_year         = models.PositiveIntegerField(null=True, blank=True)
    description          = models.TextField(blank=True)

    logo       = models.ImageField(upload_to='garage_logos/', blank=True, null=True)
    cover_photo = models.ImageField(upload_to='garage_covers/', blank=True, null=True)

    # Admin approval
    approval_status  = models.CharField(max_length=10, choices=APPROVAL_CHOICES, default='pending')
    approved_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='approved_garages')
    approved_at      = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    is_active  = models.BooleanField(default=False)  # Only active after admin approval
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_fee    = models.DecimalField(max_digits=8, decimal_places=2, default=600,
                                         help_text='Booking confirmation advance fee charged to customer (₹)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['city', 'name']

    def __str__(self):
        return f'{self.name} — {self.city}'

    @property
    def is_approved(self):
        return self.approval_status == 'approved'


class GarageHours(models.Model):
    DAYS = [(0,'Monday'),(1,'Tuesday'),(2,'Wednesday'),(3,'Thursday'),
            (4,'Friday'),(5,'Saturday'),(6,'Sunday')]

    garage     = models.ForeignKey(Garage, on_delete=models.CASCADE, related_name='hours')
    day        = models.IntegerField(choices=DAYS)
    open_time  = models.TimeField()
    close_time = models.TimeField()
    is_closed  = models.BooleanField(default=False)

    class Meta:
        unique_together = ('garage', 'day')
        ordering = ['day']


# ═══════════════════════════════════════════════════════════════
#  MECHANIC PROFILE  (filled by manager)
# ═══════════════════════════════════════════════════════════════

class MechanicProfile(models.Model):
    """
    Extended profile for mechanics — filled by the Manager, not the mechanic.
    Mechanic can only VIEW this on their dashboard.
    """
    APPROVAL_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Active'),
        ('suspended','Suspended'),
    ]
    SKILL_CHOICES = [
        ('engine',    'Engine & Transmission'),
        ('electric',  'Electrical Systems'),
        ('ac',        'AC & HVAC'),
        ('body',      'Body & Paint'),
        ('tyres',     'Tyres & Wheels'),
        ('brakes',    'Brakes & Suspension'),
        ('diagnostic','Diagnostics & OBD'),
        ('detailing', 'Detailing & Cleaning'),
    ]

    mechanic       = models.OneToOneField(User, on_delete=models.CASCADE,
                                          related_name='mechanic_profile')
    garage         = models.ForeignKey(Garage, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='mechanics')
    added_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='added_mechanics')

    # Professional info (filled by manager)
    employee_id    = models.CharField(max_length=20, blank=True)
    designation    = models.CharField(max_length=80, blank=True, default='Mechanic')
    experience_years = models.PositiveIntegerField(default=0)
    skills         = models.JSONField(default=list, blank=True)  # list of SKILL_CHOICES keys
    certifications = models.TextField(blank=True)
    aadhaar_number = models.CharField(max_length=20, blank=True)
    pan_number     = models.CharField(max_length=20, blank=True)

    # Salary
    salary_type    = models.CharField(max_length=10,
                                      choices=[('monthly','Monthly'),('per_job','Per Job')],
                                      default='monthly')
    salary_amount  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                         help_text='% of job value as commission')

    # Status
    status         = models.CharField(max_length=10, choices=APPROVAL_CHOICES, default='pending')
    approved_at    = models.DateTimeField(null=True, blank=True)
    joining_date   = models.DateField(null=True, blank=True)
    notes          = models.TextField(blank=True, help_text='Manager notes')

    # Ratings (auto-calculated)
    total_jobs     = models.PositiveIntegerField(default=0)
    avg_rating     = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.mechanic.name} @ {self.garage}'


# ═══════════════════════════════════════════════════════════════
#  MECHANIC REQUEST  (mechanic requests to join garage)
# ═══════════════════════════════════════════════════════════════

class MechanicRequest(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    mechanic      = models.ForeignKey(User, on_delete=models.CASCADE,
                                      related_name='mechanic_requests')
    garage        = models.ForeignKey(Garage, on_delete=models.CASCADE,
                                      related_name='mechanic_requests')
    message       = models.TextField(blank=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at    = models.DateTimeField(auto_now_add=True)
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    reviewed_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='reviewed_mechanic_requests')
    reject_reason = models.TextField(blank=True)

    class Meta:
        unique_together = ('mechanic', 'garage')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.mechanic.name} → {self.garage.name} ({self.status})'


# ═══════════════════════════════════════════════════════════════
#  MECHANIC LEAVE REQUEST
# ═══════════════════════════════════════════════════════════════

class MechanicLeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('casual',    'Casual Leave'),
        ('sick',      'Sick Leave'),
        ('emergency', 'Emergency Leave'),
        ('festival',  'Festival Holiday'),
        ('personal',  'Personal Work'),
    ]
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    mechanic     = models.ForeignKey(User, on_delete=models.CASCADE,
                                     related_name='leave_requests')
    garage       = models.ForeignKey('Garage', on_delete=models.CASCADE,
                                     related_name='leave_requests')
    leave_type   = models.CharField(max_length=15, choices=LEAVE_TYPES, default='casual')
    from_date    = models.DateField()
    to_date      = models.DateField()
    reason       = models.TextField(blank=True)

    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reviewed_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='reviewed_leaves')
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.mechanic.name} | {self.from_date} – {self.to_date} ({self.status})'

    @property
    def days(self):
        return (self.to_date - self.from_date).days + 1


# ═══════════════════════════════════════════════════════════════
#  MECHANIC SHIFT  (per mechanic per weekday, set by manager)
# ═══════════════════════════════════════════════════════════════

class MechanicShift(models.Model):
    DAYS = [(0,'Monday'),(1,'Tuesday'),(2,'Wednesday'),(3,'Thursday'),
            (4,'Friday'),(5,'Saturday'),(6,'Sunday')]

    mechanic    = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='shifts')
    garage      = models.ForeignKey('Garage', on_delete=models.CASCADE,
                                    related_name='mechanic_shifts')
    day         = models.IntegerField(choices=DAYS)        # 0=Mon … 6=Sun
    start_time  = models.TimeField(default='09:00')
    end_time    = models.TimeField(default='18:00')
    is_off      = models.BooleanField(default=False)       # day off

    class Meta:
        unique_together = ('mechanic', 'day')
        ordering = ['day']

    def __str__(self):
        day_name = dict(self.DAYS).get(self.day, '?')
        if self.is_off:
            return f'{self.mechanic.name} — {day_name}: OFF'
        return f'{self.mechanic.name} — {day_name}: {self.start_time}–{self.end_time}'


# ═══════════════════════════════════════════════════════════════
#  INDIVIDUAL MECHANIC  (independent, approved by admin)
# ═══════════════════════════════════════════════════════════════

class IndividualMechanicProfile(models.Model):
    """
    Independent mechanic not tied to any garage.
    Approved by Admin. Works in their city. Can do home visits.
    """
    APPROVAL_CHOICES = [
        ('pending',  'Pending Admin Approval'),
        ('approved', 'Approved & Active'),
        ('rejected', 'Rejected'),
        ('suspended','Suspended'),
    ]

    mechanic          = models.OneToOneField(User, on_delete=models.CASCADE,
                                             related_name='individual_profile')
    # Service area
    service_cities    = models.CharField(max_length=300, blank=True,
                                         help_text='Comma-separated cities they serve')
    service_radius_km = models.PositiveIntegerField(default=20)
    home_visit        = models.BooleanField(default=True)
    home_visit_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Skills & credentials
    specializations   = models.JSONField(default=list)
    experience_years  = models.PositiveIntegerField(default=0)
    certifications    = models.TextField(blank=True)
    aadhaar_number    = models.CharField(max_length=20, blank=True)
    pan_number        = models.CharField(max_length=20, blank=True)
    gst_number        = models.CharField(max_length=20, blank=True)

    # Rates
    hourly_rate       = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Admin approval
    status            = models.CharField(max_length=10, choices=APPROVAL_CHOICES, default='pending')
    approved_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='approved_individuals')
    approved_at       = models.DateTimeField(null=True, blank=True)
    rejection_reason  = models.TextField(blank=True)
    apply_reason      = models.TextField(blank=True)

    # Stats
    total_jobs        = models.PositiveIntegerField(default=0)
    avg_rating        = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    created_at        = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Individual: {self.mechanic.name}'

    @property
    def service_cities_list(self):
        return [c.strip() for c in self.service_cities.split(',') if c.strip()]


# ═══════════════════════════════════════════════════════════════
#  SERVICE
# ═══════════════════════════════════════════════════════════════

class Service(models.Model):
    CATEGORY_CHOICES = [('car','Car'),('bike','Bike'),('both','Car & Bike')]

    name        = models.CharField(max_length=120)
    slug        = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon_emoji  = models.CharField(max_length=8, default='🔧')
    category    = models.CharField(max_length=5, choices=CATEGORY_CHOICES, default='both')

    price_basic    = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_standard = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_premium  = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, default=2)
    warranty_days  = models.PositiveIntegerField(default=0)
    is_active      = models.BooleanField(default=True)
    order          = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_price(self, package='standard'):
        return {'basic': self.price_basic, 'standard': self.price_standard,
                'premium': self.price_premium}.get(package, self.price_standard)


class GarageService(models.Model):
    """Per-garage pricing for each service — manager sets their own prices."""
    garage        = models.ForeignKey(Garage, on_delete=models.CASCADE, related_name='garage_services')
    service       = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='garage_offerings')
    is_offered    = models.BooleanField(default=True)

    # Custom prices set by manager (overrides global Service prices)
    price_basic    = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_standard = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_premium  = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    notes          = models.CharField(max_length=200, blank=True)  # e.g. "Includes free tyre rotation"
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('garage', 'service')
        ordering = ['service__order', 'service__name']

    def __str__(self):
        return f'{self.garage.name} — {self.service.name}'

    def get_price(self, package='standard'):
        """Return garage-specific price, falling back to global service price."""
        prices = {
            'basic':    self.price_basic    or self.service.price_basic,
            'standard': self.price_standard or self.service.price_standard,
            'premium':  self.price_premium  or self.service.price_premium,
        }
        return prices.get(package, prices['standard'])


# ═══════════════════════════════════════════════════════════════
#  VEHICLE
# ═══════════════════════════════════════════════════════════════
class Vehicle(models.Model):
    TYPE_CHOICES = [('car','Car'),('bike','Bike')]
    FUEL_CHOICES = [('petrol','Petrol'),('diesel','Diesel'),('cng','CNG'),
                    ('electric','Electric'),('hybrid','Hybrid')]

    owner               = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicles')
    type                = models.CharField(max_length=5, choices=TYPE_CHOICES, default='car')
    brand               = models.CharField(max_length=60)
    model_name          = models.CharField(max_length=60)
    variant             = models.CharField(max_length=60, blank=True)
    registration_number = models.CharField(max_length=20, blank=True)
    year                = models.PositiveIntegerField(null=True, blank=True)
    fuel_type           = models.CharField(max_length=10, choices=FUEL_CHOICES, default='petrol')
    colour              = models.CharField(max_length=40, blank=True)
    odometer            = models.PositiveIntegerField(default=0)
    insurance_expiry     = models.DateField(null=True, blank=True)
    damage_notes         = models.TextField(blank=True, help_text="Customer notes on existing damage")
    condition_submitted  = models.BooleanField(default=False)
    is_primary           = models.BooleanField(default=False)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return f'{self.brand} {self.model_name} — {self.owner.name}'

    def save(self, *args, **kwargs):
        if self.is_primary:
            Vehicle.objects.filter(owner=self.owner, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
#  COUPON
# ═══════════════════════════════════════════════════════════════

class Coupon(models.Model):
    TYPE_CHOICES = [('flat','Flat (₹)'),('percent','Percent (%)')]

    code          = models.CharField(max_length=20, unique=True)
    discount_type = models.CharField(max_length=8, choices=TYPE_CHOICES, default='flat')
    amount        = models.DecimalField(max_digits=8, decimal_places=2)
    min_order     = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_discount  = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    valid_from    = models.DateField(null=True, blank=True)
    valid_till    = models.DateField(null=True, blank=True)
    is_active     = models.BooleanField(default=True)
    usage_count   = models.PositiveIntegerField(default=0)
    max_usage     = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.code

    def calculate_discount(self, order_total):
        if order_total < float(self.min_order):
            return 0
        if self.discount_type == 'flat':
            return min(float(self.amount), float(order_total))
        else:
            disc = float(order_total) * float(self.amount) / 100
            if self.max_discount:
                disc = min(disc, float(self.max_discount))
            return disc


# ═══════════════════════════════════════════════════════════════
#  BOOKING
# ═══════════════════════════════════════════════════════════════

def generate_booking_ref():
    from django.utils.crypto import get_random_string
    return 'EG-' + get_random_string(5, '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending',       'Pending'),
        ('confirmed',     'Confirmed'),
        ('picked_up',     'Vehicle Picked Up'),
        ('at_garage',     'At Garage'),
        ('in_progress',   'In Progress'),
        ('quality_check', 'Quality Check'),
        ('delivered',     'Delivered'),
        ('cancelled',     'Cancelled'),
    ]
    PACKAGE_CHOICES   = [('basic','Basic'),('standard','Standard'),('premium','Premium')]
    PAYMENT_STATUS    = [('pending','Pending'),('paid','Paid'),('refunded','Refunded'),('failed','Failed')]
    SERVICE_TYPE      = [('garage','At Garage'),('home','Home Visit')]

    reference = models.CharField(max_length=12, unique=True, default=generate_booking_ref)

    # Relations
    customer  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bookings')
    garage    = models.ForeignKey(Garage, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    service   = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, related_name='bookings')
    vehicle   = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    mechanic  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='assigned_jobs', limit_choices_to={'role': 'mechanic'})
    coupon    = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    individual_mechanic = models.ForeignKey(IndividualMechanicProfile, on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name='bookings')

    # Package & pricing
    package         = models.CharField(max_length=10, choices=PACKAGE_CHOICES, default='standard')
    service_type    = models.CharField(max_length=7, choices=SERVICE_TYPE, default='garage')
    base_price      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pickup_charge   = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    final_price     = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Advance + Pay-Later billing
    ADVANCE_FEE     = 600  # flat ₹600 confirmation fee
    advance_amount  = models.DecimalField(max_digits=8, decimal_places=2, default=600)
    payment_type    = models.CharField(max_length=20, default='advance')  # advance/full/cash
    advance_paid    = models.BooleanField(default=False)
    advance_paid_at = models.DateTimeField(null=True, blank=True)
    advance_method  = models.CharField(max_length=20, default='online')

    # Final settlement (filled after job completion)
    parts_total     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    labour_charge   = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    final_bill      = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # parts + labour + base
    balance_due     = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # final_bill - advance
    final_paid      = models.BooleanField(default=False)
    final_paid_at   = models.DateTimeField(null=True, blank=True)
    final_method    = models.CharField(max_length=20, blank=True)

    # Schedule
    scheduled_date  = models.DateField()
    scheduled_slot  = models.TimeField()

    # Customer snapshot
    customer_name   = models.CharField(max_length=120)
    customer_phone  = models.CharField(max_length=15)
    customer_email  = models.EmailField(blank=True)
    pickup_address  = models.TextField(blank=True)
    pickup_lat      = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_lng      = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_required = models.BooleanField(default=False)
    notes           = models.TextField(blank=True)

    # Status & payment
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    payment_status  = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='pending')
    payment_method  = models.CharField(max_length=20, default='cash',
                                        choices=[('cash','Cash at Garage'),
                                                 ('online','Online Payment'),
                                                 ('upi','UPI')])

    # Razorpay
    razorpay_order_id   = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature  = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} — {self.customer_name}'

    def save(self, *args, **kwargs):
        self.final_price = float(self.base_price) - float(self.discount_amount) + float(self.pickup_charge)
        # Final bill = base service + parts + labour (calculated after job)
        self.final_bill  = float(self.base_price) - float(self.discount_amount) + float(self.pickup_charge) + float(self.parts_total) + float(self.labour_charge)
        # Balance customer owes at garage = final bill - advance already paid
        self.balance_due = max(0, self.final_bill - float(self.advance_amount if self.advance_paid else 0))
        super().save(*args, **kwargs)

    @property
    def status_step(self):
        steps = ['pending','confirmed','picked_up','at_garage','in_progress','quality_check','delivered']
        try:
            return steps.index(self.status)
        except ValueError:
            return 0

    @property
    def is_home_visit(self):
        return self.service_type == 'home' or self.pickup_required


# ═══════════════════════════════════════════════════════════════
#  LIVE LOCATION  (mechanic GPS tracking)
# ═══════════════════════════════════════════════════════════════

class LiveLocation(models.Model):
    """Real-time mechanic location for tracking."""
    booking   = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='live_location')
    mechanic  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='live_locations')
    lat       = models.DecimalField(max_digits=9, decimal_places=6)
    lng       = models.DecimalField(max_digits=9, decimal_places=6)
    speed_kmh = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    heading   = models.IntegerField(default=0)  # degrees 0-360
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Live: {self.mechanic.name} for {self.booking.reference}'


# ═══════════════════════════════════════════════════════════════
#  EMERGENCY REQUEST
# ═══════════════════════════════════════════════════════════════

class EmergencyRequest(models.Model):
    STATUS_CHOICES = [
        ('open',       'Open — Finding Mechanic'),
        ('assigned',   'Mechanic Assigned'),
        ('on_way',     'Mechanic On The Way'),
        ('arrived',    'Mechanic Arrived'),
        ('in_progress','In Progress'),
        ('resolved',   'Resolved'),
        ('cancelled',  'Cancelled'),
    ]
    ISSUE_CHOICES = [
        ('breakdown',  'Vehicle Breakdown'),
        ('flat_tyre',  'Flat Tyre'),
        ('battery',    'Dead Battery'),
        ('accident',   'Minor Accident'),
        ('fuel',       'Out of Fuel'),
        ('overheating','Engine Overheating'),
        ('other',      'Other'),
    ]

    customer      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_requests')
    vehicle       = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True)
    issue_type    = models.CharField(max_length=15, choices=ISSUE_CHOICES)
    description   = models.TextField(blank=True)
    location_address = models.TextField()
    lat           = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng           = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    city          = models.CharField(max_length=80, blank=True)

    assigned_mechanic = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='emergency_assignments')
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    estimated_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    final_cost    = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    resolved_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Emergency: {self.customer.name} — {self.get_issue_type_display()}'


# ═══════════════════════════════════════════════════════════════
#  JOB  (mechanic work order)
# ═══════════════════════════════════════════════════════════════

class Job(models.Model):
    STATUS_CHOICES = [
        ('assigned',       'Assigned'),
        ('accepted',       'Accepted by Mechanic'),
        ('on_way',         'On the Way'),
        ('arrived',        'Arrived'),
        ('in_progress',    'In Progress'),
        ('on_hold',        'On Hold'),
        ('quality_check',  'Quality Check'),
        ('completed',      'Completed'),
        ('verified',       'Manager Verified'),
        ('issue_reported', 'Issue Reported'),
    ]

    booking     = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='job')
    mechanic    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='jobs', limit_choices_to={'role': 'mechanic'})
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    notes       = models.TextField(blank=True)
    started_at  = models.DateTimeField(null=True, blank=True)
    arrived_at  = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken_minutes = models.PositiveIntegerField(null=True, blank=True)
    self_rating = models.PositiveIntegerField(null=True, blank=True)

    # Escrow / payment release
    manager_verified   = models.BooleanField(default=False)
    manager_verified_at = models.DateTimeField(null=True, blank=True)
    verified_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='verified_jobs')
    wallet_released    = models.BooleanField(default=False)
    wallet_released_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Job #{self.pk} for {self.booking.reference}'

    @property
    def checklist_progress(self):
        total = self.checklist_items.count()
        done  = self.checklist_items.filter(is_done=True).count()
        return (done, total)


class JobTask(models.Model):
    """Individual tasks within a job — supports multiple mechanics."""
    job         = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='tasks')
    mechanic    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='job_tasks')
    task_name   = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_done     = models.BooleanField(default=False)
    done_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.task_name} — {self.mechanic.name if self.mechanic else "Unassigned"}'


class JobChecklistItem(models.Model):
    job          = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='checklist_items')
    label        = models.CharField(max_length=200)
    is_done      = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    order        = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


class JobPhoto(models.Model):
    CATEGORY_CHOICES = [
        ('before', 'Before Service'),
        ('during', 'During Service'),
        ('after',  'After Service'),
        ('parts',  'Parts Used'),
    ]
    job         = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='photos')
    photo       = models.ImageField(upload_to='job_photos/%Y/%m/')
    category    = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='before')
    caption     = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class JobPart(models.Model):
    job       = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='parts')
    name      = models.CharField(max_length=120)
    detail    = models.CharField(max_length=200, blank=True)
    quantity  = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cost      = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # quantity × unit_cost
    added_by  = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='added_parts')
    is_approved = models.BooleanField(default=True)  # manager can dispute
    created_at  = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
#  REVIEW
# ═══════════════════════════════════════════════════════════════

class Review(models.Model):
    booking      = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    rating       = models.PositiveIntegerField()  # 1–5
    text         = models.TextField(blank=True)
    mechanic_rating = models.PositiveIntegerField(null=True, blank=True)
    service_rating  = models.PositiveIntegerField(null=True, blank=True)
    punctuality     = models.PositiveIntegerField(null=True, blank=True)
    cleanliness     = models.PositiveIntegerField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.booking.reference} — {self.rating}★'


# ═══════════════════════════════════════════════════════════════
#  NOTIFICATION
# ═══════════════════════════════════════════════════════════════

class Notification(models.Model):
    TYPE_CHOICES = [
        ('booking',   'Booking'),
        ('service',   'Service'),
        ('offer',     'Offer'),
        ('reminder',  'Reminder'),
        ('mechanic',  'Mechanic'),
        ('payment',   'Payment'),
        ('account',   'Account'),
        ('system',    'System'),
        ('emergency', 'Emergency'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title       = models.CharField(max_length=200)
    message     = models.TextField()
    type        = models.CharField(max_length=10, choices=TYPE_CHOICES, default='booking')
    is_read     = models.BooleanField(default=False)
    ref_booking = models.ForeignKey(Booking, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='notifications')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.name} — {self.title}'


# ═══════════════════════════════════════════════════════════════
# GARAGE WALLET / EARNINGS
# ═══════════════════════════════════════════════════════════════

class GarageTransaction(models.Model):
    TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit',  'Debit'),
        ('refund', 'Refund'),
    ]
    garage      = models.ForeignKey(Garage, on_delete=models.CASCADE, related_name='transactions')
    booking     = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    type        = models.CharField(max_length=10, choices=TYPE_CHOICES, default='credit')
    amount      = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.garage.name} — {self.type} ₹{self.amount}'


# ═══════════════════════════════════════════════════════════════
# BOOKING MESSAGES (Customer ↔ Mechanic chat)
# ═══════════════════════════════════════════════════════════════

class BookingMessage(models.Model):
    booking     = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='messages')
    sender      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message     = models.TextField()
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.name} → {self.booking.reference}: {self.message[:40]}'


# ═══════════════════════════════════════════════════════════════
# JOB DECLINE LOG
# ═══════════════════════════════════════════════════════════════

class JobDecline(models.Model):
    job       = models.ForeignKey('Job', on_delete=models.CASCADE, related_name='declines')
    mechanic  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='declined_jobs')
    reason    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.mechanic.name} declined Job #{self.job.pk}'


# ═══════════════════════════════════════════════════════════════
# MECHANIC EARNINGS (per-job credit)
# ═══════════════════════════════════════════════════════════════

class MechanicEarning(models.Model):
    mechanic    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='earnings')
    job         = models.OneToOneField('Job', on_delete=models.CASCADE, related_name='earning')
    garage      = models.ForeignKey(Garage, on_delete=models.SET_NULL, null=True, blank=True)
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)  # booking final_bill
    commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    earning_amount = models.DecimalField(max_digits=10, decimal_places=2)  # mechanic's cut
    credited_at  = models.DateTimeField(auto_now_add=True)
    is_paid      = models.BooleanField(default=False)  # paid out to mechanic

    class Meta:
        ordering = ['-credited_at']

    def __str__(self):
        return f'{self.mechanic.name} — ₹{self.earning_amount} for Job #{self.job.pk}'


# ═══════════════════════════════════════════════════════════════
# GARAGE CUSTOM SERVICES (manager-created, not in global list)
# ═══════════════════════════════════════════════════════════════

class GarageCustomService(models.Model):
    """A service that a specific garage offers — not in the global list."""
    garage         = models.ForeignKey(Garage, on_delete=models.CASCADE, related_name='custom_services')
    name           = models.CharField(max_length=120)
    description    = models.TextField(blank=True)
    icon_emoji     = models.CharField(max_length=8, default='🔧')
    category       = models.CharField(max_length=5,
                                       choices=[('car','Car'),('bike','Bike'),('both','Car & Bike')],
                                       default='both')
    price_basic    = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_standard = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_premium  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, default=2)
    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.garage.name} — {self.name} (custom)'

    def get_price(self, package='standard'):
        return {'basic': self.price_basic,
                'standard': self.price_standard,
                'premium': self.price_premium}.get(package, self.price_standard)