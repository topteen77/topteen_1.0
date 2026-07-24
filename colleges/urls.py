from django.urls import path,include
from colleges import views

app_name="colleges"
urlpatterns = [
    path("college/<slug:slug>/",views.CollegeDetails.as_view(),name="collegedetail"),
    path(
        "institute/<int:college_id>/",
        views.IndianCollegeDetails.as_view(),
        name="indian_collegedetail",
    ),
    path(
        "institute/<int:college_id>/<slug:tab>/",
        views.IndianCollegeDetails.as_view(),
        name="indian_collegedetail_tab",
    ),
    path("",views.CollegeList.as_view(),name='college'),
    path("shortlistcollege/",views.shortlist_college_view,name="shortlistcollege"),
]