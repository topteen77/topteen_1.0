from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views
app_name = "post_matric"

router = DefaultRouter()
router.register(r'categories', views.TestCategoryViewSet)
router.register(r'tests', views.TestViewSet)
router.register(r'sections', views.SectionsViewSet)
router.register(r'questions', views.QuestionViewSet)
router.register(r'answers', views.AnswerViewSet)  # Add this line for answers
router.register(r'sessions', views.TestSessionViewSet, basename='session')
router.register(r'responses', views.UserResponseViewSet, basename='response')
router.register(r'results', views.TestResultViewSet, basename='result')
router.register(r'section-sessions', views.SectionSessionViewSet, basename='section-session')


urlpatterns = [
    # Custom API endpoints (place before router to ensure they're matched first)
    # Note: 'api/' prefix is already included in main urls.py, so we use 'web/popup-answer/' here
    path('web/popup-answer/', views.save_popup_answer, name='save_popup_answer'),

    # Router URLs
    path('', include(router.urls)),

    path('web/home/', views.Home, name='home'),
    path('web/profile/', views.Profile, name='profile'),
    path('web/Report/', views.Report, name='home1'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('web/tests/', views.Tests, name='tests'),
    path('web/results/', views.Results, name='results'),
    path('web/results_list/', views.Results_list, name='results_list'),
    path('web/take_test/<int:id>/', views.Take_test, name='take_test'),
    path('web/test_details/<int:id>/', views.Test_details, name='test_details'),
    path('web/test_results/<int:id>/', views.Test_results, name='test_results'),
    path('web/test_results/<int:id>/download-pdf/', views.download_test_results_pdf, name='download_test_results_pdf'),
    # path('register/', views.register_view, name='register'),
    path("web/download-users/", views.download_users_excel, name="download_users"),
    path('web/combined_report/<int:user_id>/', views.CombinedReport, name='combined_report'),
    # Section specific URLs (if needed)
    path('web/test/<int:test_id>/sections/', views.test_sections, name='test_sections'),  # New
    path('web/test/<int:testId>/section/<int:section_id>/<int:session_id>/starttest/', views.section_details, name='section_details'),  # New
    path('web/section/<int:section_id>/start/', views.start_section, name='start_section'),  # New
    # Update this line
    # path('api/web/test/<int:test_id>/sections/<int:section_id>/details/', views.section_details, name='section_details'),
    
    # Update results URL pattern too
    path('web/test/<int:testId>/result/<int:result_id>/', views.section_results, name='section_results'),
    # path('api/web/test/<int:testId>/sections/<int:section_id>/<int:session_id>/results/', views.section_results, name='section_results'),
    path('web/section-session/<int:session_id>/', views.section_session_detail, name='section_session_detail'),  # New
    

    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', views.RegisterView.as_view(), name='auth_register'),
    path('users/me/', views.CurrentUserView.as_view(), name='current_user'),
    path('web/career-swipe/', views.career_swipe, name='career_swipe'),
    path('web/career-matches/', views.view_matches, name='view_matches'),
    path('web/top-recommendations/', views.top_recommendations, name='top_recommendations'),
    path('web/career-clusters/', views.career_clusters_info, name='career_clusters_info'),
    path('api/career-swipe/action/', views.swipe_career_api, name='swipe_career_api'),
]

# urlpatterns = router.urls