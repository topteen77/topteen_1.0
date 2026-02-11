from django.urls import path
from . import views

app_name = 'olympiad'

urlpatterns = [
    path('', views.OlympiadExamListView.as_view(), name='exam_list'),
    path('take/<int:session_id>/', views.OlympiadTakeExamView.as_view(), name='take_exam'),
    path('result/<int:session_id>/', views.OlympiadResultDetailView.as_view(), name='result_detail'),
    path('certificate/<int:session_id>/', views.OlympiadCertificateView.as_view(), name='certificate'),
    path('api/exams/', views.olympiad_exam_list_api, name='api_exam_list'),
    path('api/register/<int:exam_id>/', views.OlympiadRegisterView.as_view(), name='api_register'),
    path('api/start/<int:exam_id>/', views.OlympiadStartExamView.as_view(), name='api_start'),
    path('api/submit-answer/', views.OlympiadSubmitAnswerView.as_view(), name='api_submit_answer'),
    path('api/submit-exam/<int:session_id>/', views.OlympiadSubmitExamView.as_view(), name='api_submit_exam'),
    path('my-results/', views.OlympiadMyResultsView.as_view(), name='my_results'),
]
