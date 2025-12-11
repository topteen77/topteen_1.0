from django.urls import path
from . import views

app_name = 'counselor_api'

urlpatterns = [
    path('login/', views.CounselorLoginAPI.as_view(), name='login'),
]
