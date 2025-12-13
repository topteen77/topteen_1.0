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
from django.urls import path,include
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls import handler404
urlpatterns = [
    path('admin/', admin.site.urls),
    path("topteenadmin/",include("topteenadmin.urls",namespace="topteenadmin")),
    path("topteenadmin/managed/",include("topteenadmin.managed_urls",namespace="topteenadminmanaged")),
    path("",include("core.urls")),
    
    path("careers/",include("careers.urls",namespace="careers")),
    path("colleges/",include("colleges.urls",namespace="colleges")),
    path("testprep/",include("entrance_exams.urls",namespace="entrance_exams")),
    path("skilllabcourse/",include("skilllab.urls",namespace="skilllabcourse")),
    path("psychometrictest/",include("psychometric_tests.urls",namespace="psychometrictests")),
    path("payments/",include("payments.urls",namespace="payments")),
    path("blogs/",include('blog.urls')),
    
    path('user/', include('users.urls',namespace='users')),
    path('oauth/', include('social_django.urls', namespace='social')),
    path('api/v1/', include('apis.urls')),
    path("institute/",include('institute.urls', namespace='institute')),
    path("psychometric/",include('app.urls',namespace='app')),
    path("api/",include('app_post_matric.urls',namespace='post_matric')),
    path("counselor/",include('counselor.urls',namespace='counselor')),
    path('analytics/', include('analytics_dashboard.urls')),
    path('user-analytics/', include('user_analytics.urls', namespace='user_analytics')),

    # old code not in use - start
    # New isolated routes for marketing authentication frontend
    # old code not in use - end
    path("marketing-auth/",include('institute.marketing_urls', namespace='marketing')),

    path('api-auth/', include('rest_framework.urls')),


]
# if settings.DEBUG:
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
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
from django.urls import path, include, re_path
from django.views.generic import TemplateView

# Catch-all pattern for unmatched URLs - uses template20/404.html
urlpatterns += [
    re_path(r'^.*$', TemplateView.as_view(template_name='template20/404.html'), name='404'),
]

handler404="core.views.page404"