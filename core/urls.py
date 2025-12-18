from django.contrib import admin
from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path("",views.Home.as_view(),name="home"),
    path("searchand-explore/",views.SearchItems.as_view(),name="searchandexplore"),
    path("searchand-explore-result/",views.AjaxSearchResult.as_view(),name="searchandexploreresult"),
    path("recommandedsearch/",views.AjaxRecommandedSearchCollege.as_view(),name="recommandedsearch"),
    path("terms-and-condition/",views.terms_and_condition,name="terms&condition"),
    path("privacy-policy/",views.privacy_policy,name="privacypolicy"),
    path("contact-us/",views.contact_us,name="contactus"),
    path("upload/",views.upload,name="upload"),
    path("about-us/",views.AboutUsView.as_view(),name="aboutus"),
    path("all-faq/",views.AllFaqView.as_view(),name="allfaq"),
    path("extracurricular-activities/", views.ExtracurricularActivitiesView.as_view(), name="extracurricular_activities"),
    path("extracurricular-activities/activity/<int:pk>/", views.ExtracurricularActivityDetailView.as_view(), name="extracurricular_activity_detail"),
    path("vocational-courses/", views.VocationalCoursesView.as_view(), name="vocational_courses"),
    path("vocational-courses/<slug:level_slug>/", views.VocationalCoursesLevelView.as_view(), name="vocational_courses_level"),
    path("vocational-courses/course/<int:pk>/", views.VocationalCourseDetailView.as_view(), name="vocational_course_detail"),
    path("career-planning/", views.CareerPlanningView.as_view(), name="career_planning"),
    path("delete-history/",views.deletehistory,name="deletehistory"), 
    path("lead-submit/",views.LeadData.as_view(),name="lead_submit"),  
]