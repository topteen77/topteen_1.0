# old code not in use - start
# This is a new isolated API module for marketing authentication
# old code not in use - end

from django.urls import path
from . import views

app_name = 'marketing_api'

urlpatterns = [
    path('register/', views.MarketingRegisterAPI.as_view(), name='marketing_register'),
    path('login/', views.MarketingLoginAPI.as_view(), name='marketing_login'),
]

