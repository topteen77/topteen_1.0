from django import forms
from django.contrib import admin, messages
from django.contrib.admin.decorators import action
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import format_html
from counselor.models import Counselor
from institute.models import StudentManagement
from .models import FollowUpStatus

import nested_admin
from .models import (
    CounselorCourse,
    Chapter,
    Part,
    CaseStudy,
    Quiz,
    Question,
    QuizAnswers,
    QuizResults,
    VideoProgress,
    Notes,
    CounselorCertification,
    CounselorCourseAttemptBackup,
)

# ============================================================================
# NESTED INLINE ADMIN FOR COURSE STRUCTURE
# ============================================================================

class QuizAnswersInline(nested_admin.NestedTabularInline):
    """Inline for quiz answers within questions"""
    model = QuizAnswers
    fields = ('answer_text', 'is_correct')
    extra = 2
    min_num = 2  # At least 2 answers per question
    verbose_name = "Answer"
    verbose_name_plural = "Answers"

class QuestionInline(nested_admin.NestedStackedInline):
    """Inline for questions within quizzes"""
    model = Question
    fields = ('question_text',)
    extra = 1
    inlines = [QuizAnswersInline]
    verbose_name = "Question"
    verbose_name_plural = "Questions"

class QuizInline(nested_admin.NestedStackedInline):
    """Inline for quizzes within parts"""
    model = Quiz
    fields = ('title',)
    extra = 0
    inlines = [QuestionInline]
    verbose_name = "Quiz"
    verbose_name_plural = "Quizzes"

class PartInline(nested_admin.NestedStackedInline):
    """Inline for parts within chapters"""
    model = Part
    fields = (
        'title',
        'description',
        'video_url',
        'video_vtt',
        'pdf_url',
        'case_study_folder_url',
        'suppress_pdf_notes_tab',
    )
    extra = 1
    inlines = [QuizInline]
    verbose_name = "Part"
    verbose_name_plural = "Parts"

class ChapterInline(nested_admin.NestedStackedInline):
    """Inline for chapters within courses"""
    model = Chapter
    fields = ('title',)
    extra = 1
    inlines = [PartInline]
    verbose_name = "Chapter"
    verbose_name_plural = "Chapters"

# ============================================================================
# COURSE ADMIN — list edits, linked counts, change form = course + pricing only
# ============================================================================

class CounselorCourseAdminForm(forms.ModelForm):
    class Meta:
        model = CounselorCourse
        fields = '__all__'


@admin.register(CounselorCourse)
class CourseAdmin(admin.ModelAdmin):
    form = CounselorCourseAdminForm
    class Media:
        js = ('counselor/js/admin_counselor_course_pricing.js',)

    list_display = (
        'id',
        'title',
        'currency',
        'actual_price',
        'discount_percent',
        'get_discounted_price_list',
        'get_chapter_count_link',
        'get_part_count_link',
        'created_at',
        'updated_at',
    )
    list_display_links = ('title',)
    search_fields = ('title',)
    list_filter = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    inlines = []

    fieldsets = (
        ('Course', {'fields': ('title',)}),
        (
            'Pricing',
            {
                'fields': (
                    'currency',
                    'actual_price',
                    'discount_percent',
                    'amount',
                    'dynamic_price',
                    'checkout_price_help',
                ),
                'description': 'Discount defaults to 0; price is calculated from MRP. Increase discount % to lower price. Dynamic price is optional.',
            },
        ),
        (
            'Timestamps',
            {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    )
    readonly_fields = ('created_at', 'updated_at', 'checkout_price_help')

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        ro.append('amount')
        return ro

    @admin.display(description='Price (calculated)', ordering='amount')
    def get_discounted_price_list(self, obj):
        return obj.amount

    @admin.display(description='Checkout')
    def checkout_price_help(self, obj):
        # Spans updated live by static/counselor/js/admin_counselor_course_pricing.js
        if obj.pk:
            sym = obj.get_currency_symbol()
            amt = obj.get_charge_amount_rupees()
        else:
            sym = '₹'
            amt = '—'
        return format_html(
            '<p class="counselor-checkout-preview">'
            '<strong>Charged at checkout:</strong> '
            '<span id="counselor-checkout-symbol">{}</span> '
            '<span id="counselor-checkout-value">{}</span> '
            '(dynamic price if set, otherwise calculated price).'
            '</p>',
            sym,
            amt,
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _chapter_count=Count('chapters', distinct=True),
            _part_count=Count('chapters__parts', distinct=True),
        )

    @admin.display(description='Chapters', ordering='_chapter_count')
    def get_chapter_count_link(self, obj):
        n = getattr(obj, '_chapter_count', None)
        if n is None:
            n = obj.chapters.count()
        url = '{}?course__id__exact={}'.format(
            reverse('admin:counselor_chapter_changelist'),
            obj.pk,
        )
        return format_html('<a href="{}">{}</a>', url, n)

    @admin.display(description='Total parts', ordering='_part_count')
    def get_part_count_link(self, obj):
        n = getattr(obj, '_part_count', None)
        if n is None:
            n = sum(ch.parts.count() for ch in obj.chapters.all())
        url = '{}?chapter__course__id__exact={}'.format(
            reverse('admin:counselor_part_changelist'),
            obj.pk,
        )
        return format_html('<a href="{}">{}</a>', url, n)

# ============================================================================
# INDIVIDUAL MODEL ADMINS (for standalone editing)
# ============================================================================

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    """Admin for Chapter model"""
    list_display = ('title', 'course', 'get_part_count', 'get_quiz_count')
    search_fields = ('title', 'course__title')
    list_filter = ('course',)
    ordering = ('course', 'title')

    fieldsets = (
        ('Chapter Information', {
            'fields': ('course', 'title'),
            'description': (
                'Chapter mindmap: add static/counselor/mindmaps/chapter_<this chapter id>.json when needed. '
                'If the file exists and counselor course mindmaps are enabled (Core website settings), a mindmap icon appears on the chapter row in course learning.'
            ),
        }),
    )
    
    def get_part_count(self, obj):
        return obj.parts.count()
    get_part_count.short_description = 'Parts'
    
    def get_quiz_count(self, obj):
        total = 0
        for part in obj.parts.all():
            total += part.quizzes.count()
        return total
    get_quiz_count.short_description = 'Quizzes'

class CaseStudyInline(admin.TabularInline):
    model = CaseStudy
    extra = 0
    fields = ('title', 'pdf_url', 'sort_order')
    ordering = ('sort_order', 'id')


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    """Admin for Part model"""
    list_display = (
        'title',
        'chapter',
        'get_course',
        'has_video',
        'has_pdf',
        'get_case_study_count',
        'get_quiz_count',
    )
    search_fields = ('title', 'chapter__title', 'chapter__course__title')
    list_filter = ('chapter__course', 'chapter')
    ordering = ('chapter__course', 'chapter', 'title')
    inlines = [CaseStudyInline]

    fieldsets = (
        ('Part Information', {
            'fields': ('chapter', 'title', 'description')
        }),
        ('Media Files', {
            'fields': ('video_url', 'video_vtt', 'pdf_url'),
            'description': 'Enter URLs for video, VTT subtitle file, and lesson PDF (optional).',
        }),
        ('Case studies', {
            'fields': ('case_study_folder_url', 'suppress_pdf_notes_tab'),
            'description': (
                'Optional folder URL (project or S3 prefix) used when each Case Study row uses a relative filename only. '
                'Add rows below. When case studies exist or “Suppress PDF notes tab” is checked, the PDF Notes tab can be hidden. '
                'Part mindmap: add static/counselor/mindmaps/part_<this part id>.json with {"markdown": "# ..."}; the Mindmap tab '
                'and sidebar icon appear when the file exists and counselor mindmaps are enabled in Core website settings.'
            ),
        }),
    )
    
    def get_course(self, obj):
        return obj.chapter.course.title if obj.chapter and obj.chapter.course else '-'
    get_course.short_description = 'Course'
    get_course.admin_order_field = 'chapter__course__title'
    
    def has_video(self, obj):
        return bool(obj.video_url)
    has_video.boolean = True
    has_video.short_description = 'Has Video'
    
    def has_pdf(self, obj):
        return bool(obj.pdf_url)
    has_pdf.boolean = True
    has_pdf.short_description = 'Has PDF'
    
    def get_quiz_count(self, obj):
        return obj.quizzes.count()
    get_quiz_count.short_description = 'Quizzes'

    @admin.display(description='Case studies')
    def get_case_study_count(self, obj):
        n = obj.case_studies.count()
        if n == 0:
            return '—'
        url = reverse('admin:counselor_casestudy_changelist') + f'?part__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, n)

@admin.register(CaseStudy)
class CaseStudyAdmin(admin.ModelAdmin):
    list_display = ('title', 'part', 'get_chapter', 'sort_order', 'pdf_url_short')
    list_filter = ('part__chapter__course', 'part__chapter')
    search_fields = ('title', 'pdf_url', 'part__title')
    ordering = ('part__chapter', 'part', 'sort_order', 'id')
    raw_id_fields = ('part',)

    fieldsets = (
        (None, {'fields': ('part', 'title', 'pdf_url', 'sort_order')}),
    )

    @admin.display(description='Chapter')
    def get_chapter(self, obj):
        if obj.part and obj.part.chapter:
            return obj.part.chapter.title
        return '—'

    @admin.display(description='PDF')
    def pdf_url_short(self, obj):
        s = (obj.pdf_url or '')[:80]
        return s + ('…' if len(obj.pdf_url or '') > 80 else '')

@admin.register(Quiz)
class QuizAdmin(nested_admin.NestedModelAdmin):
    """Admin for Quiz model with nested questions and answers"""
    list_display = ('title', 'quiz_part', 'get_course', 'get_question_count')
    search_fields = ('title', 'quiz_part__title', 'quiz_part__chapter__course__title')
    list_filter = ('quiz_part__chapter__course', 'quiz_part__chapter')
    ordering = ('quiz_part__chapter__course', 'quiz_part__chapter', 'title')
    inlines = [QuestionInline]
    
    fieldsets = (
        ('Quiz Information', {
            'fields': ('quiz_part', 'title')
        }),
    )
    
    def get_course(self, obj):
        if obj.quiz_part and obj.quiz_part.chapter:
            return obj.quiz_part.chapter.course.title
        return '-'
    get_course.short_description = 'Course'
    
    def get_question_count(self, obj):
        return obj.questions.count()
    get_question_count.short_description = 'Questions'

@admin.register(Question)
class QuestionAdmin(nested_admin.NestedModelAdmin):
    """Admin for Question model with nested answers"""
    list_display = ('get_question_preview', 'quiz', 'get_course', 'get_answer_count', 'get_correct_answer')
    search_fields = ('question_text', 'quiz__title')
    list_filter = ('quiz__quiz_part__chapter__course',)
    ordering = ('quiz__quiz_part__chapter__course', 'quiz', 'id')
    inlines = [QuizAnswersInline]
    
    fieldsets = (
        ('Question Information', {
            'fields': ('quiz', 'question_text')
        }),
    )
    
    def get_question_preview(self, obj):
        if obj.question_text:
            return obj.question_text[:100] + '...' if len(obj.question_text) > 100 else obj.question_text
        return '-'
    get_question_preview.short_description = 'Question'
    
    def get_course(self, obj):
        if obj.quiz and obj.quiz.quiz_part and obj.quiz.quiz_part.chapter:
            return obj.quiz.quiz_part.chapter.course.title
        return '-'
    get_course.short_description = 'Course'
    
    def get_answer_count(self, obj):
        return obj.answers.count()
    get_answer_count.short_description = 'Answers'
    
    def get_correct_answer(self, obj):
        correct = obj.answers.filter(is_correct=True).first()
        return correct.answer_text if correct else 'None'
    get_correct_answer.short_description = 'Correct Answer'

@admin.register(QuizAnswers)
class QuizAnswersAdmin(admin.ModelAdmin):
    """Admin for QuizAnswers model"""
    list_display = ('answer_text', 'question', 'is_correct', 'get_course')
    search_fields = ('answer_text', 'question__question_text')
    list_filter = ('is_correct', 'question__quiz__quiz_part__chapter__course')
    ordering = ('question__quiz__quiz_part__chapter__course', 'question', 'id')
    
    fieldsets = (
        ('Answer Information', {
            'fields': ('question', 'answer_text', 'is_correct')
        }),
    )
    
    def get_course(self, obj):
        if obj.question and obj.question.quiz and obj.question.quiz.quiz_part and obj.question.quiz.quiz_part.chapter:
            return obj.question.quiz.quiz_part.chapter.course.title
        return '-'
    get_course.short_description = 'Course'

@admin.register(QuizResults)
class QuizResultsAdmin(admin.ModelAdmin):
    list_display = ('user', 'modified', 'scores')
    list_filter = ('modified', 'user')
    search_fields = ('user__username', 'user__email')

    def pretty_scores(self, obj):
        import json
        return json.dumps(obj.scores, indent=2)
    
    pretty_scores.short_description = 'Scores (Pretty Format)'

@admin.register(VideoProgress)
class VideoProgressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'video_id', 'progress', 'completed', 'duration')
    search_fields = ('video_id',)
    ordering = ('video_id',)

@admin.register(Notes)
class NotesAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'part', 'video_timestamp', 'video_end_timestamp', 'updated_at')
    list_filter = ('video_timestamp', 'updated_at')

class CounselorCertificationAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = ('user', 'certificate_code', 'grade', 'created_at')
    
    # Fields to search in the admin search bar
    search_fields = ('user__username', 'certificate_code', 'grade')
    
    # Filters to apply in the sidebar
    list_filter = ('grade', 'created_at')
    
    # Fields to display in the detail view form
    fields = ('user', 'certificate_code', 'grade', 'created_at')
    
    # Make 'created_at' field readonly
    readonly_fields = ('created_at',)

# Register the model and its admin customization
admin.site.register(CounselorCertification, CounselorCertificationAdmin)


@admin.register(CounselorCourseAttemptBackup)
class CounselorCourseAttemptBackupAdmin(admin.ModelAdmin):
    """Audit trail for soft counselor course resets; restore reapplies snapshot to the user."""

    list_display = ("id", "user", "created_at", "created_by", "snapshot_preview")
    list_filter = ("created_at",)
    search_fields = ("user__email", "user__name", "user__id")
    readonly_fields = ("user", "snapshot", "created_at", "created_by")
    actions = ("restore_counselor_course_from_backup_action",)

    @action(
        description="Restore counselor course data from this backup (replaces current progress for that user)",
        permissions=["view"],
    )
    def restore_counselor_course_from_backup_action(self, request, queryset):
        from counselor.course_reset import restore_counselor_course_from_backup

        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers can restore backups.",
                messages.ERROR,
            )
            return
        if queryset.count() != 1:
            self.message_user(
                request,
                "Select exactly one backup to restore.",
                messages.ERROR,
            )
            return
        backup = queryset.first()
        try:
            result = restore_counselor_course_from_backup(backup, actor=request.user)
            if result.get("ok"):
                c = result.get("counts") or {}
                self.message_user(
                    request,
                    result.get("message", "Restored.")
                    + f" video={c.get('video_progress', 0)} notes={c.get('notes', 0)} "
                    f"quiz={c.get('quiz_results', 0)} cert={c.get('certifications', 0)}",
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    result.get("message", "Restore failed."),
                    messages.ERROR,
                )
        except Exception as ex:
            self.message_user(request, str(ex), messages.ERROR)

    def snapshot_preview(self, obj):
        snap = obj.snapshot or {}
        vp = len(snap.get("video_progress") or [])
        n = len(snap.get("notes") or [])
        q = 1 if snap.get("quiz_results") else 0
        c = len(snap.get("certifications") or [])
        return format_html(
            "video rows: {} · notes: {} · quiz: {} · certs: {}",
            vp,
            n,
            q,
            c,
        )

    snapshot_preview.short_description = "Snapshot summary"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

# Note: Chapter, Part, Quiz, Question, and QuizAnswers are already registered 
# using @admin.register decorators above



class CounselorAdminForm(forms.ModelForm):
    class Meta:
        model = Counselor
        fields = '__all__'  # Use all fields or specify which fields you want

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If the instance exists and has a counselor_admin (institute)
        if self.instance and self.instance.counselor_admin:
            # Filter the students based on the selected institute
            self.fields['students'].queryset = StudentManagement.objects.filter(
                institute=self.instance.counselor_admin
            )
        else:
            # Show all students or set an empty queryset if no institute is selected
            self.fields['students'].queryset = StudentManagement.objects.none()

@admin.register(Counselor)
class CounselorAdmin(admin.ModelAdmin):
    form = CounselorAdminForm
    list_display = (
        'counselor_name',
        'counselor_email',
        'counselor_admin',
        'counselor_gender',
        'linked_user_password_list_link',
    )
    search_fields = ('counselor_name', 'counselor_email', 'counselor_admin__username')
    list_filter = ('counselor_gender',)
    ordering = ('counselor_name',)
    actions = (
        'reset_counselor_course_soft_for_linked_user',
        'reset_counselor_course_hard_for_linked_user',
    )

    def get_fields(self, request, obj=None):
        f = list(super().get_fields(request, obj))
        if 'linked_user_password_reset' not in f:
            f.append('linked_user_password_reset')
        return f

    def get_readonly_fields(self, request, obj=None):
        return list(super().get_readonly_fields(request, obj)) + ['linked_user_password_reset']

    def linked_user_password_reset(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<span class="help">Save the counselor first, then use this button to set the linked user '
                'password (no old password required).</span>'
            )
        if not obj.coun_user_id:
            return format_html(
                '<span class="errors">No linked user account. Assign <strong>coun_user</strong> first.</span>'
            )
        User = get_user_model()
        url = reverse(
            'admin:%s_%s_set_password'
            % (User._meta.app_label, User._meta.model_name),
            args=[obj.coun_user_id],
        )
        label = obj.coun_user.email or ('user #%s' % obj.coun_user_id)
        return format_html(
            '<a class="button" href="{}" style="display:inline-block;padding:10px 15px;background:#417690;color:#fff;'
            'text-decoration:none;border-radius:4px;font-weight:600;">Set password for linked user</a>'
            '<p class="help" style="margin-top:8px;">Sets login password for <strong>{}</strong> without the old password.</p>',
            url,
            label,
        )

    linked_user_password_reset.short_description = 'Linked user password (admin)'

    def linked_user_password_list_link(self, obj):
        if not obj.coun_user_id:
            return '—'
        User = get_user_model()
        url = reverse(
            'admin:%s_%s_set_password'
            % (User._meta.app_label, User._meta.model_name),
            args=[obj.coun_user_id],
        )
        return format_html(
            '<a class="button" href="{}" style="display:inline-block;padding:4px 10px;background:#417690;'
            'color:#fff;text-decoration:none;border-radius:4px;font-size:12px;font-weight:600;">Set password</a>',
            url,
        )

    linked_user_password_list_link.short_description = 'Linked user password'
    linked_user_password_list_link.admin_order_field = None

    def _reset_counselors_linked_users(self, request, queryset, mode):
        from counselor.course_reset import reset_counselor_course_data_for_user

        if not request.user.is_superuser and not request.user.has_perm(
            'counselor.change_counselor'
        ):
            self.message_user(
                request,
                'You do not have permission to reset counselor course data.',
                messages.ERROR,
            )
            return
        lines = []
        ok_n = 0
        for c in queryset:
            if not c.coun_user:
                lines.append(f'{c.counselor_name}: no linked user')
                continue
            try:
                result = reset_counselor_course_data_for_user(
                    c.coun_user, mode=mode, actor=request.user
                )
                if result.get('ok'):
                    ok_n += 1
                    ct = result.get('counts') or {}
                    extra = ''
                    if mode == 'soft' and result.get('backup_id'):
                        extra = f" backup#{result.get('backup_id')}"
                    lines.append(
                        f'{c.counselor_name} ({c.coun_user.email}): '
                        f'video={ct.get("video_progress", 0)} notes={ct.get("notes", 0)} '
                        f'quiz={ct.get("quiz_results", 0)} cert={ct.get("certifications", 0)}'
                        f'{extra}'
                    )
                else:
                    lines.append(f'{c.counselor_name}: {result.get("message", "Failed")}')
            except Exception as ex:
                lines.append(f'{c.counselor_name}: {ex}')
        label = 'Soft reset (backup + clear)' if mode == 'soft' else 'Hard reset (no backup)'
        if ok_n:
            self.message_user(
                request,
                f'{label}: counselor course reset for {ok_n} linked user(s). '
                + (' | '.join(lines[:25]) if lines else ''),
                messages.SUCCESS,
            )
        elif lines:
            self.message_user(request, ' | '.join(lines), messages.WARNING)

    @action(
        description='Soft reset counselor course (backup snapshot, then clear; keeps payment)',
        permissions=['change'],
    )
    def reset_counselor_course_soft_for_linked_user(self, request, queryset):
        self._reset_counselors_linked_users(request, queryset, 'soft')

    @action(
        description='Hard reset counselor course (delete attempt data, no backup; keeps payment)',
        permissions=['change'],
    )
    def reset_counselor_course_hard_for_linked_user(self, request, queryset):
        self._reset_counselors_linked_users(request, queryset, 'hard')


# admin.py
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ('get_student_name', 'get_counselor_name', 'mode_of_follow_up')

    def get_student_name(self, obj):
        return obj.student.student.name if obj.student and obj.student.student else None
    get_student_name.short_description = 'Student'

    def get_counselor_name(self, obj):
        return obj.counselor.counselor_name if obj.counselor and obj.counselor else None
    get_counselor_name.short_description = 'Counselor'

admin.site.register(FollowUpStatus, FollowUpAdmin)
