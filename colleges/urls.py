from django.urls import path,include
from colleges import views

app_name="colleges"
urlpatterns = [
    path("college/<slug:slug>/",views.CollegeDetails.as_view(),name="collegedetail"),
    path("",views.CollegeList.as_view(),name='college'),
    path("shortlistcollege/",views.shortlist_college_view,name="shortlistcollege"),
]