"""topteens URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls import handler404
from users import views as users_views
from user_analytics import views as user_analytics_views
from core import views as core_views
from core.seo_views import robots_txt, sitemap_xml
from core.sitemaps import (
    BlogSitemap,
    CareerSitemap,
    CollegeSitemap,
    CourseSitemap,
    EntranceExamSitemap,
    EntranceTestPrepExamSitemap,
    GeneratedPageSitemap,
    StaticViewSitemap,
    VocationalCourseSitemap,
)
from django.views.generic import TemplateView

sitemaps = {
    "static": StaticViewSitemap,
    "blogs": BlogSitemap,
    "careers": CareerSitemap,
    "colleges": CollegeSitemap,
    "courses": CourseSitemap,
    "entrance_exams": EntranceExamSitemap,
    "entrance_test_prep_exams": EntranceTestPrepExamSitemap,
    "vocational_courses": VocationalCourseSitemap,
    "generated_pages": GeneratedPageSitemap,
}

urlpatterns = [
    path("sitemap.xml", sitemap_xml, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
    # S3 media proxy: serve S3 files through Django when S3_MEDIA_ACCESS_MODE=proxy (only your site can show media)
    path('media/s3/<path:path>', core_views.s3_media_proxy, name='s3_media_proxy'),
    path('admin/', admin.site.urls),
    path("topteenadmin/",include("topteenadmin.urls",namespace="topteenadmin")),
    path("topteenadmin/managed/",include("topteenadmin.managed_urls",namespace="topteenadminmanaged")),
    path("",include("core.urls")),
    
    path("careers/",include("careers.urls",namespace="careers")),
    path("courses/",include("courses.urls",namespace="courses")),
    path("colleges/",include("colleges.urls",namespace="colleges")),
    path("testprep/",include("entrance_exams.urls",namespace="entrance_exams")),
    path("skilllabcourse/",include("skilllab.urls",namespace="skilllabcourse")),
    path("psychometrictest/",include("psychometric_tests.urls",namespace="psychometrictests")),
    path("payments/",include("payments.urls",namespace="payments")),
    path("blogs/",include('blog.urls')),
    
    path('user/', include('users.urls',namespace='users')),
    # Role-specific auth landing pages (Jinja templates)
    path('student/login/', users_views.StudentLoginView.as_view(), name='student_login'),
    path('student/signup/', users_views.StudentSignupView.as_view(), name='student_signup'),
    path('parents/login/', users_views.ParentsLoginView.as_view(), name='parents_login'),
    path('parents/dashboard/', users_views.ParentsDashboardView.as_view(), name='parents_dashboard'),
    path('parents/student/<int:student_id>/dashboard/', users_views.ParentStudentDashboardView.as_view(), name='parents_student_dashboard'),
    path('parents/student/<int:student_id>/profile/view/', users_views.ParentStudentViewProfileView.as_view(), name='parents_student_view_profile'),
    path('parents/student/<int:student_id>/profile/edit/', users_views.ParentStudentEditProfileView.as_view(), name='parents_student_edit_profile'),
    path('parents/student/<int:student_id>/results/', users_views.ParentStudentPsychometricResultView.as_view(), name='parents_student_results'),
    path('parents/student/<int:student_id>/bookmarks/careers/', users_views.ParentStudentBookmarkCareersView.as_view(), name='parents_student_bookmark_careers'),
    path('parents/student/<int:student_id>/bookmarks/videos/', users_views.ParentStudentBookmarkVideosView.as_view(), name='parents_student_bookmark_videos'),
    path('parents/student/<int:student_id>/bookmarks/colleges/', users_views.ParentStudentBookmarkCollegesView.as_view(), name='parents_student_bookmark_colleges'),
    path('parents/student/<int:student_id>/bookmarks/blogs/', users_views.ParentStudentBookmarkBlogsView.as_view(), name='parents_student_bookmark_blogs'),
    path('parents/student/<int:student_id>/bookmark/career/', users_views.ParentStudentToggleCareerBookmark.as_view(), name='parents_student_toggle_career_bookmark'),
    path('parents/student/<int:student_id>/bookmark/video/', users_views.ParentStudentToggleVideoBookmark.as_view(), name='parents_student_toggle_video_bookmark'),
    path('parents/student/<int:student_id>/bookmark/college/', users_views.ParentStudentToggleCollegeBookmark.as_view(), name='parents_student_toggle_college_bookmark'),
    path('parents/student/<int:student_id>/bookmark/blog/', users_views.ParentStudentToggleBlogBookmark.as_view(), name='parents_student_toggle_blog_bookmark'),
    path('parents/student/<int:student_id>/suggestions/<str:kind>/', users_views.ParentStudentSuggestedListView.as_view(), name='parents_student_suggestions'),
    path('api/loan/calculate', users_views.LoanCalculatorAPIView.as_view(), name='api_loan_calculate'),
    path('oauth/', include('social_django.urls', namespace='social')),
    path('api/v1/', include('apis.urls')),
    path("institute/",include('institute.urls', namespace='institute')),
    path("psychometric/",include('app.urls',namespace='app')),
    path("api/",include('app_post_matric.urls',namespace='post_matric')),
    path("counselor/",include('counselor.urls',namespace='counselor')),
    path('analytics/', include('analytics_dashboard.urls')),
    path('user-analytics/', include('user_analytics.urls', namespace='user_analytics')),
    path('entry/attribution/', user_analytics_views.enquiry_ref_hit_api, name='entry_attribution'),
    path('forum/', include('forum.urls', namespace='forum')),
    path('seo-dashboard/', include('seo_dashboard.urls', namespace='seo_dashboard')),
    path('notifications/', include('notifications.urls', namespace='notifications')),

    # old code not in use - start
    # New isolated routes for marketing authentication frontend
    # old code not in use - end
    path("marketing-auth/",include('institute.marketing_urls', namespace='marketing')),

    path('api-auth/', include('rest_framework.urls')),


]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# Local MEDIA_ROOT: always at /media/ in DEBUG (graph_images etc.), even when S3 proxy mode is on.
# Production without DEBUG: serve locally only when not using S3 proxy mode.
if settings.DEBUG:
    urlpatterns += static('/media/', document_root=settings.MEDIA_ROOT)
elif getattr(settings, 'S3_MEDIA_ACCESS_MODE', None) != 'proxy':
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Debug toolbar is commented out in settings, so commenting out here too
# if settings.DEBUG:
#     try:
#         import debug_toolbar
#         urlpatterns += [
#             path('__debug__/', include('debug_toolbar.urls')),
#         ]
#     except ImportError:
#         pass

# Catch-all pattern for unmatched URLs - uses template20/404.html
# Exclude all known URL prefixes to avoid intercepting valid routes
urlpatterns += [
    re_path(r'^(?!admin/|topteenadmin/|careers/|colleges/|testprep/|skilllabcourse/|psychometrictest/|payments/|blogs/|user/|student/|parents/|oauth/|api/|institute/|psychometric/|counselor/|analytics/|user-analytics/|forum/|marketing-auth/|api-auth/|static/|media/).*$', 
            TemplateView.as_view(template_name='template20/404.html'), name='404'),
]

handler404="core.views.page404"