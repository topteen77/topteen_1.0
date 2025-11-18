from django.urls import path, include
import users.views as user_views
urlpatterns = [
    path('user/', include('apis.user.urls')),
    path('crm/', include('apis.crm.urls')),
]