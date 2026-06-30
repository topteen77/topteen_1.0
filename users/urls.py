from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.views.generic import RedirectView
from .import views
from .resume_v2_views import (
    ResumeV2AIReviewView,
    ResumeV2AIView,
    ResumeV2AnalyticsPartialView,
    ResumeV2AutofillView,
    ResumeV2CreateView,
    ResumeV2DashboardView,
    ResumeV2DeleteView,
    ResumeV2GoalView,
    ResumeV2StudioView,
    ResumeV2TemplatesView,
)
from django.contrib.auth import views as auth_views
from django.conf import settings

app_name = 'users'

urlpatterns = [
   path('login/', views.LoginView.as_view(),name='login'),
   path('login/<str:enc_id>/', views.LoginView.as_view(),name='referallogin'),
   path('demo-login/', views.DemoLoginView.as_view(), name='demo_login'),
   path('profiledetails/', views.ProfileBasicDetails.as_view(), name="profiledetails"),
   path('viewprofile/', views.ViewProfile.as_view(), name="viewprofile"),
   path('update-profile-section/', views.UpdateProfileSectionView.as_view(), name="update_profile_section"),
   path('loginsingup/',views.LoginSignUp.as_view(),name='loginsingup'),
   path('signupverifyotp/',views.SignUpVerifyOTP.as_view(),name='signupotpverify'),
   path('signuppwd/',views.SignUpPassword.as_view(),name='signuppwd'),
   path('loginotp/',views.LoginOTP.as_view(),name='loginotp'),
   path('loginpwd/',views.LoginPassword.as_view(),name="loginpwd"),
   path('set-password/',views.SetPassword.as_view(),name="setpassword"),
   path('change-own-password/', views.ChangeOwnPasswordView.as_view(), name="changeownpassword"),
   path('get-dashboard-url/',views.GetUserDashboardUrl.as_view(),name="getdashboardurl"),
   path('forgotpassword/',views.ForgotPassword.as_view(),name="forgotpassword"),
   path('forgotpasswordotp/',views.ForgotPasswordVerifyOTP.as_view(),name="forgotpasswordotp"),
   path('resendotp/',views.ResendOtp.as_view(),name="resendotp"),
   # Post-login: enforce institute-student mobile verification
   path('send-mobile-otp/', views.SendMobileOtp.as_view(), name='send_mobile_otp'),
   path('verify-mobile-otp/', views.VerifyMobileOtp.as_view(), name='verify_mobile_otp'),

   # Student: link parent accounts
   path('send-parent-otp/', views.SendParentOtp.as_view(), name='send_parent_otp'),
   path('verify-parent-otp/', views.VerifyParentOtp.as_view(), name='verify_parent_otp'),
   path('link-parent-mobile/', views.LinkParentMobile.as_view(), name='link_parent_mobile'),
   path('dashboard/',views.UserDashboard.as_view(),name="userdashboard"),
   path('user-feeds/',views.UserFeeds.as_view(),name="userfeeds"),
   path('logout/',views.logout,name="logout"),
   path('welcome/',views.Welcomepage.as_view(),name="welcome"),  
   path('scrapbook/',views.Scrapbook.as_view(),name="scrapbook"),
   path('my-notepad/',views.MyNotePad.as_view(),name="mynotepad"),
   path('create-note/',views.CreateNote.as_view(),name="createnote"),
   path('create-note/<int:id>/',views.CreateNote.as_view(),name="updatenote"),
   path('my-hobbies/',views.UserHobbies.as_view(),name="myhobbies"),
   path('career-interests/',views.CareerInterests.as_view(),name="careerinterest"),
   path('save-media/',views.SaveMedia.as_view(),name="savemedia"),
   path('resume-builder/create/', views.ResumeHubCreateView.as_view(), name="resumebuilder_create"),
   path('resume-builder/delete/', views.ResumeHubDeleteView.as_view(), name="resumebuilder_delete"),
   path(
       "resume-builder/duplicate/",
       views.ResumeHubDuplicateView.as_view(),
       name="resumebuilder_duplicate",
   ),
   path('resume-builder/generate/', views.ResumeGuidedGenerateView.as_view(), name="resume_guided_generate"),
   path(
       'resume-builder/studio/<int:resume_id>/',
       views.ResumeStudioSetupView.as_view(),
       name="resumebuilder_studio",
   ),
   path(
       'resume-builder/studio/<int:resume_id>/templates/',
       views.ResumeTemplateLibraryView.as_view(),
       name="resumebuilder_templates",
   ),
   path(
       "resume-builder/studio/<int:resume_id>/templates/embed/",
       views.ResumeTemplateStudioEmbedView.as_view(),
       name="resumebuilder_templates_embed",
   ),
   path(
       "resume-builder/studio/<int:resume_id>/photo/",
       views.ResumeStudioPhotoUploadView.as_view(),
       name="resumebuilder_studio_photo_upload",
   ),
   path("resume-preview/", views.resume_html_preview, name="resume_html_preview"),
   path(
       "admin/resume-studio-html-template/<int:template_pk>/preview/",
       views.admin_resume_studio_html_template_preview,
       name="admin_resume_studio_html_template_preview",
   ),
   path(
       'resume-builder/preview/<int:resume_id>/',
       views.ResumeGeneratedPreviewView.as_view(),
       name="resumebuilder_preview",
   ),
   path(
       'resume-builder/edit/<int:resume_id>/',
       views.ResumeBuilderEditView.as_view(),
       name="resumebuilder_edit",
   ),
   path(
       'resume-builder/edit/',
       RedirectView.as_view(permanent=False, pattern_name='users:resumebuilder'),
       name="resumebuilder_edit_legacy",
   ),
   path('resume-builder/', RedirectView.as_view(permanent=False, pattern_name='users:resume_v2_dashboard'), name="resumebuilder"),
   path('resume-builder/classic/', views.MyResumesHubView.as_view(), name="resumebuilder_classic"),
   # Resume Builder V2 (primary)
   path('resume-builder/v2/', ResumeV2DashboardView.as_view(), name="resume_v2_dashboard"),
   path('resume-builder/v2/create/', ResumeV2CreateView.as_view(), name="resume_v2_create"),
   path('resume-builder/v2/<int:resume_id>/delete/', ResumeV2DeleteView.as_view(), name="resume_v2_delete"),
   path('resume-builder/v2/<int:resume_id>/goal/', ResumeV2GoalView.as_view(), name="resume_v2_goal"),
   path('resume-builder/v2/<int:resume_id>/templates/', ResumeV2TemplatesView.as_view(), name="resume_v2_templates"),
   path('resume-builder/v2/<int:resume_id>/studio/', ResumeV2StudioView.as_view(), name="resume_v2_studio"),
   path('resume-builder/v2/<int:resume_id>/autofill/', ResumeV2AutofillView.as_view(), name="resume_v2_autofill"),
   path('resume-builder/v2/<int:resume_id>/ai/', ResumeV2AIView.as_view(), name="resume_v2_ai"),
   path('resume-builder/v2/<int:resume_id>/ai-review/', ResumeV2AIReviewView.as_view(), name="resume_v2_ai_review"),
   path('resume-builder/v2/<int:resume_id>/analytics/', ResumeV2AnalyticsPartialView.as_view(), name="resume_v2_analytics"),
   path(
       'resume-builder/setup/',
       RedirectView.as_view(permanent=False, pattern_name='users:resumebuilder'),
       name="resumebuilder_setup",
   ),
   path(
       'resume-builder-welcome/',
       RedirectView.as_view(permanent=False, pattern_name='users:resumebuilder'),
       name="resumebuilderwelcome",
   ),
   path('folders/',views.UserFolders.as_view(),name="userfolders"),
   path('folder/<int:id>/',views.UserFolderDetail.as_view(),name="userfolder"),
   path("resume-pdf/",views.resume_pdf_download,name="resumepdf"),
   path("calender/",views.UserCalenderView.as_view(),name="usercalender"),
   path("event-delete/<int:id>/",views.UserEventDeleteView,name="eventdelete"),
   path("user-colleges/",views.UserColleges.as_view(),name="mycolleges"),
   path("user-history/",views.UserHistoryView.as_view(),name="userhistory"),
   path("invoice/<int:invoice_id>/download/",views.invoice_download,name="invoice_download"),
   path('bookmark/',views.Bookmark.as_view(),name="bookmark"),
   path('bookmarkvideo/',views.BookmarkVideo.as_view(),name="bookmarkvideo"),
   path('bookmarkexam/',views.BookmarkExam.as_view(),name="bookmarkexam"),
   path('bookmarkcollege/',views.BookmarkCollege.as_view(),name="bookmarkcollege"),
   path('bookmarkblog/',views.BookmarkBlog.as_view(),name="bookmarkblog"),
   path('refer/',views.ReferView.as_view(),name="refer"),


   # manish
   path('create-institute/', views.create_institute, name='create_institute'),
   
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
