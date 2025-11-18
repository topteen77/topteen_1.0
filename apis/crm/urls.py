from django.urls import path
from . import views

urlpatterns = [
    path("leads",views.LeadsAPI.as_view(),name="leads"),
]