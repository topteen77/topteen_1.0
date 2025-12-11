# old code not in use - start
# This is a new isolated API module for institute authentication
# old code not in use - end

from django.urls import path
from . import views

app_name = 'institute_api'

urlpatterns = [
    path('register/', views.InstituteRegisterAPI.as_view(), name='institute_register'),
    path('login/', views.InstituteLoginAPI.as_view(), name='institute_login'),
]
