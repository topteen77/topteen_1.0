
from django.urls import path, re_path
from . import views

app_name="counselor"

urlpatterns = [
    path("counselor_dashboard/<int:coun_id>/",views.CounselorDashboard,name="CounselorDashboardView"),
    path("Counselor_Course_payment/",views.CounselorCoursepayment,name="CounselorCoursepayment"),
    path("Counselor_Course_detail/", views.CounselorCourseDetailView.as_view(), name="counselor_course_detail"),
    path("Counselor_Course_curriculum/", views.CounselorCourseCurriculumView.as_view(), name="counselor_course_curriculum"),
    path(
        "Counselor_Course_curriculum/mindmap/",
        views.CounselorCourseCurriculumMindmapFullView.as_view(),
        name="course_curriculum_mindmap_full",
    ),
    path('Counselor_Course_payment_success/<path:enc_id>/', views.CounselorCoursePaymentSuccess.as_view(), name='counselor_course_payment_success'),
    path('Counselor_Course_payment_fail/<path:enc_id>/', views.CounselorCoursePaymentFail.as_view(), name='counselor_course_payment_fail'),
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
    path('update_counselor_course_payment/', views.update_counselor_course_payment, name='update_counselor_course_payment'),  # Update counselor course payment
    
    # Course Learning Module - New dedicated learning interface
    # Note: autocomplete must come before the general course_learning pattern
    path('course_learning/<int:counselor_id>/autocomplete/', views.autocomplete_course, name='autocomplete_course'),
    re_path(
        r'^course_learning/(?P<counselor_id>\d+)/caption/(?P<part_id>\d+)\.vtt$',
        views.part_caption_vtt,
        name='part_caption_vtt',
    ),
    path(
        'course_learning/<int:counselor_id>/case-study/<int:case_id>/',
        views.case_study_pdf,
        name='case_study_pdf',
    ),
    path(
        'course_learning/<int:counselor_id>/mindmap/chapter/<int:chapter_id>/',
        views.CourseLearningChapterMindmapView.as_view(),
        name='course_learning_chapter_mindmap',
    ),
    path(
        'course_learning/<int:counselor_id>/mindmap/part/<int:part_id>/',
        views.CourseLearningPartMindmapView.as_view(),
        name='course_learning_part_mindmap',
    ),
    path('course_learning/<int:counselor_id>/', views.CourseLearningView.as_view(), name='course_learning'),
    path('course_results/<int:counselor_id>/', views.CourseResultsView.as_view(), name='course_results'),
    path('view_certificate/<int:counselor_id>/', views.ViewCertificateView.as_view(), name='view_certificate'),
    path('submit_quiz_question/<int:counselor_id>/', views.submit_quiz_question, name='submit_quiz_question'),
    path('submit_full_quiz/<int:counselor_id>/<int:quiz_id>/', views.submit_full_quiz, name='submit_full_quiz'),
    
    # Counselor authentication routes
    path("auth/login/", views.CounselorLoginView.as_view(), name="login"),
]