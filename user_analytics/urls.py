"""
URL routing for user_analytics app.

Where /user-analytics/business/visitors/ (visitors_detail) is linked:
- Business Dashboard: Conversion Funnel card "Total Visitors" count links to visitors with period.
- Web Owner Dashboard: "Visitors" metric card; source/device/country/entry/exit table cells link with filters.
- Admin Dashboard: "Visitors" metric card with period.
- Visitors detail page itself: "Clear Filters" / "Clear source" buttons (same page, params cleared).
"""
from django.urls import path
from . import views

app_name = 'user_analytics'

urlpatterns = [
    # Main admin dashboard (superuser only)
    path('', views.admin_dashboard, name='admin_dashboard'),
    
    # Main dashboard (redirects to business) - for staff
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Business Owner Dashboard
    path('business/', views.business_dashboard, name='business_dashboard'),
    
    # Accounts Dashboard
    path('accounts/', views.accounts_dashboard, name='accounts_dashboard'),
    
    # Web Owner Dashboard
    path('web-owner/', views.web_owner_dashboard, name='web_owner_dashboard'),
    path('web-owner/services/', views.web_owner_services_monitor, name='web_owner_services_monitor'),
    path('web-owner/services/test-email/', views.web_owner_service_test_email, name='web_owner_service_test_email'),
    path(
        'web-owner/services/send-daily-new-user-report/',
        views.web_owner_send_daily_new_user_report,
        name='web_owner_send_daily_new_user_report',
    ),
    path(
        'web-owner/services/daily-report-schedule/',
        views.web_owner_daily_report_schedule,
        name='web_owner_daily_report_schedule',
    ),
    path(
        'web-owner/services/clear-logs/',
        views.web_owner_clear_service_logs,
        name='web_owner_clear_service_logs',
    ),
    path(
        'web-owner/services/celery/revoke/',
        views.web_owner_revoke_celery_task,
        name='web_owner_revoke_celery_task',
    ),
    path(
        'web-owner/services/celery/revoke-all/',
        views.web_owner_revoke_all_celery_tasks,
        name='web_owner_revoke_all_celery_tasks',
    ),
    path('web-owner/email-logs/', views.web_owner_email_logs, name='web_owner_email_logs'),
    
    # User Journey
    path('user-journey/', views.user_journey_view, name='user_journey'),
    path('user-journey/<int:user_id>/', views.user_journey_view, name='user_journey_detail'),
    path('user-journey/detail/<str:session_id>/', views.user_journey_detail_view, name='user_journey_session_detail'),
    
    # Admin User Analytics (in-dashboard, with filters)
    path('admin-analytics/', views.admin_user_analytics_view, name='admin_user_analytics'),
    path('admin-analytics/cleanup/', views.cleanup_analytics_data_view, name='cleanup_analytics_data'),
    # Enquiry Sources (non-readable links: ?ref=TOKEN)
    path('admin-analytics/enquiry-sources/', views.enquiry_sources_list_view, name='enquiry_sources_list'),
    path('admin-analytics/enquiry-sources/add/', views.enquiry_source_create_view, name='enquiry_source_create'),
    path('admin-analytics/enquiry-sources/<int:pk>/edit/', views.enquiry_source_edit_view, name='enquiry_source_edit'),
    path('admin-analytics/enquiry-sources/<int:pk>/delete/', views.enquiry_source_delete_view, name='enquiry_source_delete'),
    path('admin-analytics/enquiry-sources/<int:pk>/qr.png', views.enquiry_source_qr_view, name='enquiry_source_qr'),
    path('admin-analytics/enquiry-sources/test-ref/', views.enquiry_source_test_ref_view, name='enquiry_source_test_ref'),
    path('admin-analytics/chatbot-rules/', views.chatbot_rules_view, name='chatbot_rules'),
    path('admin-analytics/chatbot-rules/search/', views.chatbot_rules_search_api, name='chatbot_rules_search'),
    
    # API Endpoints
    path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard_data'),
    
    # Detail Pages with Filters
    path('business/payments/successful/', views.successful_payments_detail, name='successful_payments_detail'),
    path('business/payments/successful/export-excel/', views.successful_payments_export_excel, name='successful_payments_export_excel'),
    path('business/payments/manual-reconcile/', views.manual_payment_reconciliation_view, name='manual_payment_reconciliation'),
    path('api/payments/manual-reconcile/suggest/', views.manual_payment_suggest_api, name='manual_payment_suggest_api'),
    path('business/payments/failed/', views.failed_payments_detail, name='failed_payments_detail'),
    path('business/payments/pending/', views.pending_payments_detail, name='pending_payments_detail'),
    path('business/enrollments/', views.enrollments_detail, name='enrollments_detail'),
    path('accounts/registrations/', views.registrations_detail, name='registrations_detail'),
    path('accounts/prospects/', views.prospects_detail, name='prospects_detail'),
    path('business/visitors/', views.visitors_detail, name='visitors_detail'),
    path('web-owner/pageviews/', views.pageviews_detail, name='pageviews_detail'),
    
    # API Endpoints for AJAX
    path('api/payments/successful/', views.successful_payments_api, name='successful_payments_api'),
    path('api/payments/failed/', views.failed_payments_api, name='failed_payments_api'),
    path('api/payments/pending/', views.pending_payments_api, name='pending_payments_api'),
    path('api/enrollments/', views.enrollments_api, name='enrollments_api'),
    path('api/business-metrics/', views.business_metrics_api, name='business_metrics_api'),
    path('api/pageviews/paths/', views.pageviews_paths_api, name='pageviews_paths_api'),
    path('api/visitors/filter-options/', views.visitors_filter_options_api, name='visitors_filter_options_api'),
    path('api/web-owner/optional-data/', views.web_owner_optional_data_api, name='web_owner_optional_data_api'),
    path('api/enquiry-ref-hit/', views.enquiry_ref_hit_api, name='enquiry_ref_hit_api'),
    path('api/payment-status/', views.payment_status_capture_api, name='payment_status_capture_api'),
    path('api/enquiry-source-events/', views.enquiry_source_events_api, name='enquiry_source_events_api'),
]

