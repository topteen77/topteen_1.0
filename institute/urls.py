from django.urls import path, include
from . import views
from users.views import DemoLoginView

app_name = "institute"

urlpatterns = [
    path("admindashboard/",views.AdminDashboardView.as_view(),name="admindashboard"),
    path("create_class/",views.CreateClassSectionView.as_view(),name="createclass"),
    path("student_data/",views.StudentData.as_view(),name="studentdata"),
    path("institute_data/",views.InstituteData.as_view(),name="institutedata"),
    path("create_institute/",views.InstituteCreateView.as_view(),name="createinstitute"),

    #manish

    path("create_counselor/<slug:slug>/",views.CounselorCreateView.as_view(),name="createcounselor"),
    path("counselor_changepassword/",views.CounselorChangePasswordView.as_view(),name="counselorchangepassword"),

    path("marketing_group_dashboard/",views.MarketingGroupDashboardView.as_view(),name="marketinggroupdashboard"),
    path("marketing_profile_edit/",views.InstituteMarketingProfileEditView.as_view(),name="marketingprofileedit"),
    path("update_seat_capacity/",views.UpdateSeatCapacityView.as_view(),name="updateseatcapacity"),
    path("institute_approve/<int:id>/", views.InstituteApproveView.as_view(), name="instituteapprove"),
    path(
        "institute_hard_delete/<int:id>/",
        views.InstituteHardDeleteView.as_view(),
        name="instituteharddelete",
    ),
    
    # path("create_counselor_dashboard",views.CounselorDashboard,name="CounselorDashboardView"),
    # path("create_Counselor_Course",views.CounselorCourse,name="CounselorCourse"),

    path("create_institute_group/",views.InstituteGroupCreateView.as_view(),name="createinstitutegroup"),
    path("institute_group_dashboard/",views.InstituteGroupDashboardView.as_view(),name="institutegroupdashboard"),
    path("institute_profile_edit/",views.InstituteProfileEditView.as_view(),name="instituteprofileedit"),
    path("institute_student_create/",views.InstituteStudentCreateView.as_view(),name="institutestudentcreate"),
    path("institute_csv_student_create/",views.InstituteCsvStudentCreateView.as_view(),name="institutecsvstudentcreate"),
    path("institute_post_matric_csv_student_create/",views.InstitutePostMatricCsvStudentCreateView.as_view(),name="institutepostmatriccsvstudentcreate"),
    path("institute_student_update/",views.InstituteStudentUpdateView.as_view(),name="institutestudentupdate"),
    path("institute_student_change_password/",views.InstituteStudentChangePasswordView.as_view(),name="institutestudentchangepassword"),
    path("institute_change_password/",views.InstituteChangePasswordView.as_view(),name="institutechangepassword"),
    path("institute_deletion_request/",views.InstituteDeletionView.as_view(),name="institutedeletion"),
    path("institute_history_log/<slug:slug>/",views.InstituteHistoryLogView.as_view(),name="institutehistorylog"),
    path("institute_student_delete/",views.InstituteStudentDeleteView.as_view(),name="institutestudentdelete"),
    path("institute_block/<int:id>/",views.InstituteBlockView.as_view(),name="instituteblock"),
    path("institute_student_block/<int:id>/",views.InstituteStudentBlockView.as_view(),name="institutestudentblock"),
    # old code not in use - start
    # Marketing user management routes
    # old code not in use - end
    path("marketing_block/<int:id>/",views.MarketingBlockView.as_view(),name="marketingblock"),
    path("download_student_sample_csv/",views.students_csv_sample_file,name="download_student_sample_csv"),
    path("p0ost_matric_student_sample_data/",views.post_matric_student_sample_data,name="post_matric_student_sample_csv"),
    # Must be before <slug:slug>/ so the API is never mistaken for an institute slug
    path("api/heatmap-data/", views.get_heatmap_data_api, name="heatmap_data_api"),
    # old code not in use - start
    # New isolated routes for institute authentication frontend
    # old code not in use - end
    path("auth/register/", views.InstituteRegisterView.as_view(), name="register"),
    path("auth/login/", views.InstituteLoginView.as_view(), name="login"),
    path("auth/demo-login/", DemoLoginView.as_view(), name="demo_login"),
    path(
        "<slug:slug>/dashboard/",
        views.InstituteMasterDashboardView.as_view(),
        name="institute_masterdashboard",
    ),
    path("<slug:slug>/", views.InstituteDashboardView.as_view(), name="institutedashboard"),
]