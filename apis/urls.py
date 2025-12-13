from django.urls import path, include
import users.views as user_views
urlpatterns = [
    path('user/', include('apis.user.urls')),
    path('crm/', include('apis.crm.urls')),
    # old code not in use - start
    # New isolated API routes for institute authentication
    # old code not in use - end
    path('institute/', include('apis.institute.urls')),
    path('counselor/', include('apis.counselor.urls')),
    # old code not in use - start
    # New isolated API routes for marketing authentication
    # old code not in use - end
    path('marketing/', include('apis.marketing.urls')),
]