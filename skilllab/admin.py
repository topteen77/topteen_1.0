from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from core import choices
from .models import (
    SkilllabCoursePayment,
    SkillLabCourse,
    SkillLabCourseGrade,
    SkillLabCourseTopicCategory,
    SkillLabCourseChapter,
    SkillLabChapterSection,
    SkillLabCourseActivity,
    SkillLabCourseProgress,
    SkillLabCourseProgressSummary,
    SkillLabCourseResume,
    SkillLabWorksheetProgress,
    SkillLabMCQAttempt,
    SkillLabMCQ,
    SkillLabMCQQuestion,
    SkillLabMCQAnswer,
    SkillLabUserHighlight,
    SkillLabUserNote,
    SkillLabUserBookmark,
    InternationalOnlineCourse,
)
from users.skilllab_dashboard import skilllab_course_student_counts_bulk


# --- Admin actions for soft delete, hard delete, restore ---

def soft_delete_selected(modeladmin, request, queryset):
    """Mark selected records as Deleted (soft delete)."""
    count = queryset.update(object_status=choices.ObjectStatus.DELETED)
    modeladmin.message_user(request, f"{count} record(s) marked as Deleted.")


soft_delete_selected.short_description = "Soft delete selected"


def hard_delete_selected(modeladmin, request, queryset):
    """Permanently delete selected records from database."""
    count = queryset.count()
    for obj in queryset:
        obj.delete(hard_delete=True)
    modeladmin.message_user(request, f"{count} record(s) permanently deleted.")


hard_delete_selected.short_description = "Hard delete selected (permanent)"


def restore_selected(modeladmin, request, queryset):
    """Restore selected records to Active status."""
    count = queryset.update(object_status=choices.ObjectStatus.ACTIVE)
    modeladmin.message_user(request, f"{count} record(s) restored to Active.")


restore_selected.short_description = "Restore selected"


# --- Base mixin for Skill Lab models with object_status ---

class SkillLabAdminMixin:
    """Mixin for Skill Lab admins: show all records, status filter, delete actions."""

    list_filter = ("object_status",)
    actions = [soft_delete_selected, restore_selected, hard_delete_selected]

    def get_queryset(self, request):
        """Show all records including soft-deleted."""
        qs = super().get_queryset(request)
        if hasattr(qs.model, "objects") and hasattr(qs.model.objects, "complete"):
            return qs.model.objects.complete()
        return qs


# --- ModelAdmin classes (each model on its own page, no inlines) ---

@admin.register(SkillLabCourseGrade)
class SkillLabCourseGradeAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'grade_number', 'sort_order', 'object_status', 'modified']
    list_editable = ['sort_order', 'object_status']
    search_fields = ['name']
    ordering = ['sort_order', 'grade_number']


@admin.register(SkillLabCourseTopicCategory)
class SkillLabCourseTopicCategoryAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'slug', 'sort_order', 'object_status', 'modified']
    list_editable = ['sort_order', 'object_status']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['sort_order', 'name']


@admin.register(SkillLabCourse)
class SkillLabCourseAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/skilllab/skilllabcourse/change_list.html"
    list_display = [
        "name", "topic_category", "grades_display", "category", "amount",
        "users_link", "chapters_link", "sections_link", "activities_link", "mcqs_link",
        "object_status", "modified",
    ]

    def delete_model(self, request, obj):
        """Hard delete: remove course + all chapters, activities, MCQs, images, PDFs, S3 files."""
        obj.delete(hard_delete=True)

    def delete_queryset(self, request, queryset):
        """Hard delete selected courses: remove each with all related data and files."""
        for obj in queryset:
            obj.delete(hard_delete=True)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            cl = response.context_data.get("cl")
            if cl is not None:
                course_ids = [obj.pk for obj in cl.result_list if obj.pk]
                counts = skilllab_course_student_counts_bulk(course_ids)
                for obj in cl.result_list:
                    obj._student_user_counts = counts.get(
                        obj.pk, {"active": 0, "deleted": 0}
                    )
        except Exception:
            pass
        return response
    list_filter = ["topic_category", "grades", "category", "object_status"]
    search_fields = ["name"]
    list_editable = ["object_status"]
    filter_horizontal = ["grades"]
    readonly_fields = ["related_content_links", "mindmap_admin_link"]
    fieldsets = (
        (None, {"fields": ("name", "slug", "category", "amount", "image", "video_url", "object_status")}),
        ("Catalog filters (class & topic)", {"fields": ("grades", "topic_category")}),
        ("Course Introduction (tab content)", {"fields": ("course_intro_html",)}),
        ("Course Index (tab content)", {"fields": ("course_index_html",)}),
        ("Mindmap", {"fields": ("mindmap_admin_link",)}),
        ("Related content", {"fields": ("related_content_links",)}),
    )

    def grades_display(self, obj):
        if not obj.pk:
            return "-"
        labels = list(obj.grades.order_by('sort_order', 'grade_number').values_list('name', flat=True))
        return ", ".join(labels) if labels else "-"

    grades_display.short_description = "Classes"

    def users_link(self, obj):
        if not obj.pk:
            return "-"
        counts = getattr(obj, "_student_user_counts", {"active": 0, "deleted": 0})
        active = counts.get("active", 0)
        deleted = counts.get("deleted", 0)
        base_url = (
            reverse("admin:skilllab_skilllabcourseprogresssummary_changelist")
            + f"?skilllab_course__id__exact={obj.pk}"
        )
        active_url = base_url + f"&object_status__exact={choices.ObjectStatus.ACTIVE}"
        deleted_url = base_url + f"&object_status__exact={choices.ObjectStatus.DELETED}"

        parts = []
        if active:
            parts.append(format_html('<a href="{}">{} Users</a>', active_url, active))
        if deleted:
            parts.append(
                format_html(
                    '<a href="{}" title="Soft-deleted — restore or hard delete">{} deleted</a>',
                    deleted_url,
                    deleted,
                )
            )
        if parts:
            return format_html(" · ".join(str(p) for p in parts))
        return format_html('<span style="color:#999;">0 Users</span>')

    users_link.short_description = "Users"

    def mindmap_admin_link(self, obj):
        if not obj.pk:
            return "-"
        from course_mindmap.constants import COURSE_TYPE_SKILLLAB

        url = (
            reverse("admin:course_mindmap_generate")
            + f"?course_type_key={COURSE_TYPE_SKILLLAB}&course_id={obj.pk}"
        )
        config_url = reverse("admin:course_mindmap_coursemindmapconfig_changelist")
        return format_html(
            '<a href="{}">Generate / preview mindmap</a> · <a href="{}">All mindmap configs</a>',
            url,
            config_url,
        )

    mindmap_admin_link.short_description = "Course mindmap"

    def chapters_link(self, obj):
        if not obj.pk:
            return "-"
        count = obj.skilllabcoursechapter.count()
        url = reverse("admin:skilllab_skilllabcoursechapter_changelist") + f"?skilllab__id__exact={obj.pk}"
        return format_html('<a href="{}">{} Chapters</a>', url, count)

    chapters_link.short_description = "Chapters"

    def sections_link(self, obj):
        if not obj.pk:
            return "-"
        count = SkillLabChapterSection.objects.filter(chapter__skilllab=obj).count()
        url = reverse("admin:skilllab_skilllabchaptersection_changelist") + f"?chapter__skilllab__id__exact={obj.pk}"
        return format_html('<a href="{}">{} Sections</a>', url, count)

    sections_link.short_description = "Sections"

    def activities_link(self, obj):
        if not obj.pk:
            return "-"
        count = SkillLabCourseActivity.objects.filter(skilllab_chapter__skilllab=obj).count()
        url = reverse("admin:skilllab_skilllabcourseactivity_changelist") + f"?skilllab_chapter__skilllab__id__exact={obj.pk}"
        return format_html('<a href="{}">{} Activities</a>', url, count)

    activities_link.short_description = "Activities"

    def mcqs_link(self, obj):
        if not obj.pk:
            return "-"
        count = SkillLabMCQ.objects.filter(skilllab_chapter__skilllab=obj).count()
        url = reverse("admin:skilllab_skilllabmcq_changelist") + f"?skilllab_chapter__skilllab__id__exact={obj.pk}"
        return format_html('<a href="{}">{} MCQs</a>', url, count)

    mcqs_link.short_description = "MCQs"

    def related_content_links(self, obj):
        if not obj.pk:
            return "-"
        links = []
        ch_url = reverse("admin:skilllab_skilllabcoursechapter_changelist") + f"?skilllab__id__exact={obj.pk}"
        links.append(format_html('<a href="{}">View Chapters</a>', ch_url))
        act_url = reverse("admin:skilllab_skilllabcourseactivity_changelist") + f"?skilllab_chapter__skilllab__id__exact={obj.pk}"
        links.append(format_html('<a href="{}">View Activities</a>', act_url))
        mcq_url = reverse("admin:skilllab_skilllabmcq_changelist") + f"?skilllab_chapter__skilllab__id__exact={obj.pk}"
        links.append(format_html('<a href="{}">View MCQs</a>', mcq_url))
        course_q = f"skilllab_course__id__exact={obj.pk}"
        summary_url = reverse("admin:skilllab_skilllabcourseprogresssummary_changelist") + f"?{course_q}"
        links.append(format_html('<a href="{}">Student progress summary</a>', summary_url))
        progress_url = reverse("admin:skilllab_skilllabcourseprogress_changelist") + f"?{course_q}"
        links.append(format_html('<a href="{}">Chapter progress</a>', progress_url))
        resume_url = reverse("admin:skilllab_skilllabcourseresume_changelist") + f"?{course_q}"
        links.append(format_html('<a href="{}">Resume state</a>', resume_url))
        worksheet_url = (
            reverse("admin:skilllab_skilllabworksheetprogress_changelist")
            + f"?activity__skilllab_chapter__skilllab__id__exact={obj.pk}"
        )
        links.append(format_html('<a href="{}">Worksheet progress</a>', worksheet_url))
        mcq_attempt_url = (
            reverse("admin:skilllab_skilllabmcqattempt_changelist")
            + f"?mcq__skilllab_chapter__skilllab__id__exact={obj.pk}"
        )
        links.append(format_html('<a href="{}">MCQ attempts</a>', mcq_attempt_url))
        payment_url = reverse("admin:skilllab_skilllabcoursepayment_changelist") + f"?{course_q}"
        links.append(format_html('<a href="{}">Payments</a>', payment_url))
        return format_html(" | ".join(str(link) for link in links))

    related_content_links.short_description = "Related content"


@admin.register(SkillLabCourseChapter)
class SkillLabCourseChapterAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["chapter_name", "skilllab", "sections_count", "sections_link", "activities_link", "mcqs_link", "object_status", "modified"]
    list_filter = ["skilllab", "object_status"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_sections_count=Count("sections"))
    search_fields = ["chapter_name"]
    list_editable = ["object_status"]
    readonly_fields = ["related_content_links"]
    fieldsets = (
        (None, {"fields": ("chapter_name", "skilllab", "object_status")}),
        ("Related content", {"fields": ("related_content_links",)}),
        ("Legacy content (fallback when no sections)", {"fields": ("content",), "classes": ("collapse",)}),
    )

    def sections_link(self, obj):
        if not obj.pk:
            return "-"
        count = obj.sections.count()
        url = reverse("admin:skilllab_skilllabchaptersection_changelist") + f"?chapter__id__exact={obj.pk}"
        return format_html('<a href="{}">{} Sections</a>', url, count)

    sections_link.short_description = "Sections"

    def sections_count(self, obj):
        return getattr(obj, "_sections_count", obj.sections.count())

    sections_count.short_description = "Sections"
    sections_count.admin_order_field = "_sections_count"

    def activities_link(self, obj):
        if not obj.pk:
            return "-"
        count = obj.skilllabcourseactivity.count()
        url = reverse("admin:skilllab_skilllabcourseactivity_changelist") + f"?skilllab_chapter__id__exact={obj.pk}"
        return format_html('<a href="{}">{} Activities</a>', url, count)

    activities_link.short_description = "Activities"

    def mcqs_link(self, obj):
        if not obj.pk:
            return "-"
        count = obj.mcqs.count()
        url = reverse("admin:skilllab_skilllabmcq_changelist") + f"?skilllab_chapter__id__exact={obj.pk}"
        return format_html('<a href="{}">{} MCQs</a>', url, count)

    mcqs_link.short_description = "MCQs"

    def related_content_links(self, obj):
        if not obj.pk:
            return "-"
        links = []
        sec_url = reverse("admin:skilllab_skilllabchaptersection_changelist") + f"?chapter__id__exact={obj.pk}"
        links.append(format_html('<a href="{}">View Sections</a>', sec_url))
        act_url = reverse("admin:skilllab_skilllabcourseactivity_changelist") + f"?skilllab_chapter__id__exact={obj.pk}"
        links.append(format_html('<a href="{}">View Activities</a>', act_url))
        mcq_url = reverse("admin:skilllab_skilllabmcq_changelist") + f"?skilllab_chapter__id__exact={obj.pk}"
        links.append(format_html('<a href="{}">View MCQs</a>', mcq_url))
        return format_html(" | ".join(str(l) for l in links))

    related_content_links.short_description = "Related content"


@admin.register(SkillLabChapterSection)
class SkillLabChapterSectionAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["order", "section_type", "title", "chapter", "content_preview", "object_status", "modified"]
    list_filter = ["section_type", "chapter__skilllab", "chapter", "object_status"]
    search_fields = ["title", "content", "chapter__chapter_name"]
    list_editable = ["object_status"]
    autocomplete_fields = ["chapter"]
    ordering = ["chapter", "order"]
    fieldsets = (
        (None, {"fields": ("chapter", "section_type", "order", "title", "object_status")}),
        ("Content", {"fields": ("content",)}),
    )

    def content_preview(self, obj):
        text = (obj.content or "")[:80]
        return text + "..." if len(obj.content or "") > 80 else text

    content_preview.short_description = "Content"


@admin.register(SkillLabCourseActivity)
class SkillLabCourseActivityAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["name", "type", "skilllab_chapter", "object_status", "modified"]
    list_filter = ["type", "skilllab_chapter__skilllab", "object_status"]
    search_fields = ["name", "content"]
    list_editable = ["object_status"]


@admin.register(SkillLabMCQ)
class SkillLabMCQAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["title", "skilllab_chapter", "object_status", "modified"]
    list_filter = ["skilllab_chapter__skilllab", "object_status"]
    search_fields = ["title", "description"]
    list_editable = ["object_status"]


@admin.register(SkillLabMCQQuestion)
class SkillLabMCQQuestionAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["question_number", "question_text_preview", "mcq", "order", "object_status", "modified"]
    list_filter = ["mcq__skilllab_chapter__skilllab", "object_status"]
    search_fields = ["question_text"]
    list_editable = ["object_status"]

    def question_text_preview(self, obj):
        text = obj.question_text or ""
        return text[:80] + "..." if len(text) > 80 else text

    question_text_preview.short_description = "Question"


@admin.register(SkillLabMCQAnswer)
class SkillLabMCQAnswerAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["answer_letter", "answer_text_preview", "is_correct", "question", "order", "object_status", "modified"]
    list_filter = ["is_correct", "question__mcq__skilllab_chapter__skilllab", "object_status"]
    search_fields = ["answer_text"]
    list_editable = ["object_status"]

    def answer_text_preview(self, obj):
        text = obj.answer_text or ""
        return text[:60] + "..." if len(text) > 60 else text

    answer_text_preview.short_description = "Answer"


@admin.register(SkillLabCourseProgress)
class SkillLabCourseProgressAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "skilllab_course", "chapter", "completed", "completed_at", "object_status", "modified"]
    list_filter = ["completed", "skilllab_course", "object_status"]
    search_fields = ["user__email", "skilllab_course__name", "chapter__chapter_name"]
    raw_id_fields = ["user", "skilllab_course", "chapter"]
    actions = [soft_delete_selected, restore_selected, hard_delete_selected]


@admin.register(SkillLabCourseProgressSummary)
class SkillLabCourseProgressSummaryAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "skilllab_course", "progress_percentage", "completed_sections_count", "total_sections_count", "object_status", "updated_at"]
    list_filter = ["skilllab_course", "object_status"]
    search_fields = ["user__email", "user__username", "skilllab_course__name"]
    raw_id_fields = ["user", "skilllab_course"]
    readonly_fields = ["progress_percentage", "completed_sections_count", "total_sections_count", "updated_at"]
    ordering = ["user", "-progress_percentage"]
    list_select_related = ["user", "skilllab_course"]
    list_editable = ["object_status"]


@admin.register(SkillLabCourseResume)
class SkillLabCourseResumeAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "skilllab_course", "last_section_index", "object_status", "updated_at"]
    list_filter = ["skilllab_course", "object_status"]
    search_fields = ["user__email", "skilllab_course__name"]
    raw_id_fields = ["user", "skilllab_course"]
    ordering = ["-updated_at"]


@admin.register(SkillLabWorksheetProgress)
class SkillLabWorksheetProgressAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "activity", "downloaded_at", "object_status", "modified"]
    list_filter = ["activity__skilllab_chapter__skilllab", "object_status"]
    search_fields = ["user__email", "activity__name", "activity__skilllab_chapter__skilllab__name"]
    raw_id_fields = ["user", "activity"]


@admin.register(SkillLabMCQAttempt)
class SkillLabMCQAttemptAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "mcq", "score", "total", "attempted_at", "object_status"]
    list_filter = ["mcq__skilllab_chapter__skilllab", "object_status"]
    search_fields = ["user__email", "mcq__title", "mcq__skilllab_chapter__skilllab__name"]
    raw_id_fields = ["user", "mcq"]
    ordering = ["-attempted_at"]


@admin.register(SkillLabUserHighlight)
class SkillLabUserHighlightAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "skilllab_course", "section_type", "section_id", "object_status", "modified"]
    list_filter = ["skilllab_course", "section_type", "object_status"]
    search_fields = ["user__email", "skilllab_course__name", "highlighted_text"]
    raw_id_fields = ["user", "skilllab_course"]


@admin.register(SkillLabUserNote)
class SkillLabUserNoteAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "skilllab_course", "name", "section_type", "object_status", "modified"]
    list_filter = ["skilllab_course", "section_type", "object_status"]
    search_fields = ["user__email", "skilllab_course__name", "name", "note_text"]
    raw_id_fields = ["user", "skilllab_course"]


@admin.register(SkillLabUserBookmark)
class SkillLabUserBookmarkAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["user", "skilllab_course", "section_title", "section_key", "object_status", "modified"]
    list_filter = ["skilllab_course", "object_status"]
    search_fields = ["user__email", "skilllab_course__name", "section_title", "section_key"]
    raw_id_fields = ["user", "skilllab_course"]


class InternationalOnlineCourseAdminForm(forms.ModelForm):
    class Meta:
        model = InternationalOnlineCourse
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        max_size_mb = getattr(settings, "S3_MAX_FILE_SIZE_MB", 2)
        for field_name in ("image", "logo"):
            if field_name in self.fields:
                self.fields[field_name].required = False
                self.fields[field_name].help_text = (
                    f"Optional. Max size: {max_size_mb} MB. "
                    "Leave empty to use the default placeholder on the website."
                )

    def _validate_upload_size(self, uploaded_file, label):
        if not uploaded_file or not hasattr(uploaded_file, "size"):
            return uploaded_file
        max_size_mb = getattr(settings, "S3_MAX_FILE_SIZE_MB", 2)
        max_bytes = max_size_mb * 1024 * 1024
        if uploaded_file.size > max_bytes:
            raise ValidationError(f"{label} must be {max_size_mb} MB or less.")
        return uploaded_file

    def clean_image(self):
        return self._validate_upload_size(self.cleaned_data.get("image"), "Image")

    def clean_logo(self):
        return self._validate_upload_size(self.cleaned_data.get("logo"), "Logo")


@admin.register(InternationalOnlineCourse)
class InternationalOnlineCourseAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    form = InternationalOnlineCourseAdminForm
    change_form_template = "admin/skilllab/internationalonlinecourse/change_form.html"
    list_display = ["title", "subject", "institute", "priority", "object_status", "modified"]
    list_filter = ["subject", "institute", "object_status"]
    search_fields = ["title", "description", "subject", "institute"]
    list_editable = ["priority", "object_status"]
    ordering = ["priority", "title"]
    readonly_fields = ["image_preview", "logo_preview"]
    fieldsets = (
        (None, {"fields": ("title", "description", "url", "subject", "institute", "priority", "object_status")}),
        ("Images", {"fields": ("image", "image_preview", "logo", "logo_preview")}),
    )

    class Media:
        css = {"all": ("skilllab/css/admin_international_course.css",)}
        js = ("skilllab/js/admin_international_course.js",)

    def delete_model(self, request, obj):
        obj.delete(hard_delete=True)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete(hard_delete=True)

    def _preview_html(self, obj, field_name):
        if not obj or not obj.pk:
            return "-"
        url = obj.get_image_url() if field_name == "image" else obj.get_logo_url()
        max_height = "80px" if field_name == "image" else "48px"
        preview_id = f"intl-course-{field_name}-preview"
        return format_html(
            '<img id="{}" src="{}" data-preview-field="{}" '
            'style="max-height:{};max-width:160px;border:1px solid #ddd;border-radius:4px;padding:2px;" />',
            preview_id,
            url,
            field_name,
            max_height,
        )

    @admin.display(description="Image preview")
    def image_preview(self, obj):
        return self._preview_html(obj, "image")

    @admin.display(description="Logo preview")
    def logo_preview(self, obj):
        return self._preview_html(obj, "logo")


@admin.register(SkilllabCoursePayment)
class SkilllabCoursePaymentAdmin(SkillLabAdminMixin, admin.ModelAdmin):
    list_display = ["id", "user", "skilllab_course", "is_success", "object_status", "modified"]
    list_filter = ["is_success", "skilllab_course", "object_status"]
    search_fields = ["user__email", "skilllab_course__name"]
    list_editable = ["object_status"]
    raw_id_fields = ["user", "skilllab_course"]
