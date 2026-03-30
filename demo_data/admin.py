from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from core.choices import UserType
from .models import DemoDatasetConfig, DemoCounselorCourseState, ResultType
from .demo_dataset import (
    create_demo_dataset,
    remove_demo_counselor_data,
    remove_demo_data,
    reset_demo_counselor_data,
    reset_demo_data,
    setup_demo_counselor_data,
)

User = get_user_model()


@admin.register(DemoDatasetConfig)
class DemoDatasetConfigAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "num_students_class_10",
        "num_students_class_12",
        "num_students_with_psychometric",
        "psychometric_tests_complete",
        "demo_counselor_course_state",
        "result_type_class_10",
        "result_type_class_12",
        "student_count",
        "institute_id",
        "counselor_id",
        "updated_at",
    ]
    list_editable = [
        "num_students_class_10",
        "num_students_class_12",
        "num_students_with_psychometric",
        "psychometric_tests_complete",
        "result_type_class_10",
        "result_type_class_12",
    ]
    readonly_fields = [
        "institute_id",
        "institute_user_id",
        "parent_user_id",
        "student_user_ids",
        "counselor_user_id",
        "counselor_id",
        "updated_at",
    ]
    fieldsets = (
        (
            "Demo data configuration",
            {
                "fields": (
                    "num_students_class_10",
                    "num_students_class_12",
                    "num_students_with_psychometric",
                    "psychometric_tests_complete",
                    "result_type_class_10",
                    "result_type_class_12",
                ),
                "description": "Class 10/12 counts; psychometric counts; result types. Student/demo institute data only. Use the separate Demo counselor section below for counselor course demo.",
            },
        ),
        (
            "Last run output (read-only)",
            {
                "fields": (
                    "institute_id",
                    "institute_user_id",
                    "parent_user_id",
                    "student_user_ids",
                    "counselor_user_id",
                    "counselor_id",
                    "updated_at",
                ),
            },
        ),
    )
    change_list_template = "admin/demo_data/demodatasetconfig/change_list.html"

    def get_queryset(self, request):
        return super().get_queryset(request)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        config = DemoDatasetConfig.get_singleton()
        n10 = config.num_students_class_10
        n12 = config.num_students_class_12
        n10_psych = min(getattr(config, "num_psychometric_class_10", 0), n10)
        n12_psych = min(getattr(config, "num_psychometric_class_12", 0), n12)
        result_labels = dict(ResultType.CHOICES)
        extra_context["config"] = config
        extra_context["result_type_choices"] = ResultType.CHOICES
        counselor_state_labels = dict(DemoCounselorCourseState.CHOICES)
        extra_context["config_table"] = [
            {"user": "Class 10", "total_students": n10, "psych_completed": n10_psych, "result_type_value": config.result_type_class_10, "result_type_label": result_labels.get(config.result_type_class_10, config.result_type_class_10), "editable": True},
            {"user": "Class 12", "total_students": n12, "psych_completed": n12_psych, "result_type_value": config.result_type_class_12, "result_type_label": result_labels.get(config.result_type_class_12, config.result_type_class_12), "editable": True},
            {"user": "Parent", "total_students": 1, "psych_completed": None, "result_type_value": "", "result_type_label": "—", "editable": False},
            {"user": "Institute", "total_students": 1, "psych_completed": None, "result_type_value": "", "result_type_label": "—", "editable": False},
        ]
        extra_context["demo_counselor_course_state"] = getattr(config, "demo_counselor_course_state", DemoCounselorCourseState.PASSED)
        extra_context["demo_counselor_state_choices"] = DemoCounselorCourseState.CHOICES
        extra_context["demo_counselor_state_label"] = counselor_state_labels.get(
            getattr(config, "demo_counselor_course_state", DemoCounselorCourseState.PASSED), "—"
        )
        demo_users = []
        ids = []
        if config.institute_user_id:
            ids.append(config.institute_user_id)
        if config.parent_user_id:
            ids.append(config.parent_user_id)
        if config.student_user_ids:
            ids.extend(config.student_user_ids)
        if ids:
            type_order = {
                UserType.INSTITUTE: 0,
                UserType.PARENT: 1,
                UserType.STUDENT: 2,
                UserType.COUNSELOR: 3,
            }
            role_labels = dict(UserType.CHOICES)
            for u in User.objects.filter(id__in=ids):
                demo_users.append({
                    "id": u.id,
                    "name": u.name or "",
                    "email": u.email or "",
                    "role": role_labels.get(u.user_type, str(u.user_type)),
                    "user_type": u.user_type,
                })
            demo_users.sort(key=lambda x: (type_order.get(x["user_type"], 99), x["id"]))
        extra_context["demo_users"] = demo_users
        demo_counselor_user = None
        cid = getattr(config, "counselor_user_id", None)
        if cid:
            demo_counselor_user = User.objects.filter(id=cid).first()
        extra_context["demo_counselor_user"] = demo_counselor_user
        return super().changelist_view(request, extra_context)

    def student_count(self, obj):
        if obj and obj.student_user_ids:
            return len(obj.student_user_ids)
        return 0

    student_count.short_description = "Students (last run)"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "save/",
                self.admin_site.admin_view(self.config_save_view),
                name="demo_data_config_save",
            ),
            path(
                "setup/",
                self.admin_site.admin_view(self.setup_demo_data_view),
                name="demo_data_setup",
            ),
            path(
                "reset/",
                self.admin_site.admin_view(self.reset_demo_data_view),
                name="demo_data_reset",
            ),
            path(
                "remove/",
                self.admin_site.admin_view(self.remove_demo_data_view),
                name="demo_data_remove",
            ),
            path(
                "counselor_config_save/",
                self.admin_site.admin_view(self.counselor_config_save_view),
                name="demo_data_counselor_config_save",
            ),
            path(
                "setup_counselor/",
                self.admin_site.admin_view(self.setup_demo_counselor_view),
                name="demo_data_setup_counselor",
            ),
            path(
                "reset_counselor/",
                self.admin_site.admin_view(self.reset_demo_counselor_view),
                name="demo_data_reset_counselor",
            ),
            path(
                "remove_counselor/",
                self.admin_site.admin_view(self.remove_demo_counselor_view),
                name="demo_data_remove_counselor",
            ),
        ]
        return custom + urls

    def config_save_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        config = DemoDatasetConfig.get_singleton()
        try:
            def _int(val, default):
                if val is None or val == "":
                    return default
                return int(val)

            n10 = _int(request.POST.get("num_students_class_10"), config.num_students_class_10)
            n12 = _int(request.POST.get("num_students_class_12"), config.num_students_class_12)
            p10 = _int(request.POST.get("num_psychometric_class_10"), getattr(config, "num_psychometric_class_10", 1))
            p12 = _int(request.POST.get("num_psychometric_class_12"), getattr(config, "num_psychometric_class_12", 2))
            r10 = request.POST.get("result_type_class_10") or config.result_type_class_10
            r12 = request.POST.get("result_type_class_12") or config.result_type_class_12
            if n10 + n12 == 0:
                messages.error(request, "At least one of Class 10 or Class 12 count must be > 0.")
                return redirect("admin:demo_data_demodatasetconfig_changelist")
            if p10 > n10:
                messages.error(request, "Psychometric completed (Class 10) cannot exceed total students (Class 10).")
                return redirect("admin:demo_data_demodatasetconfig_changelist")
            if p12 > n12:
                messages.error(request, "Psychometric completed (Class 12) cannot exceed total students (Class 12).")
                return redirect("admin:demo_data_demodatasetconfig_changelist")
            config.num_students_class_10 = n10
            config.num_students_class_12 = n12
            config.num_psychometric_class_10 = p10
            config.num_psychometric_class_12 = p12
            config.result_type_class_10 = r10
            config.result_type_class_12 = r12
            config.num_students_with_psychometric = p10 + p12
            config.save(update_fields=[
                "num_students_class_10", "num_students_class_12",
                "num_psychometric_class_10", "num_psychometric_class_12",
                "result_type_class_10", "result_type_class_12",
                "num_students_with_psychometric",
            ])
            messages.success(request, "Student demo configuration saved.")
        except ValueError as e:
            messages.error(request, f"Invalid number: {e}")
        except Exception as e:
            messages.error(request, f"Could not save: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def counselor_config_save_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        config = DemoDatasetConfig.get_singleton()
        try:
            dc_state = request.POST.get("demo_counselor_course_state") or getattr(
                config, "demo_counselor_course_state", DemoCounselorCourseState.PASSED
            )
            valid_states = {c[0] for c in DemoCounselorCourseState.CHOICES}
            if dc_state in valid_states:
                config.demo_counselor_course_state = dc_state
                config.save(update_fields=["demo_counselor_course_state"])
            messages.success(request, "Demo counselor options saved.")
        except Exception as e:
            messages.error(request, f"Could not save: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def setup_demo_counselor_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        try:
            setup_demo_counselor_data()
            messages.success(
                request,
                "Demo counselor created (demo_counselor@topteen.demo / demo123). Separate from student demo data.",
            )
        except Exception as e:
            messages.error(request, f"Demo counselor setup failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def reset_demo_counselor_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        confirm = request.GET.get("confirm") == "1"
        if not confirm:
            messages.warning(
                request,
                "Add ?confirm=1 to confirm reset demo counselor only (student demo data is not touched).",
            )
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        try:
            reset_demo_counselor_data()
            messages.success(request, "Demo counselor reset complete.")
        except Exception as e:
            messages.error(request, f"Reset failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def remove_demo_counselor_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        confirm = request.GET.get("confirm") == "1"
        if not confirm:
            messages.warning(
                request,
                "Add ?confirm=1 to confirm remove demo counselor only (student demo data is not touched).",
            )
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        try:
            remove_demo_counselor_data()
            messages.success(request, "Demo counselor removed.")
        except Exception as e:
            messages.error(request, f"Remove failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def setup_demo_data_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        try:
            create_demo_dataset()
            messages.success(
                request,
                "Student / institute demo dataset created. Demo counselor is unchanged — use Setup demo counselor separately.",
            )
        except Exception as e:
            messages.error(request, f"Setup failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def reset_demo_data_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        confirm = request.GET.get("confirm") == "1"
        if not confirm:
            messages.warning(
                request,
                "Add ?confirm=1 to the URL to confirm reset. Only system-generated demo data will be deleted and recreated.",
            )
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        try:
            reset_demo_data()
            messages.success(
                request,
                "Student / institute demo reset complete. Demo counselor was not modified — use Reset demo counselor if needed.",
            )
        except Exception as e:
            messages.error(request, f"Reset failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def remove_demo_data_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        confirm = request.GET.get("confirm") == "1"
        if not confirm:
            messages.warning(
                request,
                "Add ?confirm=1 to the URL to confirm remove. Only system-generated demo data will be deleted (not recreated).",
            )
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        try:
            remove_demo_data()
            messages.success(
                request,
                "Student / institute demo removed. Demo counselor account was not removed — use Remove demo counselor if needed.",
            )
        except Exception as e:
            messages.error(request, f"Remove failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")
