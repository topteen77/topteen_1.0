from django.urls import path,include
from . import views

app_name="institute"

urlpatterns = [
    path("admindashboard",views.AdminDashboardView.as_view(),name="admindashboard"),
    path("create_class",views.CreateClassSectionView.as_view(),name="createclass"),
    path("student_data",views.StudentData.as_view(),name="studentdata"),
    path("institute_data",views.InstituteData.as_view(),name="institutedata"),
    path("create_institute",views.InstituteCreateView.as_view(),name="createinstitute"),

    #manish

    path("create_counselor/<slug:slug>",views.CounselorCreateView.as_view(),name="createcounselor"),
    path("counselor_changepassword/",views.CounselorChangePasswordView.as_view(),name="counselorchangepassword"),

    path("marketing_group_dashboard",views.MarketingGroupDashboardView.as_view(),name="marketinggroupdashboard"),
    path("marketing_profile_edit",views.InstituteMarketingProfileEditView.as_view(),name="marketingprofileedit"),
    path("institute_approve/<int:id>", views.InstituteApproveView.as_view(), name="instituteapprove"),
    
    # path("create_counselor_dashboard",views.CounselorDashboard,name="CounselorDashboardView"),
    # path("create_Counselor_Course",views.CounselorCourse,name="CounselorCourse"),

    path("create_institute_group",views.InstituteGroupCreateView.as_view(),name="createinstitutegroup"),
    path("institute_group_dashboard",views.InstituteGroupDashboardView.as_view(),name="institutegroupdashboard"),
    path("institute_profile_edit",views.InstituteProfileEditView.as_view(),name="instituteprofileedit"),
    path("institute_student_create",views.InstituteStudentCreateView.as_view(),name="institutestudentcreate"),
    path("institute_csv_student_create",views.InstituteCsvStudentCreateView.as_view(),name="institutecsvstudentcreate"),
    path("institute_post_matric_csv_student_create",views.InstitutePostMatricCsvStudentCreateView.as_view(),name="institutepostmatriccsvstudentcreate"),
    path("institute_student_update/",views.InstituteStudentUpdateView.as_view(),name="institutestudentupdate"),
    path("institute_student_change_password/",views.InstituteStudentChangePasswordView.as_view(),name="institutestudentchangepassword"),
    path("institute_change_password/",views.InstituteChangePasswordView.as_view(),name="institutechangepassword"),
    path("institute_deletion_request",views.InstituteDeletionView.as_view(),name="institutedeletion"),
    path("institute_history_log/<slug:slug>",views.InstituteHistoryLogView.as_view(),name="institutehistorylog"),
    path("institute_student_delete/",views.InstituteStudentDeleteView.as_view(),name="institutestudentdelete"),
    path("institute_block/<int:id>",views.InstituteBlockView.as_view(),name="instituteblock"),
    path("institute_student_block/<int:id>",views.InstituteStudentBlockView.as_view(),name="institutestudentblock"),
    path("download_student_sample_csv",views.students_csv_sample_file,name="download_student_sample_csv"),
    path("p0ost_matric_student_sample_data",views.post_matric_student_sample_data,name="post_matric_student_sample_csv"),
    path("<slug:slug>",views.InstituteDashboardView.as_view(),name="institutedashboard"),
]