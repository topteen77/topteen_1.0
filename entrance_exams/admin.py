from django.contrib import admin
from .models import EntranceExam
# Register your models here.
class EntranceExamAdmin(admin.ModelAdmin):
    list_display = ['id','name','exam_pattern']
admin.site.register(EntranceExam,EntranceExamAdmin)