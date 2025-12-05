from django.urls import path,include
from entrance_exams import views

app_name="entrance_exams"
urlpatterns = [
    path("",views.TestPreptenth.as_view(),name="testpreptenth"),
    path("<slug:exam_slug>-detail/",views.TestPrepDetail.as_view(),name="testprepdetail"),
    path("filter/",views.TestPrepFilter.as_view(),name="testprepfilter"),
    path("shortlist_exam/",views.shortlist_exam_view,name="shortlist_exam"),
]