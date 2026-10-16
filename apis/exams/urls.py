from django.urls import path

from . import views

app_name = "exams_api"

urlpatterns = [
    path("trending/", views.TrendingExamsAPI.as_view(), name="trending_exams"),
]
