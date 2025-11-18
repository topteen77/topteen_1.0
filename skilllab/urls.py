from django.urls import path,include
from . import views

app_name="skilllab"
urlpatterns = [
    path("",views.SkillLabCourseList.as_view(),name="skilllabcourselist"),
    path("skilllabcoursedetail/<slug:skilllab_slug>",views.SkillLabCourseDetail.as_view(),name="skilllabcoursedetail"),
    path("skilllabcoursechapterdetail/<slug:chapter_slug>",views.SkillLabCourseChapterDetail.as_view(),name="skilllabcoursechapterdetail"),
    path("skilllabcourseactivityworksheetdetail/<slug:workactive_slug>",views.SkillLabCourseActivityDetail.as_view(),name="skilllabcourseactivityworksheetdetail"), 
    path('skilllabcourse-payment-success/<str:enc_id>',views.SkilllabCoursePaymentSuccess.as_view(),name="skillabcoursepaymentsuccess"),
    path('skilllabcourse-payment-fail/<str:enc_id>',views.SkilllabCoursePaymentFail.as_view(),name="skilllabcoursepaymentfail"),
    path("skilllab-course-payment/<slug:slug>",views.CreateSkilllabCoursePaymentWithEazyPay.as_view(),name="createskilllabcoursepayment"), 
    path("update-skilllab-course-payment",views.UpdateSkilllabCoursePaymentWithEazyPay.as_view(),name="updateskilllcaourseeazypay"),
]