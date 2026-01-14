"""
URL routing for user_analytics app.
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
    
    # User Journey
    path('user-journey/', views.user_journey_view, name='user_journey'),
    path('user-journey/<int:user_id>/', views.user_journey_view, name='user_journey_detail'),
    
    # API Endpoints
    path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard_data'),
    
    # Detail Pages with Filters
    path('business/payments/successful/', views.successful_payments_detail, name='successful_payments_detail'),
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
]

