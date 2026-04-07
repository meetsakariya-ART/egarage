"""core/urls.py — FINAL COMPLETE"""
from django.urls import path
from . import views, auth_views

urlpatterns = [

    # ── PUBLIC ──────────────────────────────────────────────
    path('',                               views.homeView,                name='home'),
    path('find/',                          views.garageFinderView,        name='garage_finder'),
    path('services/<slug:slug>/',          views.serviceDetailView,       name='service_detail'),

    # ── AUTH ─────────────────────────────────────────────────
    path('signup/',                        auth_views.signupView,         name='signup'),
    path('signup/verify/',                 auth_views.signupVerifyView,   name='signup_verify'),
    path('login/',                         auth_views.loginView,          name='login'),
    path('login/verify/',                  auth_views.loginVerifyView,    name='login_verify'),
    path('logout/',                        auth_views.logoutView,         name='logout'),
    path('otp/resend/',                    auth_views.resendOtpView,      name='resend_otp'),
    path('forgot-password/',               auth_views.forgotPasswordView, name='forgot_password'),
    path('reset-password/',                auth_views.resetPasswordView,  name='reset_password'),

    # ── DASHBOARD ────────────────────────────────────────────
    path('dashboard/',                     views.dashboardView,           name='dashboard'),

    # ── BOOKING ──────────────────────────────────────────────
    path('booking/',                       views.bookingView,             name='booking'),
    path('booking/confirm/',               views.bookingConfirmView,      name='booking_confirm'),
    path('booking/confirmed/',             views.bookingConfirmedView,    name='booking_confirmed'),
    path('booking/payment/',               views.paymentView,             name='payment'),
    path('booking/payment-done/',           views.dummyPaymentSuccessView, name='dummy_payment_success'),
    path('booking/payment-success/',        views.paymentSuccessView,      name='payment_success'),
    path('test-email/',                    views.testEmailView,           name='test_email'),
    path('booking/payment-failed/',        views.paymentFailedView,       name='payment_failed'),
    path('booking/<str:ref>/pay-balance/', views.balancePaymentView,      name='pay_balance'),
    path('booking/<str:ref>/balance-done/',views.balancePaymentDoneView,  name='balance_payment_done'),

    # ── CUSTOMER ─────────────────────────────────────────────
    path('bookings/',                      views.bookingsView,            name='bookings'),
    path('bookings/<str:ref>/',            views.bookingDetailView,       name='booking_detail'),
    path('bookings/<str:ref>/invoice/',    views.downloadInvoiceView,     name='download_invoice'),
    path('booking/<str:ref>/rate/',        views.rateServiceView,         name='rate_service'),
    path('track/',                         views.trackView,               name='track'),
    path('emergency/',                     views.emergencyView,           name='emergency'),
    path('vehicles/',                      views.vehiclesView,            name='vehicles'),
    path('vehicle/<int:pk>/condition/',    views.vehicleConditionView,    name='vehicle_condition'),
    path('profile/',                       views.profileView,             name='profile'),
    path('profile/change-password/',       views.changePasswordView,      name='change_password'),
    path('notifications/',                 views.notificationsView,       name='notifications'),

    # ── MECHANIC ─────────────────────────────────────────────
    path('jobs/',                          views.mechanicJobsView,        name='mechanic_jobs'),
    path('jobs/<str:job_id>/',             views.jobDetailView,           name='job_detail'),
    path('earnings/',                      views.earningsView,            name='earnings'),
    path('schedule/',                      views.scheduleView,            name='schedule'),
    path('apply-individual/',              views.applyIndividualMechanicView, name='apply_individual'),
    path('garage/<int:pk>/join/',          views.requestJoinGarageView,   name='request_join_garage'),

    # ── MANAGER ──────────────────────────────────────────────
    path('reports/',                       views.reportsView,             name='reports'),
    path('team/',                          views.teamView,                name='team'),
    path('garage-settings/',               views.garageSettingsView,      name='garage_settings'),
    path('garage-services/',               views.garageServicesView,       name='garage_services'),

    # ── ADMIN ────────────────────────────────────────────────
    path('admin-panel/',                   views.adminDashboardView,      name='admin_panel'),
    path('admin-panel/add-admin/',         views.addSubAdminView,         name='add_sub_admin'),
    path('request-admin/',                 views.requestAdminView,        name='request_admin'),
    path('api/leave/<int:pk>/approve/',    views.approveLeaveView,        name='approve_leave'),
    path('api/leave/<int:pk>/reject/',     views.rejectLeaveView,         name='reject_leave'),
    path('api/mechanic/<int:mechanic_id>/shifts/', views.saveShiftView,   name='save_shifts'),

    # ── AJAX ─────────────────────────────────────────────────
    path('api/check-email/',               views.checkEmailView,          name='check_email'),
    path('api/validate-coupon/',           views.validateCouponView,      name='validate_coupon'),
    path('api/booking/<str:ref>/status/',  views.bookingStatusView,       name='booking_status'),
    path('api/mark-notification-read/',    views.markNotificationRead,    name='mark_notif_read'),
    path('api/toggle-availability/',       views.toggleAvailabilityView,  name='toggle_availability'),
    path('api/location/update/',           views.updateLiveLocation,      name='update_location'),

    # ── VEHICLE CRUD ─────────────────────────────────────────
    path('api/vehicle/add/',               views.addVehicleView,          name='add_vehicle'),
    path('api/vehicle/<int:pk>/delete/',   views.deleteVehicleView,       name='delete_vehicle'),
    path('api/vehicle/<int:pk>/primary/',  views.setPrimaryVehicle,       name='set_primary_vehicle'),

    # ── JOB ACTIONS ──────────────────────────────────────────
    path('api/job/<int:pk>/status/',       views.updateJobStatus,         name='update_job_status'),
    path('api/job/<int:pk>/verify/',       views.managerVerifyJobView,    name='verify_job'),
    path('api/job/<int:pk>/decline/',      views.declineJobView,          name='decline_job'),
    path('api/job/<int:pk>/reassign/',     views.reassignJobView,         name='reassign_job'),
    path('api/job/<int:pk>/task/add/',     views.addJobTaskView,          name='add_job_task'),
    path('api/task/<int:task_pk>/done/',   views.completeJobTaskView,     name='complete_task'),
    path('api/job/<int:pk>/parts/add/',    views.addJobPartView,          name='add_job_part'),
    path('api/part/<int:part_pk>/remove/', views.removeJobPartView,       name='remove_job_part'),
    path('api/booking/<str:ref>/invoice/', views.liveInvoiceView,         name='live_invoice'),
    path('api/booking/<str:ref>/settle/',  views.finalSettlementView,     name='final_settlement'),
    path('api/booking/<str:ref>/messages/', views.bookingMessagesView,    name='booking_messages'),
    path('api/booking/<str:ref>/cancel/',   views.cancelBookingView,       name='cancel_booking'),
    path('api/booking/<str:ref>/assign/',   views.assignBookingView,       name='assign_booking'),
    path('manager/master/',                views.managerMasterView,       name='manager_master'),
    path('manager/finance/',               views.managerFinanceView,       name='manager_finance'),
    path('manager/pricing/',               views.garagePricingView,        name='garage_pricing'),
    path('admin/finance/',                 views.adminNetworkFinanceView,  name='admin_finance'),
    path('api/garage/<int:garage_id>/services/', views.garageServicesApiView, name='garage_services_api'),
    path('api/job/<int:pk>/checklist/',        views.updateChecklist,      name='update_checklist'),
    path('api/job/<int:pk>/checklist/add/',    views.addChecklistItem,     name='checklist_add'),
    path('api/job/<int:pk>/photo/',        views.uploadJobPhoto,          name='upload_job_photo'),

    # ── EMERGENCY ────────────────────────────────────────────
    path('api/emergency/<int:pk>/accept/', views.acceptEmergencyView,     name='accept_emergency'),

    # ── ADMIN APIS ───────────────────────────────────────────
    path('api/admin/approve-admin/<int:pk>/',   views.approveAdminRequest,       name='approve_admin'),
    path('api/admin/approve-manager/<int:pk>/', views.approveManagerView,         name='approve_manager'),
    path('api/admin/reject-manager/<int:pk>/',  views.rejectManagerView,          name='reject_manager'),
    path('api/admin/reject-admin/<int:pk>/',    views.rejectAdminRequest,        name='reject_admin'),
    path('api/admin/approve-garage/<int:pk>/',  views.approveGarageView,         name='approve_garage'),
    path('api/admin/reject-garage/<int:pk>/',   views.rejectGarageView,          name='reject_garage'),
    path('api/admin/approve-mechanic/<int:pk>/',views.approveIndividualMechView, name='approve_ind_mech'),
    path('api/admin/reject-mechanic/<int:pk>/', views.rejectIndividualMechView,  name='reject_ind_mech'),
    path('api/admin/toggle-user/<int:pk>/',     views.toggleUserActive,          name='toggle_user'),
    path('api/admin/make-super/<int:pk>/',      views.makeSuperAdmin,            name='make_super_admin'),
]