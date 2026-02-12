from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from core.choices import UserType
from .models import DemoDatasetConfig, ResultType
from .demo_dataset import create_demo_dataset, reset_demo_data, remove_demo_data

User = get_user_model()


@admin.register(DemoDatasetConfig)
class DemoDatasetConfigAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "num_students_class_10",
        "num_students_class_12",
        "num_students_with_psychometric",
        "psychometric_tests_complete",
        "result_type_class_10",
        "result_type_class_12",
        "student_count",
        "institute_id",
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
                "description": "Class 10/12 counts; how many have psychometric (e.g. 1 Class 10 + 2 Class 12 = 3). Result type per class: Class 10 (e.g. varied = high/medium/low/mixed), Class 12 (e.g. high). 1 parent, 1 institute (fixed).",
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
        extra_context["config_table"] = [
            {"user": "Class 10", "total_students": n10, "psych_completed": n10_psych, "result_type_value": config.result_type_class_10, "result_type_label": result_labels.get(config.result_type_class_10, config.result_type_class_10), "editable": True},
            {"user": "Class 12", "total_students": n12, "psych_completed": n12_psych, "result_type_value": config.result_type_class_12, "result_type_label": result_labels.get(config.result_type_class_12, config.result_type_class_12), "editable": True},
            {"user": "Parent", "total_students": 1, "psych_completed": None, "result_type_value": "", "result_type_label": "—", "editable": False},
            {"user": "Institute", "total_students": 1, "psych_completed": None, "result_type_value": "", "result_type_label": "—", "editable": False},
        ]
        demo_users = []
        ids = []
        if config.institute_user_id:
            ids.append(config.institute_user_id)
        if config.parent_user_id:
            ids.append(config.parent_user_id)
        if config.student_user_ids:
            ids.extend(config.student_user_ids)
        if ids:
            type_order = {UserType.INSTITUTE: 0, UserType.PARENT: 1, UserType.STUDENT: 2}
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
            messages.success(request, "Configuration saved.")
        except ValueError as e:
            messages.error(request, f"Invalid number: {e}")
        except Exception as e:
            messages.error(request, f"Could not save: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def setup_demo_data_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        try:
            create_demo_dataset()
            messages.success(request, "Demo dataset created successfully. Only system-flagged data was created.")
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
                "Demo data reset complete. Only system-flagged data was removed and recreated; no actual user data was affected.",
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
                "Demo data removed. Only system-flagged data was deleted; no actual user data was affected.",
            )
        except Exception as e:
            messages.error(request, f"Remove failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")
