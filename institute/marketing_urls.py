# old code not in use - start
# New isolated URL routes for marketing authentication frontend
# old code not in use - end

from django.urls import path
from . import views

app_name = 'marketing'

urlpatterns = [
    path('register/', views.MarketingRegisterView.as_view(), name='register'),
    path('login/', views.MarketingLoginView.as_view(), name='login'),
]

