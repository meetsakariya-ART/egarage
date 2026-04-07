"""
core/admin.py  —  eGarage Complete Admin
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    User, AdminRequest, Garage, GarageHours, Service, Vehicle,
    Booking, Job, JobChecklistItem, JobPhoto, JobPart,
    Coupon, Notification, Review, LiveLocation, EmergencyRequest,
    MechanicProfile, MechanicRequest, IndividualMechanicProfile,
    MechanicLeaveRequest, MechanicShift,
)


# ── USER ─────────────────────────────────────────────────────
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display    = ('email', 'name', 'role', 'city',
                       'approval_status_display',
                       'manager_approved', 'manager_created',
                       'is_available', 'is_active', 'date_joined')
    list_filter     = ('role', 'is_active', 'is_super_admin',
                       'admin_approved', 'manager_approved',
                       'manager_created', 'is_individual')
    search_fields   = ('email', 'name', 'phone', 'city')
    ordering        = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login')

    fieldsets = (
        ('Login',          {'fields': ('email', 'password')}),
        ('Personal Info',  {'fields': ('name', 'phone', 'city', 'state', 'pincode',
                                       'address', 'date_of_birth', 'gender', 'blood_group',
                                       'profile_photo', 'whatsapp', 'emergency_contact')}),
        ('Role & Status',  {'fields': ('role', 'is_active', 'is_staff', 'is_admin',
                                       'is_super_admin', 'admin_approved',
                                       'manager_approved', 'manager_created',
                                       'is_available', 'is_individual')}),
        ('Location',       {'fields': ('current_lat', 'current_lng', 'last_seen')}),
        ('Permissions',    {'fields': ('is_superuser', 'groups', 'user_permissions')}),
        ('Dates',          {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': (
            'email', 'name', 'phone', 'role', 'city', 'password1', 'password2',
            'is_super_admin', 'admin_approved', 'manager_approved',
        )}),
    )

    actions = ['approve_managers', 'reject_managers',
               'make_super_admin', 'approve_as_admin', 'deactivate_users']

    @admin.display(description='Approval')
    def approval_status_display(self, obj):
        if obj.role == 'manager':
            if obj.manager_approved:
                return format_html('<span style="color:green;font-weight:bold;">✓ Manager OK</span>')
            else:
                return format_html('<span style="color:orange;font-weight:bold;">⏳ Manager Pending</span>')
        if obj.role == 'admin':
            if obj.admin_approved:
                return format_html('<span style="color:green;font-weight:bold;">✓ Admin OK</span>')
            else:
                return format_html('<span style="color:red;font-weight:bold;">✕ Admin Pending</span>')
        return '—'

    def approve_managers(self, request, queryset):
        managers = queryset.filter(role='manager')
        managers.update(manager_approved=True)
        self.message_user(request, f'✅ {managers.count()} manager(s) approved.')
    approve_managers.short_description = '✅ Approve selected Managers'

    def reject_managers(self, request, queryset):
        managers = queryset.filter(role='manager')
        managers.update(is_active=False)
        self.message_user(request, f'🚫 {managers.count()} manager(s) rejected/deactivated.')
    reject_managers.short_description = '🚫 Reject selected Managers'

    def make_super_admin(self, request, queryset):
        queryset.update(is_super_admin=True, admin_approved=True, is_staff=True,
                        is_superuser=True, role='admin')
        self.message_user(request, f'{queryset.count()} user(s) made Super Admin.')
    make_super_admin.short_description = '⭐ Make Super Admin'

    def approve_as_admin(self, request, queryset):
        queryset.update(admin_approved=True, is_staff=True, role='admin')
        self.message_user(request, f'{queryset.count()} user(s) approved as Admin.')
    approve_as_admin.short_description = '✅ Approve as Admin'

    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} user(s) deactivated.')
    deactivate_users.short_description = '🚫 Deactivate selected'


# ── MANAGER REQUESTS — dedicated view showing only pending managers ──
class PendingManagerProxy(User):
    """Proxy model so Django admin shows a separate 'Manager Requests' section."""
    class Meta:
        proxy        = True
        verbose_name = 'Manager Request'
        verbose_name_plural = '🟠 Manager Requests (Pending Approval)'

@admin.register(PendingManagerProxy)
class PendingManagerAdmin(admin.ModelAdmin):
    list_display  = ('email', 'name', 'phone', 'city', 'date_joined', 'manager_approved', 'approval_action')
    list_filter   = ('manager_approved', 'is_active')
    search_fields = ('email', 'name', 'phone', 'city')
    ordering      = ('-date_joined',)
    actions       = ['approve_managers', 'reject_managers']
    readonly_fields = ('email', 'name', 'phone', 'city', 'date_joined', 'last_login')

    def get_queryset(self, request):
        # Only show managers (pending AND approved) — admin can see all managers here
        return super().get_queryset(request).filter(role='manager')

    @admin.display(description='Status')
    def approval_action(self, obj):
        if obj.manager_approved:
            return format_html('<span style="color:green;font-weight:bold;">✓ Approved</span>')
        return format_html(
            '<a href="/admin/core/pendingmanagerproxy/{}/change/" '
            'style="background:#f97316;color:#fff;padding:3px 10px;border-radius:5px;'
            'text-decoration:none;font-weight:bold;font-size:12px;">Review →</a>',
            obj.pk
        )

    def approve_managers(self, request, queryset):
        count = queryset.filter(manager_approved=False).count()
        queryset.update(manager_approved=True)
        self.message_user(request, f'✅ {count} manager(s) approved. They can now login.')
    approve_managers.short_description = '✅ Approve selected managers'

    def reject_managers(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'🚫 Selected managers rejected and deactivated.')
    reject_managers.short_description = '🚫 Reject & deactivate selected'

    fieldsets = (
        ('Manager Details', {'fields': ('email', 'name', 'phone', 'city', 'date_joined')}),
        ('Approval',        {'fields': ('manager_approved', 'is_active')}),
    )


# ── ADMIN REQUEST ─────────────────────────────────────────────
@admin.register(AdminRequest)
class AdminRequestAdmin(admin.ModelAdmin):
    list_display  = ('user', 'status', 'created_at', 'reviewed_by', 'reviewed_at')
    list_filter   = ('status',)
    search_fields = ('user__name', 'user__email')
    readonly_fields = ('created_at',)
    actions = ['approve_requests', 'reject_requests']

    def approve_requests(self, request, queryset):
        for req in queryset.filter(status='pending'):
            req.status = 'approved'
            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user
            req.save()
            req.user.role = 'admin'
            req.user.admin_approved = True
            req.user.is_staff = True
            req.user.save()
        self.message_user(request, 'Selected requests approved.')
    approve_requests.short_description = '✅ Approve selected'

    def reject_requests(self, request, queryset):
        queryset.filter(status='pending').update(status='rejected', reviewed_at=timezone.now())
        self.message_user(request, 'Selected requests rejected.')
    reject_requests.short_description = '❌ Reject selected'


# ── GARAGE ────────────────────────────────────────────────────
class GarageHoursInline(admin.TabularInline):
    model  = GarageHours
    extra  = 0


@admin.register(Garage)
class GarageAdmin(admin.ModelAdmin):
    list_display  = ('name', 'city', 'manager', 'approval_status', 'is_active', 'created_at')
    list_filter   = ('approval_status', 'is_active', 'city', 'state')
    search_fields = ('name', 'city', 'manager__name', 'manager__email')
    inlines       = [GarageHoursInline]
    readonly_fields = ('created_at',)
    actions = ['approve_garages', 'reject_garages']

    def approve_garages(self, request, queryset):
        queryset.update(approval_status='approved', is_active=True,
                        approved_by=request.user, approved_at=timezone.now())
        self.message_user(request, f'{queryset.count()} garage(s) approved.')
    approve_garages.short_description = '✅ Approve garages'

    def reject_garages(self, request, queryset):
        queryset.update(approval_status='rejected', is_active=False)
        self.message_user(request, f'{queryset.count()} garage(s) rejected.')
    reject_garages.short_description = '❌ Reject garages'


# ── MECHANIC PROFILE ──────────────────────────────────────────
@admin.register(MechanicProfile)
class MechanicProfileAdmin(admin.ModelAdmin):
    list_display  = ('mechanic', 'garage', 'designation', 'status', 'salary_type', 'salary_amount')
    list_filter   = ('status', 'salary_type', 'garage__city')
    search_fields = ('mechanic__name', 'mechanic__email', 'garage__name')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_mechanics']

    def approve_mechanics(self, request, queryset):
        queryset.update(status='approved', approved_at=timezone.now())
        self.message_user(request, f'{queryset.count()} mechanic(s) approved.')
    approve_mechanics.short_description = '✅ Approve mechanics'


@admin.register(MechanicRequest)
class MechanicRequestAdmin(admin.ModelAdmin):
    list_display = ('mechanic', 'garage', 'status', 'created_at')
    list_filter  = ('status',)


# ── INDIVIDUAL MECHANIC ───────────────────────────────────────
@admin.register(IndividualMechanicProfile)
class IndividualMechanicAdmin(admin.ModelAdmin):
    list_display  = ('mechanic', 'service_cities', 'status', 'home_visit', 'hourly_rate', 'created_at')
    list_filter   = ('status', 'home_visit')
    search_fields = ('mechanic__name', 'mechanic__email', 'service_cities')
    readonly_fields = ('created_at',)
    actions = ['approve_individual']

    def approve_individual(self, request, queryset):
        queryset.update(status='approved', approved_by=request.user, approved_at=timezone.now())
        for p in queryset:
            p.mechanic.is_individual = True
            p.mechanic.save(update_fields=['is_individual'])
        self.message_user(request, f'{queryset.count()} individual mechanic(s) approved.')
    approve_individual.short_description = '✅ Approve individual mechanics'


# ── SERVICE ───────────────────────────────────────────────────
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display  = ('name', 'icon_emoji', 'category', 'price_basic', 'price_standard', 'price_premium', 'is_active', 'order')
    list_filter   = ('category', 'is_active')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')


# ── VEHICLE ───────────────────────────────────────────────────
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display  = ('brand', 'model_name', 'owner', 'registration_number', 'fuel_type', 'is_primary')
    list_filter   = ('type', 'fuel_type')
    search_fields = ('brand', 'model_name', 'registration_number', 'owner__name')


# ── COUPON ────────────────────────────────────────────────────
@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'amount', 'min_order', 'usage_count', 'is_active', 'valid_till')
    list_filter  = ('discount_type', 'is_active')
    search_fields = ('code',)


# ── BOOKING ───────────────────────────────────────────────────
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display   = ('reference', 'customer_name', 'service', 'garage', 'status', 'payment_status', 'final_price', 'scheduled_date')
    list_filter    = ('status', 'payment_status', 'service_type', 'scheduled_date')
    search_fields  = ('reference', 'customer_name', 'customer_email', 'customer_phone')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    date_hierarchy = 'scheduled_date'
    ordering       = ('-created_at',)


# ── JOB ───────────────────────────────────────────────────────
class JobChecklistInline(admin.TabularInline):
    model = JobChecklistItem
    extra = 0

class JobPhotoInline(admin.TabularInline):
    model = JobPhoto
    extra = 0

class JobPartInline(admin.TabularInline):
    model = JobPart
    extra = 0


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display  = ('pk', 'booking', 'mechanic', 'status', 'started_at', 'completed_at')
    list_filter   = ('status',)
    search_fields = ('booking__reference', 'mechanic__name')
    inlines       = [JobChecklistInline, JobPhotoInline, JobPartInline]
    readonly_fields = ('created_at', 'updated_at')


# ── REVIEW ────────────────────────────────────────────────────
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ('booking', 'rating', 'mechanic_rating', 'service_rating', 'created_at')
    list_filter   = ('rating',)
    search_fields = ('booking__reference', 'text')


# ── NOTIFICATION ──────────────────────────────────────────────
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'type', 'is_read', 'created_at')
    list_filter  = ('type', 'is_read')
    search_fields = ('user__name', 'title', 'message')


# ── EMERGENCY ─────────────────────────────────────────────────
@admin.register(EmergencyRequest)
class EmergencyRequestAdmin(admin.ModelAdmin):
    list_display  = ('customer', 'issue_type', 'city', 'status', 'assigned_mechanic', 'created_at')
    list_filter   = ('status', 'issue_type', 'city')
    search_fields = ('customer__name', 'location_address', 'city')
    readonly_fields = ('created_at',)


# ── LIVE LOCATION ─────────────────────────────────────────────
@admin.register(LiveLocation)
class LiveLocationAdmin(admin.ModelAdmin):
    list_display = ('mechanic', 'booking', 'lat', 'lng', 'speed_kmh', 'updated_at')
    search_fields = ('mechanic__name', 'booking__reference')


# ── MECHANIC LEAVE REQUESTS ────────────────────────────────────
@admin.register(MechanicLeaveRequest)
class MechanicLeaveRequestAdmin(admin.ModelAdmin):
    list_display  = ('mechanic', 'garage', 'leave_type', 'from_date', 'to_date', 'status', 'reviewed_by')
    list_filter   = ('status', 'leave_type', 'garage__city')
    search_fields = ('mechanic__name', 'mechanic__email', 'garage__name')
    readonly_fields = ('created_at',)
    actions = ['approve_leaves', 'reject_leaves']

    def approve_leaves(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='approved', reviewed_by=request.user, reviewed_at=timezone.now()
        )
        self.message_user(request, f'✅ {queryset.count()} leave(s) approved.')
    approve_leaves.short_description = '✅ Approve selected leave requests'

    def reject_leaves(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='rejected', reviewed_by=request.user, reviewed_at=timezone.now()
        )
        self.message_user(request, f'Rejected {queryset.count()} leave(s).')
    reject_leaves.short_description = '✕ Reject selected leave requests'


# ── MECHANIC SHIFTS ────────────────────────────────────────────
@admin.register(MechanicShift)
class MechanicShiftAdmin(admin.ModelAdmin):
    list_display  = ('mechanic', 'garage', 'get_day', 'start_time', 'end_time', 'is_off')
    list_filter   = ('is_off', 'day', 'garage__city')
    search_fields = ('mechanic__name', 'garage__name')

    @admin.display(description='Day')
    def get_day(self, obj):
        return dict(obj.DAYS).get(obj.day, '?')