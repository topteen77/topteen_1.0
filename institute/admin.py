from django.contrib import admin
from institute.models import Institute,StudentManagement,InstituteAccountDeletion,InstituteLog,ClassAndSection,InstituteGroup,InstituteMarketingGroup
# Register your models here.

class InstituteMarketingGroupAdmin(admin.ModelAdmin):
    list_display=["id","m_group_name","marketing_group_admin"]
    readonly_fields=["created","modified"]
admin.site.register(InstituteMarketingGroup,InstituteMarketingGroupAdmin)

class InstituteAdmin(admin.ModelAdmin):
    list_display=["name","created_by","logo"]
    readonly_fields=["created","modified","slug"]

admin.site.register(Institute,InstituteAdmin)

class ClassAndSectionAdmin(admin.ModelAdmin):
    list_display = ["class_and_section", "stream"]
    readonly_fields = ["created", "modified"]
    search_fields = ["class_and_section", "stream"]
    list_filter = ["stream"]
    ordering = ["class_and_section"]
    
admin.site.register(ClassAndSection,ClassAndSectionAdmin)

class StudentManagementAdmin(admin.ModelAdmin):
    list_display=["institute","student","class_and_section"]
    readonly_fields=["created","modified"]
    
admin.site.register(StudentManagement,StudentManagementAdmin)

class InstituteAccountDeletionAdmin(admin.ModelAdmin):
    list_display=["institute","reason"]
    readonly_fields=["created","modified"]
    
admin.site.register(InstituteAccountDeletion,InstituteAccountDeletionAdmin)

class InstituteLogAdmin(admin.ModelAdmin):
    list_display=["institute","email","students_counts"]
    readonly_fields=["created","modified"]
    
admin.site.register(InstituteLog,InstituteLogAdmin)

class InstituteGroupAdmin(admin.ModelAdmin):
    list_display=["id","group_name","institute_group_admin"]
    readonly_fields=["created","modified"]

admin.site.register(InstituteGroup,InstituteGroupAdmin)