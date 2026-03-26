from django.urls import path
from . import views

urlpatterns = [
    path("shortlistcareer",views.ShortlistCourseAPI.as_view(),name="shortlistcareer"),
    path("shortlistcollege",views.ShortlistCollegeAPI.as_view(),name="shortlistcollege"),
    path("shortlistexam",views.ShortlistExamAPI.as_view(),name="shortlistexam"),
    path("user-note-save",views.UserNoteSave.as_view(),name="usernotesave"),
    path("user-note-delete",views.UserNoteDelete.as_view(),name="usernotedelete"),
    path("remove-hobbie",views.DeleteUserHobbie.as_view(),name="deletehobbie"),
    path("resume-about",views.UserResumeAbout.as_view(),name="resumeabout"),
    path("resume-skill",views.UserResumeSkillAdd.as_view(),name="resumeskill"),
    path("resume-certificate",views.UserResumeCertificationAdd.as_view(),name="resumecertificate"),
    path("resume-internship",views.UserResumeInternshipAdd.as_view(),name="resumeinternship"),
    path("resume-activity",views.UserResumeActivitiesAdd.as_view(),name="resumeactivity"),
    path("resume-volunteer",views.UserResumeVolunteering.as_view(),name="resumevolunteer"),
    path("resume-mail-send",views.UserResumeMailSend.as_view(),name="resumemailsend"),
    path("create-folder",views.CreateUserFolder.as_view(),name="createfolder"), 
    path("create-file",views.CreateUserFolderFile.as_view(),name="createfolderfile"),  
    path("skilllab-course-payment",views.CreateSkillabCoursePayment.as_view(),name="createskilllabcoursepayment"), 
    path("skilllab-course-update-payment",views.UpdateSkilllabCoursePayment.as_view(),name="updateskilllabcoursepayment"),     
]
