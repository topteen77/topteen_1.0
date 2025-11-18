from django import forms
from django.contrib import admin
from counselor.models import Counselor
from institute.models import StudentManagement
from .models import FollowUpStatus

from django.contrib import admin
# from .models import Chapter, Part, Quiz, Question, QuizAnswers, QuizResults
# import nested_admin

# class QuizAnswersInline(nested_admin.NestedTabularInline):
#     model = QuizAnswers
#     fields = ('answer_text', 'is_correct')
#     extra = 1  # Number of extra blank answer rows

# class QuestionInline(nested_admin.NestedStackedInline):
#     model = Question
#     fields = ('question_text',)
#     extra = 1  # Number of extra blank question rows
#     inlines = [QuizAnswersInline]  # Nest QuizAnswersInline inside QuestionInline

# class QuizAdmin(nested_admin.NestedModelAdmin):
#     list_display = ('title', 'quiz_part')
#     inlines = [QuestionInline]    # Add questions inline to Quiz admin


# # Admin for Parts
# class PartAdmin(admin.ModelAdmin):
#     list_display = ('title', 'chapter', 'video_url', 'pdf_url')
#     search_fields = ('title',)
#     list_filter = ('chapter',)
#     ordering = ('title',)

# # Admin for Chapters
# class ChapterAdmin(admin.ModelAdmin):
#     list_display = ('title', 'description')
#     search_fields = ('title',)

# # QuizResults Admin
# @admin.register(QuizResults)
# class QuizResultsAdmin(admin.ModelAdmin):
#     list_display = ('user', 'modified', 'scores')
#     list_filter = ('modified', 'user')
#     search_fields = ('user__username', 'user__email')

#     # Optional: Display JSON data in a more readable format
#     def pretty_scores(self, obj):
#         import json
#         return json.dumps(obj.scores, indent=2)
    
#     pretty_scores.short_description = 'Scores (Pretty Format)'

# # Register models with the admin interface
# admin.site.register(Chapter, ChapterAdmin)
# admin.site.register(Part, PartAdmin)
# admin.site.register(Quiz, QuizAdmin)  # QuizAdmin now includes questions and answers inline
# admin.site.register(UserQuizAttempt, UserQuizAttemptAdmin)



# from .models import Chapter, Part, Quiz

# @admin.register(Chapter)
# class ChapterAdmin(admin.ModelAdmin):
#     list_display = ('id', 'title')

# @admin.register(Part)
# class PartAdmin(admin.ModelAdmin):
#     list_display = ('id', 'title', 'chapter')

# @admin.register(Quiz)
# class QuizAdmin(admin.ModelAdmin):
#     list_display = ('id', 'question', 'part', 'correct_option', 'attempts_left')


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
