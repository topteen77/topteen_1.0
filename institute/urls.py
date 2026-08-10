from django.urls import path, include
from . import views
from . import tieup_views
from users.views import DemoLoginView

app_name = "institute"

urlpatterns = [
    path("admindashboard/",views.AdminDashboardView.as_view(),name="admindashboard"),
    path("create_class/",views.CreateClassSectionView.as_view(),name="createclass"),
    path("student_data/",views.StudentData.as_view(),name="studentdata"),
    path("institute_data/",views.InstituteData.as_view(),name="institutedata"),
    path("create_institute/",views.InstituteCreateView.as_view(),name="createinstitute"),
    path(
        "seed_institute_demo_students/",
        views.InstituteSeedDemoStudentsView.as_view(),
        name="seedinstitutedemostudents",
    ),
    path(
        "convert_demo_institute/",
        views.InstituteConvertDemoToPaidView.as_view(),
        name="convertdemoinstitute",
    ),

    #manish

    path("create_counselor/<slug:slug>/",views.CounselorCreateView.as_view(),name="createcounselor"),
    path("counselor_changepassword/",views.CounselorChangePasswordView.as_view(),name="counselorchangepassword"),

    path("marketing_group_dashboard/",views.MarketingGroupDashboardView.as_view(),name="marketinggroupdashboard"),
    path("marketing_group_dashboard/<str:page>/", views.MarketingGroupDashboardView.as_view(), name="marketinggroupdashboard_page"),
    path("marketing_group_heatmap/", views.MarketingGroupHeatmapView.as_view(), name="marketinggroupheatmap"),
    path("institute_group_heatmap/", views.InstituteGroupHeatmapView.as_view(), name="institutegroupheatmap"),
    path("marketing_profile_edit/",views.InstituteMarketingProfileEditView.as_view(),name="marketingprofileedit"),
    path("update_seat_capacity/",views.UpdateSeatCapacityView.as_view(),name="updateseatcapacity"),
    path("institute_approve/<int:id>/", views.InstituteApproveView.as_view(), name="instituteapprove"),
    path(
        "institute_approve_billing/<int:id>/",
        tieup_views.InstituteApproveWithBillingView.as_view(),
        name="instituteapprovebilling",
    ),
    path(
        "marketing_tieup_mark_received/",
        tieup_views.MarketingTieUpMarkReceivedView.as_view(),
        name="marketing_tieup_mark_received",
    ),
    path(
        "marketing_tieup_coupon_create/",
        tieup_views.MarketingTieUpCouponCreateView.as_view(),
        name="marketing_tieup_coupon_create",
    ),
    path(
        "<slug:slug>/tieup-pay/",
        tieup_views.InstituteTieUpPayView.as_view(),
        name="institute_tieup_pay",
    ),
    path(
        "<slug:slug>/tieup-create-order/",
        tieup_views.institute_tieup_create_order,
        name="institute_tieup_create_order",
    ),
    path(
        "<slug:slug>/tieup-coupon-preview/",
        tieup_views.institute_tieup_coupon_preview,
        name="institute_tieup_coupon_preview",
    ),
    path(
        "<slug:slug>/tieup-list-coupons/",
        tieup_views.institute_tieup_list_coupons,
        name="institute_tieup_list_coupons",
    ),
    path(
        "tieup-payment-verify/",
        tieup_views.institute_tieup_payment_verify,
        name="institute_tieup_payment_verify",
    ),
    path(
        "tieup-invoice/<int:invoice_id>/download/",
        tieup_views.institute_tieup_invoice_download,
        name="institute_tieup_invoice_download",
    ),
    path(
        "tieup-payment-success/<path:enc_id>/",
        tieup_views.InstituteTieUpPaymentSuccessView.as_view(),
        name="institute_tieup_payment_success",
    ),
    path(
        "tieup-payment-fail/<path:enc_id>/",
        tieup_views.InstituteTieUpPaymentFailView.as_view(),
        name="institute_tieup_payment_fail",
    ),
    path("institute_reject/<int:id>/", views.InstituteRejectView.as_view(), name="institutereject"),
    path(
        "institute_hard_delete/<int:id>/",
        views.InstituteHardDeleteView.as_view(),
        name="instituteharddelete",
    ),
    
    # path("create_counselor_dashboard",views.CounselorDashboard,name="CounselorDashboardView"),
    # path("create_Counselor_Course",views.CounselorCourse,name="CounselorCourse"),

    path("create_institute_group/",views.InstituteGroupCreateView.as_view(),name="createinstitutegroup"),
    path("institute_group_dashboard/",views.InstituteGroupDashboardView.as_view(),name="institutegroupdashboard"),
    path(
        "institute_group_dashboard/api/bulk-assign-counselor/",
        views.InstituteGroupBulkAssignCounselorView.as_view(),
        name="institutegroup_bulk_assign_counselor",
    ),
    path(
        "institute_group_dashboard/api/institute-counselor/",
        views.InstituteGroupInstituteCounselorView.as_view(),
        name="institutegroup_institute_counselor",
    ),
    path(
        "institute_group_dashboard/api/counselor-profile/",
        views.InstituteGroupCounselorProfileUpdateView.as_view(),
        name="institutegroup_counselor_profile_update",
    ),
    path("institute_group_dashboard/<str:page>/", views.InstituteGroupDashboardView.as_view(), name="institutegroupdashboard_page"),
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
    path("api/tieup-pay-status/", tieup_views.tieup_pay_status_api, name="tieup_pay_status_api"),
    path("api/heatmap-data/", views.get_heatmap_data_api, name="heatmap_data_api"),
    path("api/marketing_search_suggest/", views.marketing_search_suggest, name="marketing_search_suggest"),
    path("api/institute_group_search_suggest/", views.institute_group_search_suggest, name="institute_group_search_suggest"),
    path("api/admin_institute_search_suggest/", views.admin_institute_search_suggest, name="admin_institute_search_suggest"),
    # old code not in use - start
    # New isolated routes for institute authentication frontend
    # old code not in use - end
    path("auth/register/", views.InstituteRegisterView.as_view(), name="register"),
    path("auth/login/", views.InstituteLoginView.as_view(), name="login"),
    path("auth/demo-login/", DemoLoginView.as_view(), name="demo_login"),
    # v2 heatmap is now a normal dashboard page: /institute/<slug>/heatmap/ (handled by institutedashboard_page)
    # Keep legacy view at a non-conflicting URL for backwards compatibility.
    path("<slug:slug>/heatmap-legacy/", views.InstituteHeatmapView.as_view(), name="instituteheatmap_legacy"),
    # Assign institute student to counselor (AJAX)
    path("<slug:slug>/assign-counselor/", views.AssignStudentToCounselorView.as_view(), name="assign_student_counselor"),
    path("<slug:slug>/assign-package/", views.AssignStudentPackageView.as_view(), name="assign_student_package"),
    # Change/unassign counselor for a student (AJAX)
    path("<slug:slug>/set-counselor/", views.SetStudentCounselorView.as_view(), name="set_student_counselor"),
    path("<slug:slug>/api/student_name_suggest/", views.institute_student_name_suggest, name="institute_student_name_suggest"),
    # Backwards-compatible name used across templates/APIs
    path("<slug:slug>/dashboard/", views.InstituteDashboardView.as_view(), name="institute_masterdashboard"),
    path("<slug:slug>/<str:page>/", views.InstituteDashboardView.as_view(), name="institutedashboard_page"),
    path("<slug:slug>/",views.InstituteDashboardView.as_view(),name="institutedashboard"),
]