from django import forms
from django.contrib import admin
from counselor.models import Counselor
from institute.models import StudentManagement
from .models import FollowUpStatus

from django.contrib import admin
from django.contrib import admin
import nested_admin
from .models import CounselorCourse, Chapter, Part, Quiz, Question, QuizAnswers, QuizResults ,VideoProgress , Notes ,CounselorCertification

class QuizAnswersInline(nested_admin.NestedTabularInline):
    model = QuizAnswers
    fields = ('answer_text', 'is_correct')
    extra = 1

class QuestionInline(nested_admin.NestedStackedInline):
    model = Question
    fields = ('question_text',)
    extra = 1
    inlines = [QuizAnswersInline]

class QuizAdmin(nested_admin.NestedModelAdmin):
    list_display = ('title', 'quiz_part')
    inlines = [QuestionInline]

class PartAdmin(admin.ModelAdmin):
    list_display = ('title', 'chapter', 'video_url','video_vtt', 'pdf_url')
    fields = ('title', 'chapter', 'description', 'video_url','video_vtt', 'pdf_url')
    search_fields = ('title',)
    list_filter = ('chapter',)
    ordering = ('title',)

class ChapterInline(admin.StackedInline):
    model = Chapter
    extra = 1

@admin.register(CounselorCourse)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'updated_at')
    search_fields = ('title',)
    inlines = [ChapterInline]
    list_filter = ('created_at',)
    ordering = ('-created_at',)

class ChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'course')
    search_fields = ('title', 'course__title')
    list_filter = ('course',)

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

# Registering models
admin.site.register(Chapter, ChapterAdmin)
admin.site.register(Part, PartAdmin)
admin.site.register(Quiz, QuizAdmin)



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
