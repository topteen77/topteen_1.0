"""
URL routing for user_analytics app.
"""
from django.urls import path
from . import views

app_name = 'user_analytics'

urlpatterns = [
    # Main dashboard (redirects to business)
    path('', views.dashboard, name='dashboard'),
    
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
]

