from django.urls import path,include
from . import views

app_name = "skilllabcourse"
urlpatterns = [
    path("",views.SkillLabCourseList.as_view(),name="skilllabcourselist"),
    path("skilllabcoursedetail/<slug:skilllab_slug>/",views.SkillLabCourseDetail.as_view(),name="skilllabcoursedetail"),
    path("course_learning/<slug:course_slug>/",views.SkillLabCourseLearningView.as_view(),name="course_learning"),
    path("save-resume/", views.SkillLabSaveResumeView.as_view(), name="save_resume"),
    path("mark-chapter-complete/",views.SkillLabMarkChapterCompleteView.as_view(),name="mark_chapter_complete"),
    path("section-content/",views.SkillLabSectionContentView.as_view(),name="section_content"),
    path("mark-worksheet-downloaded/",views.SkillLabMarkWorksheetDownloadedView.as_view(),name="mark_worksheet_downloaded"),
    path("download-worksheet/<int:activity_id>/",views.SkillLabWorksheetDownloadView.as_view(),name="download_worksheet"),
    path("submit-mcq/",views.SkillLabSubmitMCQView.as_view(),name="submit_mcq"),
    path("certificate/<slug:course_slug>/",views.SkillLabCourseCertificateView.as_view(),name="skilllab_certificate"),
    path("skilllabcoursechapterdetail/<slug:chapter_slug>/",views.SkillLabCourseChapterDetail.as_view(),name="skilllabcoursechapterdetail"),
    path("skilllabcourseactivityworksheetdetail/<slug:workactive_slug>/",views.SkillLabCourseActivityDetail.as_view(),name="skilllabcourseactivityworksheetdetail"), 
    path('skilllabcourse-payment-success/<str:enc_id>/',views.SkilllabCoursePaymentSuccess.as_view(),name="skillabcoursepaymentsuccess"),
    path('skilllabcourse-payment-fail/<str:enc_id>/',views.SkilllabCoursePaymentFail.as_view(),name="skilllabcoursepaymentfail"),
    path("skilllab-course-payment/<slug:slug>/",views.CreateSkilllabCoursePaymentWithEazyPay.as_view(),name="createskilllabcoursepayment"), 
    path("update-skilllab-course-payment/",views.UpdateSkilllabCoursePaymentWithEazyPay.as_view(),name="updateskilllcaourseeazypay"),
]