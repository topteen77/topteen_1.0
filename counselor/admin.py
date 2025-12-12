from django import forms
from django.contrib import admin
from counselor.models import Counselor
from institute.models import StudentManagement
from .models import FollowUpStatus

from django.contrib import admin
import nested_admin
from .models import CounselorCourse, Chapter, Part, Quiz, Question, QuizAnswers, QuizResults ,VideoProgress , Notes ,CounselorCertification

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
    fields = ('title', 'description', 'video_url', 'video_vtt', 'pdf_url')
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
# MAIN COURSE ADMIN - NESTED ADMIN
# ============================================================================

@admin.register(CounselorCourse)
class CourseAdmin(nested_admin.NestedModelAdmin):
    """Main admin for CounselorCourse with nested editing"""
    list_display = ('title', 'get_chapter_count', 'get_part_count', 'created_at', 'updated_at')
    search_fields = ('title',)
    list_filter = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    inlines = [ChapterInline]
    
    fieldsets = (
        ('Course Information', {
            'fields': ('title',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
    
    def get_chapter_count(self, obj):
        """Display number of chapters"""
        return obj.chapters.count()
    get_chapter_count.short_description = 'Chapters'
    get_chapter_count.admin_order_field = 'chapters__count'
    
    def get_part_count(self, obj):
        """Display total number of parts across all chapters"""
        total = 0
        for chapter in obj.chapters.all():
            total += chapter.parts.count()
        return total
    get_part_count.short_description = 'Total Parts'

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
            'fields': ('course', 'title')
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

@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    """Admin for Part model"""
    list_display = ('title', 'chapter', 'get_course', 'has_video', 'has_pdf', 'get_quiz_count')
    search_fields = ('title', 'chapter__title', 'chapter__course__title')
    list_filter = ('chapter__course', 'chapter')
    ordering = ('chapter__course', 'chapter', 'title')
    
    fieldsets = (
        ('Part Information', {
            'fields': ('chapter', 'title', 'description')
        }),
        ('Media Files', {
            'fields': ('video_url', 'video_vtt', 'pdf_url'),
            'description': 'Enter URLs for video, VTT subtitle file, and PDF resources.'
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
    list_display = ('id', 'user', 'part','video_timestamp', 'updated_at')
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
    list_display = ('counselor_name', 'counselor_email', 'counselor_admin', 'counselor_gender')
    search_fields = ('counselor_name', 'counselor_email', 'counselor_admin__username')
    list_filter = ('counselor_gender',)
    ordering = ('counselor_name',)


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
