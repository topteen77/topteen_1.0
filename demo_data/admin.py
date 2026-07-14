from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from core.choices import UserType
from django.utils import timezone
from datetime import timedelta
import random
from .models import (
    DemoDatasetConfig,
    DemoCounselorCourseState,
    DemoJobAction,
    DemoJobStatus,
    ResultType,
)
from .demo_dataset import reseed_demo_student_psychometric
from .tasks import (
    remove_demo_counselor_task,
    remove_demo_dataset_task,
    reset_demo_counselor_task,
    reset_demo_dataset_task,
    setup_demo_counselor_task,
    setup_demo_dataset_task,
)
from notifications.services import get_celery_open_tasks, revoke_celery_task, revoke_celery_tasks

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
        "last_job_status",
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
        "last_job_status",
        "last_job_action",
        "last_job_task_id",
        "last_job_message",
        "last_job_started_at",
        "last_job_finished_at",
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
        (
            "Background job (Celery)",
            {
                "fields": (
                    "last_job_status",
                    "last_job_action",
                    "last_job_task_id",
                    "last_job_message",
                    "last_job_started_at",
                    "last_job_finished_at",
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
        extra_context["job_in_progress"] = config.job_in_progress()
        extra_context["last_job_status"] = config.last_job_status
        extra_context["last_job_status_label"] = dict(DemoJobStatus.CHOICES).get(
            config.last_job_status, config.last_job_status
        )
        extra_context["last_job_action_label"] = DemoJobAction.LABELS.get(
            config.last_job_action, config.last_job_action or "—"
        )
        extra_context["last_job_message"] = config.last_job_message
        extra_context["last_job_task_id"] = config.last_job_task_id
        extra_context["last_job_started_at"] = config.last_job_started_at
        extra_context["last_job_finished_at"] = config.last_job_finished_at

        celery_diag = get_celery_open_tasks()
        extra_context["celery_task_rows"] = celery_diag.get("task_rows") or []
        extra_context["celery_open_tasks"] = celery_diag.get("open_tasks") or 0
        extra_context["celery_inspect_ok"] = celery_diag.get("inspect_ok")
        extra_context["celery_inspect_error"] = celery_diag.get("inspect_error") or ""

        # Demo student dropdown (for dummy counseling/session data generation)
        demo_students = []
        try:
            from institute.models import StudentManagement

            sids = list(getattr(config, "student_user_ids", []) or [])
            if sids:
                for sm in (
                    StudentManagement.objects.filter(student_id__in=sids)
                    .select_related("student", "class_and_section")
                    .order_by("id")
                ):
                    demo_students.append(
                        {
                            "id": sm.id,
                            "name": (getattr(getattr(sm, "student", None), "name", None) or "").strip()
                            or f"Student {sm.id}",
                            "class": (getattr(getattr(sm, "class_and_section", None), "class_and_section", None) or "").strip(),
                        }
                    )
        except Exception:
            demo_students = []
        extra_context["demo_students"] = demo_students

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
                "reseed_student_psych/",
                self.admin_site.admin_view(self.reseed_student_psych_view),
                name="demo_data_reseed_student_psych",
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
            path(
                "generate_counseling/",
                self.admin_site.admin_view(self.generate_counseling_data_view),
                name="demo_data_generate_counseling",
            ),
            path(
                "reset_counseling/",
                self.admin_site.admin_view(self.reset_counseling_data_view),
                name="demo_data_reset_counseling",
            ),
            path(
                "generate_heatmap/",
                self.admin_site.admin_view(self.generate_heatmap_data_view),
                name="demo_data_generate_heatmap",
            ),
            path(
                "reset_heatmap/",
                self.admin_site.admin_view(self.reset_heatmap_data_view),
                name="demo_data_reset_heatmap",
            ),
            path(
                "clear_job/",
                self.admin_site.admin_view(self.clear_demo_job_view),
                name="demo_data_clear_job",
            ),
            path(
                "celery_revoke/",
                self.admin_site.admin_view(self.revoke_celery_task_view),
                name="demo_data_celery_revoke",
            ),
            path(
                "celery_revoke_all/",
                self.admin_site.admin_view(self.revoke_all_celery_tasks_view),
                name="demo_data_celery_revoke_all",
            ),
        ]
        return custom + urls

    def _maybe_mark_demo_job_cancelled(self, task_id, reason="Cancelled from admin."):
        """If the revoked id matches the tracked demo job, clear the in-progress marker."""
        config = DemoDatasetConfig.get_singleton()
        if not task_id or config.last_job_task_id != task_id:
            return
        if config.job_in_progress():
            config.mark_job_failed(reason)

    def revoke_celery_task_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        task_id = (request.POST.get("task_id") or "").strip()
        task_name = (request.POST.get("task_name") or "").strip()
        state = (request.POST.get("state") or "").strip().lower()
        terminate = state in ("", "active") or request.POST.get("terminate") == "1"
        result = revoke_celery_task(task_id, terminate=terminate)
        label = f"{task_name} ({task_id})" if task_name else task_id
        if result.get("ok"):
            self._maybe_mark_demo_job_cancelled(
                task_id, f"Cancelled from admin: {task_name or task_id}"
            )
            messages.success(
                request,
                f"Stopped Celery task {label}. "
                "Periodic beat jobs may be re-queued later.",
            )
        else:
            messages.error(
                request, result.get("message") or f"Failed to stop task {label}."
            )
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def revoke_all_celery_tasks_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        diag = get_celery_open_tasks()
        task_rows = diag.get("task_rows") or []
        task_ids = [t.get("id") for t in task_rows if t.get("id")]
        if not task_ids:
            messages.info(request, "No open Celery tasks to stop.")
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        summary = revoke_celery_tasks(task_ids, terminate=True)
        config = DemoDatasetConfig.get_singleton()
        if config.job_in_progress() and config.last_job_task_id in task_ids:
            config.mark_job_failed("Cancelled from admin (stop all open tasks).")
        if summary.get("ok_count"):
            messages.success(
                request,
                f"Stopped {summary['ok_count']} Celery task(s). "
                "Beat may re-queue periodic tasks on the next schedule tick.",
            )
        if summary.get("fail_count"):
            first_err = next(
                (r.get("message") for r in summary.get("results", []) if not r.get("ok")),
                "",
            )
            messages.warning(
                request,
                f"Could not stop {summary['fail_count']} task(s)."
                + (f" {first_err}" if first_err else ""),
            )
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def clear_demo_job_view(self, request):
        """Unlock a stuck queued/running status marker (does not revoke Celery)."""
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        config = DemoDatasetConfig.get_singleton()
        config.last_job_status = DemoJobStatus.IDLE
        config.last_job_message = "Job status cleared manually."
        config.last_job_finished_at = timezone.now()
        config.save(
            update_fields=[
                "last_job_status",
                "last_job_message",
                "last_job_finished_at",
                "updated_at",
            ]
        )
        messages.info(request, "Background job status cleared. You can queue a new demo job.")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def _enqueue_demo_job(self, request, action, celery_task, queued_message):
        """Queue a long demo job on Celery; refuse if another job is already running."""
        config = DemoDatasetConfig.get_singleton()
        if config.job_in_progress():
            messages.warning(
                request,
                f"A demo job is already {config.last_job_status} "
                f"({DemoJobAction.LABELS.get(config.last_job_action, config.last_job_action)}). "
                "Wait for it to finish (refresh this page), then try again.",
            )
            return redirect("admin:demo_data_demodatasetconfig_changelist")
        try:
            async_result = celery_task.delay()
            config.mark_job_queued(action, async_result.id, queued_message)
            messages.success(
                request,
                f"{queued_message} Task id: {async_result.id}. "
                "Refresh this page to see progress (Celery worker must be running).",
            )
        except Exception as e:
            config.mark_job_failed(f"Could not queue job: {e}")
            messages.error(
                request,
                f"Could not queue Celery job: {e}. "
                "Check Redis / celery worker is up.",
            )
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def generate_counseling_data_view(self, request):
        """
        Admin utility: Create dummy FollowUpStatus rows for the demo counselor against selected demo students.
        Used to test counselor dashboard/session report/students follow-ups quickly.
        """
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        config = DemoDatasetConfig.get_singleton()
        counselor_id = getattr(config, "counselor_id", None)
        if not counselor_id:
            messages.error(request, "Demo counselor not set up. Run 'Setup demo counselor' first.")
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        # Inputs
        level = (request.POST.get("counseling_level") or "medium").strip().lower()
        student_ids = request.POST.getlist("demo_student_ids") or []
        if not student_ids:
            one = (request.POST.get("demo_student_id") or "").strip()
            if one:
                student_ids = [one]
        try:
            student_ids = [int(x) for x in student_ids if str(x).strip().isdigit()]
        except Exception:
            student_ids = []
        if not student_ids:
            messages.error(request, "Select at least one demo student.")
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        # Intensity presets
        presets = {
            "light": {"count": 3, "span_days": 10},
            "medium": {"count": 8, "span_days": 28},
            "heavy": {"count": 16, "span_days": 56},
        }
        p = presets.get(level, presets["medium"])
        n = int(p["count"])
        span = int(p["span_days"])

        try:
            from counselor.models import FollowUpStatus, Counselor
            from institute.models import StudentManagement

            counselor = Counselor.objects.filter(id=int(counselor_id)).first()
            if not counselor:
                messages.error(request, "Demo counselor profile missing. Re-run 'Setup demo counselor'.")
                return redirect("admin:demo_data_demodatasetconfig_changelist")

            students = list(StudentManagement.objects.filter(id__in=student_ids))
            if not students:
                messages.error(request, "No matching demo students found.")
                return redirect("admin:demo_data_demodatasetconfig_changelist")

            # Ensure selected demo students are assigned to the demo counselor so counselor dashboards show them.
            try:
                counselor.students.add(*students)
            except Exception:
                try:
                    for sm in students:
                        counselor.students.add(sm)
                except Exception:
                    pass

            today = timezone.localdate()
            modes = ["call", "meeting", "email"]
            statuses = ["completed", "pending", "follow-up"]
            notes = [
                "Career exploration & clarity gap reduction",
                "Roadmap planning & milestone setting",
                "Parent counseling touchpoint",
                "Interest vs knowledge alignment discussion",
                "Action plan shared + resources sent",
            ]

            created_total = 0
            for sm in students:
                for i in range(n):
                    # Spread across past `span` days; keep more density in the latest week
                    back = int(round((span * i) / max(1, n - 1)))
                    d = today - timedelta(days=back)
                    st = statuses[i % len(statuses)]
                    md = modes[(i + 1) % len(modes)]
                    msg = notes[i % len(notes)]
                    nxt = None
                    if st != "completed":
                        nxt = min(today + timedelta(days=7), today + timedelta(days=14))
                    FollowUpStatus.objects.create(
                        counselor=counselor,
                        student=sm,
                        mode_of_follow_up=md,
                        follow_up_status=st,
                        last_follow_up_date=d,
                        next_follow_up_date=nxt,
                        is_followed_up=(st == "completed"),
                        message=msg,
                    )
                    created_total += 1

            messages.success(
                request,
                f"Created {created_total} dummy follow-up entries for {len(students)} student(s) (level: {level}).",
            )
        except Exception as e:
            messages.error(request, f"Could not generate dummy counseling data: {e}")

        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def reset_counseling_data_view(self, request):
        """
        Admin utility: Delete FollowUpStatus rows for the demo counselor against selected demo students.
        Intended to reset the counselor UI testing data without touching student/institute demo dataset.
        """
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        config = DemoDatasetConfig.get_singleton()
        counselor_id = getattr(config, "counselor_id", None)
        if not counselor_id:
            messages.error(request, "Demo counselor not set up. Run 'Setup demo counselor' first.")
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        # Inputs (optional): if nothing selected, reset for all demo students in config
        student_ids = request.POST.getlist("demo_student_ids_reset") or []
        if not student_ids:
            one = (request.POST.get("demo_student_id_reset") or "").strip()
            if one:
                student_ids = [one]
        try:
            student_ids = [int(x) for x in student_ids if str(x).strip().isdigit()]
        except Exception:
            student_ids = []

        try:
            from counselor.models import FollowUpStatus
            from institute.models import StudentManagement

            if not student_ids:
                # Map demo student user IDs -> StudentManagement ids (same scope as generation dropdown)
                sids = list(getattr(config, "student_user_ids", []) or [])
                student_ids = list(
                    StudentManagement.objects.filter(student_id__in=sids).values_list("id", flat=True)
                )

            if not student_ids:
                messages.warning(request, "No demo students found to reset.")
                return redirect("admin:demo_data_demodatasetconfig_changelist")

            deleted, _ = FollowUpStatus.objects.filter(
                counselor_id=int(counselor_id),
                student_id__in=student_ids,
            ).delete()
            messages.success(
                request,
                f"Reset dummy counselling data: deleted {deleted} FollowUpStatus row(s).",
            )
        except Exception as e:
            messages.error(request, f"Could not reset dummy counselling data: {e}")

        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def generate_heatmap_data_view(self, request):
        """
        Admin utility: Create demo `Results` rows (test1/test2/test3) for selected demo students.
        Heatmap reads these three test papers to compute interest/knowledge/alignment.
        """
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        config = DemoDatasetConfig.get_singleton()
        student_ids = request.POST.getlist("demo_student_ids_heatmap") or []

        try:
            from institute.models import StudentManagement
            from app.models import Results

            sids = list(getattr(config, "student_user_ids", []) or [])
            qs = StudentManagement.objects.filter(student_id__in=sids).select_related("student", "class_and_section")
            if student_ids:
                qs = qs.filter(id__in=student_ids)
            sms = list(qs)
            if not sms:
                messages.error(request, "No matching demo students found for heatmap generation.")
                return redirect("admin:demo_data_demodatasetconfig_changelist")

            # Deterministic randomness per run (stable demo).
            seed = int(timezone.now().strftime("%Y%m%d"))
            rng = random.Random(seed)

            # Ensure streams are set so heatmap clusters aren't all "Unknown".
            stream_choices = ["PCM", "CBM", "COMM", "HME", "HMB"]

            # Helper payloads: keep within expected ranges used by institute/utils.py
            def _test1_results():
                # Personality-ish numeric values
                keys = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
                return {k: rng.randint(2, 9) for k in keys}

            def _test2_scores():
                # RIASEC scores 0..6
                return {k: rng.randint(0, 6) for k in ["R", "I", "A", "S", "E", "C"]}

            def _test3_scores():
                # Intelligence-like numeric values 0..10
                keys = ["linguistic", "logical", "spatial", "musical", "bodily", "interpersonal", "intrapersonal", "naturalist"]
                return {k: rng.randint(0, 10) for k in keys}

            created = 0
            updated = 0
            for sm in sms:
                u = getattr(sm, "student", None)
                if not u:
                    continue

                # Best-effort: set stream on the student's class/section.
                try:
                    cas = getattr(sm, "class_and_section", None)
                    if cas is not None and not getattr(cas, "stream", None):
                        cas.stream = rng.choice(stream_choices)
                        cas.save(update_fields=["stream"])
                except Exception:
                    pass

                # Remove any existing duplicates so heatmap `.first()` is stable.
                for tp in ("test1", "test2", "test3"):
                    Results.objects.filter(user=u, test_paper=tp).delete()

                Results.objects.create(
                    user=u,
                    test_paper="test1",
                    scores={},
                    results=_test1_results(),
                    selected_answers={},
                )
                Results.objects.create(
                    user=u,
                    test_paper="test2",
                    scores=_test2_scores(),
                    results={},
                    selected_answers={},
                )
                Results.objects.create(
                    user=u,
                    test_paper="test3",
                    scores=_test3_scores(),
                    results={},
                    selected_answers={},
                )
                created += 3

            messages.success(
                request,
                f"Heatmap demo data generated: {created} Results rows for {len(sms)} student(s).",
            )
        except Exception as e:
            messages.error(request, f"Heatmap demo generation failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

    def reset_heatmap_data_view(self, request):
        """Admin utility: delete demo `Results` rows (test1/test2/test3) for selected/all demo students."""
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        config = DemoDatasetConfig.get_singleton()
        student_ids = request.POST.getlist("demo_student_ids_heatmap_reset") or []
        try:
            from institute.models import StudentManagement
            from app.models import Results

            sids = list(getattr(config, "student_user_ids", []) or [])
            qs = StudentManagement.objects.filter(student_id__in=sids).select_related("student")
            if student_ids:
                qs = qs.filter(id__in=student_ids)
            uids = [sm.student_id for sm in qs if getattr(sm, "student_id", None)]
            if not uids:
                messages.error(request, "No matching demo students found for heatmap reset.")
                return redirect("admin:demo_data_demodatasetconfig_changelist")

            deleted, _ = Results.objects.filter(user_id__in=uids, test_paper__in=["test1", "test2", "test3"]).delete()
            messages.success(request, f"Heatmap demo data reset: deleted {deleted} Results row(s).")
        except Exception as e:
            messages.error(request, f"Heatmap demo reset failed: {e}")
        return redirect("admin:demo_data_demodatasetconfig_changelist")

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
        return self._enqueue_demo_job(
            request,
            DemoJobAction.SETUP_COUNSELOR,
            setup_demo_counselor_task,
            "Demo counselor setup queued on Celery.",
        )

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
        return self._enqueue_demo_job(
            request,
            DemoJobAction.RESET_COUNSELOR,
            reset_demo_counselor_task,
            "Demo counselor reset queued on Celery.",
        )

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
        return self._enqueue_demo_job(
            request,
            DemoJobAction.REMOVE_COUNSELOR,
            remove_demo_counselor_task,
            "Demo counselor remove queued on Celery.",
        )

    def setup_demo_data_view(self, request):
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return self._enqueue_demo_job(
            request,
            DemoJobAction.SETUP_STUDENTS,
            setup_demo_dataset_task,
            "Student demo setup queued on Celery (avoids 502 on large batches).",
        )

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
        return self._enqueue_demo_job(
            request,
            DemoJobAction.RESET_STUDENTS,
            reset_demo_dataset_task,
            "Student demo reset queued on Celery.",
        )

    def reseed_student_psych_view(self, request):
        """
        POST: reseed psychometric data for one system-demo student (user id) with a chosen ResultType.
        """
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method != "POST":
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        raw_uid = (request.POST.get("demo_student_user_id") or "").strip()
        result_type = (request.POST.get("result_type") or "").strip()
        if not raw_uid.isdigit():
            messages.error(request, "Invalid student user id.")
            return redirect("admin:demo_data_demodatasetconfig_changelist")

        try:
            out = reseed_demo_student_psychometric(int(raw_uid), result_type)
            messages.success(
                request,
                f"Psychometric data reseeded for demo student (user id {out['user_id']}, class {out['grade']}, profile: {out['result_type']}).",
            )
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Reseed failed: {e}")

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
        return self._enqueue_demo_job(
            request,
            DemoJobAction.REMOVE_STUDENTS,
            remove_demo_dataset_task,
            "Student demo remove queued on Celery.",
        )
