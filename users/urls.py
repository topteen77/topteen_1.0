from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from .import views
from django.contrib.auth import views as auth_views
from django.conf import settings

app_name = 'users'

urlpatterns = [
   path('login', views.LoginView.as_view(),name='login'),
   path('login/<str:enc_id>', views.LoginView.as_view(),name='referallogin'),
   path('profiledetails', views.ProfileBasicDetails.as_view(), name="profiledetails"),
   path('loginsingup',views.LoginSignUp.as_view(),name='loginsingup'),
   path('signupverifyotp',views.SignUpVerifyOTP.as_view(),name='signupotpverify'),
   path('signuppwd',views.SignUpPassword.as_view(),name='signuppwd'),
   path('loginotp',views.LoginOTP.as_view(),name='loginotp'),
   path('loginpwd',views.LoginPassword.as_view(),name="loginpwd"),
   path('get-dashboard-url',views.GetUserDashboardUrl.as_view(),name="getdashboardurl"),
   path('forgotpassword',views.ForgotPassword.as_view(),name="forgotpassword"),
   path('forgotpasswordotp',views.ForgotPasswordVerifyOTP.as_view(),name="forgotpasswordotp"),
   path('resendotp',views.ResendOtp.as_view(),name="resendotp"),
   path('dashboard',views.UserDashboard.as_view(),name="userdashboard"),
   path('user-feeds',views.UserFeeds.as_view(),name="userfeeds"),
   path('logout',views.logout,name="logout"),
   path('welcome',views.Welcomepage.as_view(),name="welcome"),  
   path('scrapbook',views.Scrapbook.as_view(),name="scrapbook"),
   path('my-notepad',views.MyNotePad.as_view(),name="mynotepad"),
   path('create-note',views.CreateNote.as_view(),name="createnote"),
   path('create-note/<int:id>',views.CreateNote.as_view(),name="updatenote"),
   path('my-hobbies',views.UserHobbies.as_view(),name="myhobbies"),
   path('career-interests',views.CareerInterests.as_view(),name="careerinterest"),
   path('save-media',views.SaveMedia.as_view(),name="savemedia"),
   path('resume-builder',views.ResumeBuilder.as_view(),name="resumebuilder"),
   path('resume-builder-welcome',views.ResumeBuilderWelcome.as_view(),name="resumebuilderwelcome"),
   path('folders',views.UserFolders.as_view(),name="userfolders"),
   path('folder/<int:id>',views.UserFolderDetail.as_view(),name="userfolder"),
   path("resume-pdf",views.resume_pdf_download,name="resumepdf"),
   path("calender",views.UserCalenderView.as_view(),name="usercalender"),
   path("event-delete/<int:id>",views.UserEventDeleteView,name="eventdelete"),
   path("user-colleges/",views.UserColleges.as_view(),name="mycolleges"),
   path("user-history",views.UserHistoryView.as_view(),name="userhistory"),
   path('bookmark',views.Bookmark.as_view(),name="bookmark"),
   path('bookmarkvideo',views.BookmarkVideo.as_view(),name="bookmarkvideo"),
   path('bookmarkexam',views.BookmarkExam.as_view(),name="bookmarkexam"),
   path('bookmarkcollege',views.BookmarkCollege.as_view(),name="bookmarkcollege"),
   path('refer',views.ReferView.as_view(),name="refer"),


   # manish
   path('create-institute/', views.create_institute, name='create_institute'),
   
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
