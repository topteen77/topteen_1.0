from django.db import models
from django.core.exceptions import ValidationError


class DemoCounselorCourseState:
    """Career counselor course progress for the demo counselor account."""
    PASSED = "passed"
    FAILED = "failed"
    NOT_COMPLETED = "not_completed"
    CHOICES = (
        (PASSED, "Passed (full completion + certificate if eligible)"),
        (FAILED, "Failed (videos done; quizzes still to pass)"),
        (NOT_COMPLETED, "Not completed (paid; no lesson/quiz progress)"),
    )


class ResultType:
    """How to generate psychometric scores for demo students."""
    VARIED = "varied"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MIXED = "mixed"
    CHOICES = [
        (VARIED, "Varied (different scores per student)"),
        (HIGH, "High (all high scores)"),
        (MEDIUM, "Medium (mid-range scores)"),
        (LOW, "Low (all low scores)"),
        (MIXED, "Mixed (mix of high/low across tests)"),
    ]


class DemoJobStatus:
    """Background Celery job status for long demo setup/reset/remove runs."""
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CHOICES = [
        (IDLE, "Idle"),
        (QUEUED, "Queued"),
        (RUNNING, "Running"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
    ]
    IN_PROGRESS = (QUEUED, RUNNING)


class DemoJobAction:
    SETUP_STUDENTS = "setup_students"
    RESET_STUDENTS = "reset_students"
    REMOVE_STUDENTS = "remove_students"
    SETUP_COUNSELOR = "setup_counselor"
    RESET_COUNSELOR = "reset_counselor"
    REMOVE_COUNSELOR = "remove_counselor"
    CHOICES = [
        (SETUP_STUDENTS, "Setup student demo"),
        (RESET_STUDENTS, "Reset student demo"),
        (REMOVE_STUDENTS, "Remove student demo"),
        (SETUP_COUNSELOR, "Setup demo counselor"),
        (RESET_COUNSELOR, "Reset demo counselor"),
        (REMOVE_COUNSELOR, "Remove demo counselor"),
    ]
    LABELS = dict(CHOICES)


class DemoDatasetConfig(models.Model):
    """
    Singleton (one row): configuration for demo data generation + IDs from last run.
    Admin edits configuration; Setup/Reset writes institute_id, student_user_ids, etc.
    """
    # --- Configuration (admin-editable) ---
    num_students_class_10 = models.PositiveIntegerField(
        default=2,
        help_text="Number of demo students in Class 10.",
    )
    num_students_class_12 = models.PositiveIntegerField(
        default=4,
        help_text="Number of demo students in Class 12.",
    )
    psychometric_tests_complete = models.BooleanField(
        default=True,
        help_text="If True, students with psychometric data get TestCompletion flags set (test1/test2/test3 complete).",
    )
    num_psychometric_class_10 = models.PositiveIntegerField(
        default=1,
        help_text="Number of Class 10 demo students with psychometric (test) complete.",
    )
    num_psychometric_class_12 = models.PositiveIntegerField(
        default=2,
        help_text="Number of Class 12 demo students with psychometric (test) complete.",
    )
    num_students_with_psychometric = models.PositiveIntegerField(
        default=3,
        help_text="Deprecated: use num_psychometric_class_10 + num_psychometric_class_12. Kept for migration.",
    )
    result_type_class_10 = models.CharField(
        max_length=20,
        choices=ResultType.CHOICES,
        default=ResultType.VARIED,
        help_text="Result type for Class 10 students with psychometric data (e.g. varied = high/medium/low/mixed).",
    )
    result_type_class_12 = models.CharField(
        max_length=20,
        choices=ResultType.CHOICES,
        default=ResultType.HIGH,
        help_text="Result type for Class 12 students with psychometric data.",
    )
    demo_counselor_course_state = models.CharField(
        max_length=20,
        choices=DemoCounselorCourseState.CHOICES,
        default=DemoCounselorCourseState.PASSED,
        help_text="Course progress for the demo counselor: passed, failed (stuck after videos), or not completed (paid only).",
    )

    # --- Last run output (system-written, read-only in admin) ---
    institute_id = models.PositiveIntegerField(null=True, blank=True)
    institute_user_id = models.PositiveIntegerField(null=True, blank=True)
    parent_user_id = models.PositiveIntegerField(null=True, blank=True)
    student_user_ids = models.JSONField(
        default=list,
        help_text="List of user IDs for demo students (from last setup/reset).",
    )
    counselor_user_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Demo counselor user ID (from last setup/reset).",
    )
    counselor_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Demo Counselor profile ID (from last setup/reset).",
    )

    # --- Background job status (Celery) ---
    last_job_status = models.CharField(
        max_length=20,
        choices=DemoJobStatus.CHOICES,
        default=DemoJobStatus.IDLE,
        help_text="Status of the last queued demo setup/reset/remove job.",
    )
    last_job_action = models.CharField(
        max_length=40,
        choices=DemoJobAction.CHOICES,
        blank=True,
        default="",
        help_text="Which admin action was last queued.",
    )
    last_job_task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Celery task id of the last queued job.",
    )
    last_job_message = models.TextField(
        blank=True,
        default="",
        help_text="Human-readable status / error from the last job.",
    )
    last_job_started_at = models.DateTimeField(null=True, blank=True)
    last_job_finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = "Demo dataset config"
        verbose_name_plural = "Demo dataset config"

    def __str__(self):
        return "Demo dataset config"

    def get_total_students(self):
        return self.num_students_class_10 + self.num_students_class_12

    def clean(self):
        total = self.get_total_students()
        if total == 0:
            raise ValidationError(
                {"num_students_class_10": "At least one of Class 10 or Class 12 count must be > 0."}
            )
        n10 = self.num_students_class_10
        n12 = self.num_students_class_12
        n10_psych = getattr(self, "num_psychometric_class_10", 0)
        n12_psych = getattr(self, "num_psychometric_class_12", 0)
        if n10_psych > n10:
            raise ValidationError({"num_psychometric_class_10": f"Cannot exceed Class 10 count ({n10})."})
        if n12_psych > n12:
            raise ValidationError({"num_psychometric_class_12": f"Cannot exceed Class 12 count ({n12})."})

    @classmethod
    def get_singleton(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def job_in_progress(self):
        return self.last_job_status in DemoJobStatus.IN_PROGRESS

    def mark_job_queued(self, action, task_id, message=""):
        from django.utils import timezone

        self.last_job_status = DemoJobStatus.QUEUED
        self.last_job_action = action
        self.last_job_task_id = task_id or ""
        self.last_job_message = message or "Queued on Celery worker."
        self.last_job_started_at = timezone.now()
        self.last_job_finished_at = None
        self.save(
            update_fields=[
                "last_job_status",
                "last_job_action",
                "last_job_task_id",
                "last_job_message",
                "last_job_started_at",
                "last_job_finished_at",
                "updated_at",
            ]
        )

    def mark_job_running(self, message=""):
        from django.utils import timezone

        self.last_job_status = DemoJobStatus.RUNNING
        self.last_job_message = message or "Running…"
        if not self.last_job_started_at:
            self.last_job_started_at = timezone.now()
        self.save(
            update_fields=[
                "last_job_status",
                "last_job_message",
                "last_job_started_at",
                "updated_at",
            ]
        )

    def mark_job_success(self, message=""):
        from django.utils import timezone

        self.last_job_status = DemoJobStatus.SUCCESS
        self.last_job_message = message or "Completed successfully."
        self.last_job_finished_at = timezone.now()
        self.save(
            update_fields=[
                "last_job_status",
                "last_job_message",
                "last_job_finished_at",
                "updated_at",
            ]
        )

    def mark_job_failed(self, message=""):
        from django.utils import timezone

        self.last_job_status = DemoJobStatus.FAILED
        self.last_job_message = message or "Job failed."
        self.last_job_finished_at = timezone.now()
        self.save(
            update_fields=[
                "last_job_status",
                "last_job_message",
                "last_job_finished_at",
                "updated_at",
            ]
        )
