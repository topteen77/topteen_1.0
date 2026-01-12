from django.urls import path,include
from topteenadmin import views

app_name="topteenadmin"
urlpatterns = [
    path("",views.TopteensDashboard.as_view(),name="topteendashboard"),
    
    #signup
    path('login/', views.LoginView.as_view(),name='login'),
    path('logout/', views.custom_logout,name='logout'),
    path('forgotpassword/',views.password_reset_request,name="forgotpassword"),
    path('changepassword/<uidb64>/<token>/',views.ChangePasswordView.as_view(),name="changepassword"),
    path('profile/',views.profileupdate,name="UpdateProfile"),
    
    # Media Library
    path('media-library/', views.MediaLibraryView.as_view(), name='media_library'),
    path('media-library/upload/', views.MediaLibraryUploadView.as_view(), name='media_library_upload'),
    path('media-library/delete-file/', views.MediaLibraryDeleteFileView.as_view(), name='media_library_delete_file'),
    path('media-library/create-folder/', views.MediaLibraryCreateFolderView.as_view(), name='media_library_create_folder'),
    path('media-library/delete-folder/', views.MediaLibraryDeleteFolderView.as_view(), name='media_library_delete_folder'),

    
]