from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notifications_page, name='page'),
    path('admin/settings/', views.notification_admin_settings, name='admin_settings'),
    path('api/latest/', views.notifications_latest_api, name='latest_api'),
    path('api/list/', views.notifications_list_api, name='list_api'),
    path('api/mark-read/', views.notification_mark_read_api, name='mark_read_api'),
    path('api/mark-all-read/', views.notification_mark_all_read_api, name='mark_all_read_api'),
    path('api/delete/', views.notification_delete_api, name='delete_api'),
    path('api/admin/toggle-type/', views.notification_toggle_type_api, name='toggle_type_api'),
    path('api/admin/delete-all/', views.notification_admin_delete_all_api, name='delete_all_api'),
]

