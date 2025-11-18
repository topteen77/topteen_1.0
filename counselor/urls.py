
from django.urls import path,include
from . import views

app_name="counselor"

urlpatterns = [
    path("counselor_dashboard/<int:coun_id>/",views.CounselorDashboard,name="CounselorDashboardView"),
    path("Counselor_Course_payment",views.CounselorCoursepayment,name="CounselorCoursepayment"),
    path("Counselor_Course/<int:counselor_id>/",views.CourseStartsView.as_view(),name="Counselor_Course"),
    path('Counselor_enrolled_course/', views.CounselorEnrolledCourseView.as_view(), name='counselor_enrolled_course'),
    path('<int:coun_id>/follow_up/',views.Students_follow_up, name='Counselor_follow_up_page'),


    path('display_pdfs/', views.display_pdfs, name='display_pdfs'),
    path('testvttvideo/', views.TestVttVideo, name='TestVttVideo'),
    # path('notes/add/<int:part_id>/', views.add_note, name='add_note'),
    # path('notes/edit/<int:note_id>/', views.edit_note, name='edit_note'),
    # path('notes/delete/<int:note_id>/', views.delete_note, name='delete_note'),

    path('notes/add/<int:part_id>/', views.add_note, name='add_note'),
    path('notes/edit/<int:note_id>/<int:part_id>/', views.edit_note, name='edit_note'),
    path('notes/delete/<int:note_id>/', views.delete_note, name='delete_note'),

    path('update_progress/', views.update_progress, name='update_progress'),  # Update progress
    path('get_progress_and_duration/<str:video_id>/', views.get_progress_and_duration, name='get_progress_and_duration'),  # Get progress
]