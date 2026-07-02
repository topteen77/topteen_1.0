# quiz/urls.py

from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

app_name = 'app'


urlpatterns = [
    path('speed-test/', views.speed_test, name='speed_test'),
    path('upload/', views.upload_file, name='upload_file'),
    path('home/', views.test_buttons, name='test_buttons'),

    path('logout/', views.custom_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/<int:user_id>/', views.dashboard, name='dashboard_for_user'),
    path('career-tree/', views.career_tree, name='career-tree'),
    path('career-tree1/', views.career_tree1, name='career-tree1'),
    path('quick-link/', views.quick_link, name='quick-link'),
    path('final_assessment_pdf/', views.final_assessment_pdf, name='final_assessment_pdf'),
    path('Assessment_pdf_inst_user/<int:user_id>/', views.Assessment_pdf_inst_user, name='Assessment_pdf_inst_user'),
    path('t1_intro/', views.test1_intro, name='test1-intro'),
    path('t2_intro/', views.test2_intro, name='test2-intro'),
    path('t3_intro/', views.test3_intro, name='test3-intro'),
    path('test1/', views.test1_view, name='test1_view'),
    path('test2/', views.test2_view, name='test2_view'),
    path('test3/', views.test3_view, name='test3_view'),

    path('test3_numerical/', views.test3_numerical, name='test3-numerical'),
    path('test3_logical/', views.test3_logical, name='test3-logical'),
    path('test3_verbal/', views.test3_verbal, name='test3-verbal'),
    path('test3_emotional/', views.test3_emotional, name='test3-emotional'),
    path('test3_machanical/', views.test3_machanical, name='test3-machanical'),
    path('test3_language/', views.test3_language, name='test3-language'),
    path('test3_spatial/', views.test3_spatial, name='test3-spatial'),

    
    path('submit/', views.app_submit, name='app_submit'),
    path('submit_clicks/', views.submit_clicks, name='submit_clicks'),
    path(
        'stream-decision-questionnaire/submit/',
        views.stream_decision_questionnaire_submit,
        name='stream_decision_questionnaire_submit',
    ),
    path('download_pdf/<str:test_paper>/', views.download_pdf, name='download-pdf'),

    # new addition
    path('export-to-excel/<str:email>/', views.export_to_excel, name='export_to_excel'),
    path('test_1/<str:test_paper>/', views.test_1, name='test_1'),
    path('pdf-check/', views.pdf_checker, name='pdf'),
    path('pdf-preview/test<int:test_number>/', views.test_pdf_preview, name='test_pdf_preview'),
    path('pdf-preview/test<int:test_number>/<int:user_id>/', views.test_pdf_preview, name='test_pdf_preview'),
    
    # Class 10 Combined Report endpoints
    path('web/combined_report/<int:user_id>/', views.class10_combined_report, name='class10_combined_report'),
    path('web/combined_report/<int:user_id>/download-pdf/', views.class10_report_download_pdf, name='class10_report_download_pdf'),
    # Allow viewing own report without user_id
    path('web/combined_report/', views.class10_combined_report, name='class10_combined_report_own'),
    path('web/combined_report/download-pdf/', views.class10_report_download_pdf, name='class10_report_download_pdf_own'),
    
    # Individual Test Report endpoints (HTML)
    path('web/test1_report/', views.test1_report_html, name='test1_report_html'),
    path('web/test1_report/<int:user_id>/', views.test1_report_html, name='test1_report_html'),
    path('web/test2_report/', views.test2_report_html, name='test2_report_html'),
    path('web/test2_report/<int:user_id>/', views.test2_report_html, name='test2_report_html'),
    path('web/test3_report/', views.test3_report_html, name='test3_report_html'),
    path('web/test3_report/<int:user_id>/', views.test3_report_html, name='test3_report_html'),
    
    # Individual Test Report endpoints (PDF)
    path('web/test1_report/download-pdf/', views.test1_report_pdf, name='test1_report_pdf'),
    path('web/test1_report/<int:user_id>/download-pdf/', views.test1_report_pdf, name='test1_report_pdf'),
    path('web/test2_report/download-pdf/', views.test2_report_pdf, name='test2_report_pdf'),
    path('web/test2_report/<int:user_id>/download-pdf/', views.test2_report_pdf, name='test2_report_pdf'),
    path('web/test3_report/download-pdf/', views.test3_report_pdf, name='test3_report_pdf'),
    path('web/test3_report/<int:user_id>/download-pdf/', views.test3_report_pdf, name='test3_report_pdf'),

]
    
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static('/media/', document_root=settings.MEDIA_ROOT)

""" ### old paths """
# urlpatterns = [

#     path('upload/', views.upload_file, name='upload_file'),
#     path('questions/', views.quiz_questions, name='quiz_questions'),
#     path('submit/', views.app_submit, name='app_submit'),
#     path('download_pdf/', views.download_pdf, name='download-pdf'),
#     # path('pdf_view/', views.ViewPDF.as_view(), name="pdf_view"),
#     path('generate_pdf/', views.generate_pdf, name='download-pdf'),
# ]
