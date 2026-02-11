from django.contrib import admin
from .models import (
    OlympiadExam,
    OlympiadQuestion,
    OlympiadExamQuestionSet,
    OlympiadRegistration,
    OlympiadSession,
    OlympiadResponse,
)


@admin.register(OlympiadExam)
class OlympiadExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'class_level', 'exam_date', 'duration_minutes', 'total_marks', 'status', 'is_published')
    list_filter = ('level', 'status', 'is_published')
    search_fields = ('name',)
    date_hierarchy = 'exam_date'


@admin.register(OlympiadQuestion)
class OlympiadQuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'question_type', 'difficulty', 'marks', 'topic', 'order', 'exam', 'correct_answer_display')
    list_filter = ('question_type', 'difficulty', 'exam')
    search_fields = ('topic', 'syllabus_section')

    @admin.display(description='Correct answer')
    def correct_answer_display(self, obj):
        if obj.correct_answer is None:
            return '—'
        if isinstance(obj.correct_answer, dict):
            return obj.correct_answer.get('option_id', str(obj.correct_answer))
        return str(obj.correct_answer)


class OlympiadExamQuestionSetInline(admin.TabularInline):
    model = OlympiadExamQuestionSet
    extra = 0
    raw_id_fields = ('question',)


@admin.register(OlympiadRegistration)
class OlympiadRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'registration_type', 'payment_status', 'registered_at')
    list_filter = ('payment_status', 'registration_type')
    raw_id_fields = ('user', 'exam')


@admin.register(OlympiadSession)
class OlympiadSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'status', 'started_at', 'ended_at', 'total_marks_awarded')
    list_filter = ('status',)
    raw_id_fields = ('user', 'exam')


@admin.register(OlympiadResponse)
class OlympiadResponseAdmin(admin.ModelAdmin):
    list_display = ('session', 'question', 'marks_awarded', 'auto_scored', 'submitted_at')
    raw_id_fields = ('session', 'question')
