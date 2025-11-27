from django.urls import path,include
from careers import views
from . import api_views

app_name="careers"
urlpatterns = [
    path("",views.Careers.as_view(),name="career"),
    path("career/<slug>-<int:career_id>-detail",views.CareerDetail.as_view(),name="careerdetail"),
    path("profession/<slug:career_slug>",views.Professions.as_view(),name="profession"),
    path("tag/<slug:tagslug>",views.CareerTagFilter.as_view(),name='careertag'),
    path("careerlibrary",views.CareerLibrary.as_view(),name='defaultcareerlibrary'),
    path("careerlibrary/<slug:cluster_slug>-<int:cluster_id>",views.CareerLibrary.as_view(),name="careerlibrary"),
    
    path("career-videos",views.CareerVideosView.as_view(),name="careervideos"),
    path("career-videos/category/<slug:category_slug>",views.CategoryCareerVideosView.as_view(),name="category"),
    path("career-videos/<video_slug>",views.VideoDetail.as_view(),name="videodetail"),
    path("career_rating",views.CareerRatingView.as_view(),name="careerrating"),
    path("career_rating_delete/<int:id>",views.career_rate_delete_view,name="ratingdelete"),
    path("shortlist_video",views.shortlist_video_view,name="shortlist_video"),
    
    # API endpoints
    path("api/process-docx/", api_views.process_docx_api, name="process_docx_api"),
    path("api/autocomplete/professions/", api_views.autocomplete_professions, name="autocomplete_professions"),
    path("api/autocomplete/skills/", api_views.autocomplete_skills, name="autocomplete_skills"),
    path("api/autocomplete/clusters/", api_views.autocomplete_clusters, name="autocomplete_clusters"),
]