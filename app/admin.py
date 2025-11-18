# quiz/admin.py

from django.contrib import admin
from .models import Question, TestCompletion, Answer, Results

from django.contrib.auth import get_user_model
User = get_user_model()

# Customizing the display of the Results model in the admin panel
class ResultsAdmin(admin.ModelAdmin):
    list_display = ('user', 'test_paper', 'formatted_scores', 'formatted_results', 'modified')
    list_filter = ('test_paper', 'modified')
    search_fields = ('user__email', 'test_paper')  # Changed to search by email
    # If you want to search by both email and name, you can add multiple fields:
    # search_fields = ('user__email', 'user__first_name', 'user__last_name', 'test_paper')

    def formatted_scores(self, obj):
        return ', '.join([f"{key}: {value}" for key, value in obj.scores.items()])
    formatted_scores.short_description = 'Scores'

    def formatted_results(self, obj):
        return ', '.join([f"{key}: {value}" for key, value in obj.results.items()])
    formatted_results.short_description = 'Results'
# from users.models import UserProfile

# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'grade', 'schoolname', 'gender')  # Adjust the fields as per your model
#     search_fields = ('user__username', 'gender')  # Use double underscores for related fields
#     list_filter = ('grade', 'college')

# admin.site.register(UserProfile, UserProfileAdmin)

# Registering the models in the admin panel
admin.site.register(Results, ResultsAdmin)

class AnswerAdmin(admin.StackedInline):
    model = Answer

class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerAdmin]
    list_filter = ['category']
from .models import Category, Course, Stream

class CourseInline(admin.TabularInline):
    model = Course
    extra = 1

class StreamInline(admin.TabularInline):
    model = Stream
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = [CourseInline, StreamInline]

admin.site.register(Course)
admin.site.register(Stream)

admin.site.register(Question, QuestionAdmin)
admin.site.register(Answer)
# admin.site.register(Results)


class TestCompletionAdmin(admin.ModelAdmin):
    # Specify the fields that you want to be searchable
    search_fields = ['user__email']  # Assuming your TestCompletion model has a ForeignKey to the User model

admin.site.register(TestCompletion, TestCompletionAdmin)
