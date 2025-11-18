from django.contrib import admin
from .models import (
    TestCategory, Test, Question, Answer, Sections,SectionSession,
    TestSession, UserResponse, TestResult, TestTopCategories
)


@admin.register(TestTopCategories)
class TestTopCategoriesAdmin(admin.ModelAdmin):
    list_display = ('user', 'test_paper', 'high_category', 'low_category')
    search_fields = ('user__email','user__name', 'high_category', 'low_category')
    list_filter = ('high_category', 'low_category')

@admin.register(SectionSession)
class SectionSessionAdmin(admin.ModelAdmin):
    list_display = ('session', 'section', 'start_time', 'end_time', 'is_completed')
    list_filter = ('section', 'is_completed')
    search_fields = ('session__user__email','session__user__name', 'section__title')
    ordering = ('-start_time',)

@admin.register(Sections)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'test', 'order', 'time_limit', 'created_at')
    list_filter = ('test',)
    search_fields = ('title', 'test__title')
    ordering = ('test', 'order')


@admin.register(TestCategory)
class TestCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'updated_at')


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('text', 'order', 'question_type', 'question_dimension', 'question_level')


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'time_limit', 'is_active', 'created_at', 'updated_at')
    list_filter = ('category', 'is_active', 'created_at', 'updated_at')
    search_fields = ('title', 'description')
    inlines = [QuestionInline]


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    fields = ('text', 'is_correct', 'score', 'category')  # Updated: Use 'category' instead of 'categories'

# To check the section question
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'test', 'section', 'order', 'question_type', 'question_dimension', 'question_level')
    list_filter = ('section', 'test', 'question_type', 'question_level', 'question_dimension')
    search_fields = ('text', 'test__title', 'section__title')
    ordering = ('test', 'section', 'order')

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('question', 'text', 'is_correct', 'score', 'category')
    list_filter = (
        'question__section',
        'question__test',
        'question__question_type',
        'question__question_level',
        'question__question_dimension',
    )
    search_fields = ('text', 'question__text')


# @admin.register(Question)
# class QuestionAdmin(admin.ModelAdmin):
#     list_display = ('text', 'test', 'question_type', 'order', 'question_dimension', 'question_level', 'created_at', 'updated_at')
#     list_filter = ('test', 'question_type', 'question_dimension', 'question_level', 'created_at', 'updated_at')
#     search_fields = ('text',)
#     inlines = [AnswerInline]


# @admin.register(Answer)
# class AnswerAdmin(admin.ModelAdmin):
#     list_display = ('text', 'question', 'is_correct', 'score', 'category', 'created_at', 'updated_at')  # Updated: Use 'category'
#     list_filter = ('question__test', 'is_correct', 'category', 'created_at', 'updated_at')  # Updated: Use 'category'
#     search_fields = ('text',)


@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'test', 'start_time', 'end_time', 'is_completed', 'created_at', 'updated_at')
    list_filter = ('test', 'is_completed', 'start_time', 'end_time', 'created_at', 'updated_at')
    search_fields = ('user__email','user__name', 'test__title')


@admin.register(UserResponse)
class UserResponseAdmin(admin.ModelAdmin):
    list_display = ('session', 'get_answers_summary', 'created_at', 'updated_at')
    list_filter = ('session__test', 'created_at', 'updated_at')
    search_fields = ('session__user__email','session__user__name', 'session__test__title')

    def get_answers_summary(self, obj):
        """Return a summary of the JSON answers"""
        if obj.selected_answer:
            # Count the number of answers in the JSON
            answer_count = len(obj.selected_answer.get('submitted_answers', {}))
            return f"{answer_count} answers submitted"
        return "No answers"
    get_answers_summary.short_description = 'Answers Summary'


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('session', 'score', 'grade', 'get_category_counts', 'created_at', 'updated_at')
    list_filter = ('session__test', 'grade', 'created_at', 'updated_at')
    search_fields = ('session__user__email','session__user__name', 'feedback', 'session__test__title')

    def get_category_counts(self, obj):
        """Display category counts as a formatted string"""
        if obj.category_counts:
            return ", ".join([f"{key}: {value}" for key, value in obj.category_counts.items()])
        return "No category counts"
    get_category_counts.short_description = 'Category Counts'