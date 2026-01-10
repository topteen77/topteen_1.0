from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('course/<int:course_id>/', views.CourseDetailView.as_view(), name='coursedetail'),
    path('course/<slug:slug>-<int:course_id>/', views.CourseDetailView.as_view(), name='coursedetail'),
]
