from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import BaseModel
from course_mindmap.constants import (
    GENERATION_STATUS_CHOICES,
    GENERATION_STATUS_DRY_RUN,
    GENERATION_STATUS_FAILED,
    GENERATION_STATUS_GENERATED,
    GRADE_MODE_CHOICES,
    GRADE_MODE_NONE,
    SCOPE_CHOICES,
)

User = get_user_model()


class CourseMindmapGeneration(BaseModel):
    """Audit log for dry-run / run generation attempts."""

    course_type_key = models.CharField(max_length=64, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    course = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        max_length=20,
        choices=GENERATION_STATUS_CHOICES,
        default=GENERATION_STATUS_DRY_RUN,
        db_index=True,
    )
    dry_run = models.BooleanField(default=True)
    map_type = models.CharField(max_length=32, blank=True, default="classic_vertical")
    report = models.JSONField(default=dict, blank=True)
    scope_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    generated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="course_mindmap_generations",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Course mindmap generation"
        verbose_name_plural = "Course mindmap generations"
        ordering = ("-created",)

    def __str__(self):
        return f"{self.course_type_key} #{self.object_id} ({self.status})"


class CourseMindmapData(BaseModel):
    """DB-stored mindmap JSON per scope (course / chapter / section) for fast reads."""

    course_type_key = models.CharField(max_length=64, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    course = GenericForeignKey("content_type", "object_id")

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, db_index=True)
    scope_id = models.PositiveIntegerField(default=0, db_index=True)
    label = models.CharField(max_length=255, blank=True)

    payload = models.JSONField(default=dict)
    is_valid = models.BooleanField(default=False, db_index=True)
    generation = models.ForeignKey(
        CourseMindmapGeneration,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="data_rows",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Course mindmap data"
        verbose_name_plural = "Course mindmap data"
        ordering = ("content_type", "object_id", "scope", "scope_id")
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "scope", "scope_id"],
                name="unique_course_mindmap_scope",
            ),
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id", "scope"]),
        ]

    def __str__(self):
        sid = self.scope_id if self.scope_id is not None else "—"
        return f"{self.scope}:{sid} ({self.label})"


class CourseMindmapConfig(BaseModel):
    """Per-course placement and grade visibility (unlocked after verification)."""

    course_type_key = models.CharField(max_length=64, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    course = GenericForeignKey("content_type", "object_id")

    enable_title_mindmap = models.BooleanField(default=False)
    enable_sidebar_mindmap = models.BooleanField(default=False)
    enable_content_area_mindmap = models.BooleanField(default=False)

    grade_mode = models.CharField(
        max_length=20,
        choices=GRADE_MODE_CHOICES,
        default=GRADE_MODE_NONE,
    )
    grades = models.ManyToManyField(
        "skilllab.SkillLabCourseGrade",
        blank=True,
        related_name="mindmap_configs",
        help_text="When grade mode is Selected, only these classes see mindmaps.",
    )
    map_type = models.CharField(max_length=32, blank=True, default="")

    is_verified = models.BooleanField(default=False, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_course_mindmap_configs",
    )
    last_generation = models.ForeignKey(
        CourseMindmapGeneration,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="configs",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Course mindmap configuration"
        verbose_name_plural = "Course mindmap configurations"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="unique_course_mindmap_config",
            ),
        ]

    def __str__(self):
        return f"Mindmap config #{self.object_id} ({self.course_type_key})"

    @property
    def config_locked(self) -> bool:
        return not self.is_verified
