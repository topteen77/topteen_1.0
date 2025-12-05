# quiz/urls.py

from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

app_name = 'app'


urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('home/', views.test_buttons, name='test_buttons'),

    path('logout/', views.custom_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
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
    path('download_pdf/<str:test_paper>/', views.download_pdf, name='download-pdf'),

    # new addition
    path('export-to-excel/<str:email>/', views.export_to_excel, name='export_to_excel'),
    path('test_1/<str:test_paper>/', views.test_1, name='test_1'),
    path('pdf-check/', views.pdf_checker, name='pdf'),

]
    
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

print(static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT))

""" ### old paths """
# urlpatterns = [

#     path('upload/', views.upload_file, name='upload_file'),
#     path('questions/', views.quiz_questions, name='quiz_questions'),
#     path('submit/', views.app_submit, name='app_submit'),
#     path('download_pdf/', views.download_pdf, name='download-pdf'),
#     # path('pdf_view/', views.ViewPDF.as_view(), name="pdf_view"),
#     path('generate_pdf/', views.generate_pdf, name='download-pdf'),
# ]
