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
    path('profile/',views.profileupdate,name="UpdateProfile")

    
]