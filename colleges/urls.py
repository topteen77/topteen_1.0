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
    path(
        "shortlist-indian-college/",
        views.shortlist_indian_college_view,
        name="shortlist_indian_college",
    ),
    path(
        "matched-courses/",
        views.MatchedCoursesView.as_view(),
        name="matched_courses",
    ),
    path(
        "api/matched-courses/",
        views.psychometric_match_courses_api,
        name="matched_courses_api",
    ),
    path(
        "courses/<int:course_id>/",
        views.IndianCourseDetailView.as_view(),
        name="indian_course_detail",
    ),
]