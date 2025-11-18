# analytics_dashboard/urls.py
from django.urls import path
from . import views

app_name = 'analytics_dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('update-data/', views.update_dashboard_data, name='update_dashboard_data'),
    path('real-time-data/', views.get_real_time_data, name='get_real_time_data'),
]
