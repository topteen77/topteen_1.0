from django.contrib import admin
from institute.models import Institute,StudentManagement,InstituteAccountDeletion,InstituteLog,ClassAndSection,InstituteGroup,InstituteMarketingGroup
from users.models import User
from core import choices
# Register your models here.

class UserStatusFilter(admin.SimpleListFilter):
    """Filter marketing groups by user status (active/inactive)"""
    title = 'user status'
    parameter_name = 'user_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active Users'),
            ('inactive', 'Inactive Users'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(marketing_group_admin__user_status=choices.UserStatus.UNBLOCK)
        elif self.value() == 'inactive':
            return queryset.filter(marketing_group_admin__user_status=choices.UserStatus.BLOCK)
        return queryset

class InstituteMarketingGroupAdmin(admin.ModelAdmin):
    list_display=["id","m_group_name","marketing_group_admin","get_object_status","get_user_status","get_user_email","created","modified"]
    readonly_fields=["created","modified"]
    list_filter=[UserStatusFilter,"object_status","created","modified"]
    search_fields=["m_group_name","marketing_group_admin__email","marketing_group_admin__name"]
    
    def get_queryset(self, request):
        # Show all marketing groups including those with inactive users
        # Use complete() to show all marketing groups (not just active ones)
        qs = InstituteMarketingGroup.objects.complete()
        # Also ensure we get users from complete queryset (including soft-deleted)
        return qs.select_related('marketing_group_admin')
    
    def get_object_status(self, obj):
        """Display the object_status of the marketing group itself"""
        # ObjectStatus: DELETED=0, ACTIVE=1, INACTIVE=2
        if obj.object_status == choices.ObjectStatus.ACTIVE:
            return "Active"
        elif obj.object_status == choices.ObjectStatus.INACTIVE:
            return "Inactive"
        elif obj.object_status == choices.ObjectStatus.DELETED:
            return "Deleted"
        else:
            return f"Unknown ({obj.object_status})"
    get_object_status.short_description = "Group Status"
    get_object_status.admin_order_field = "object_status"
    
    def get_user_status(self, obj):
        """Display the status of the marketing group admin user"""
        if obj.marketing_group_admin:
            # Get fresh user from complete queryset to avoid caching issues
            try:
                user = User.objects.complete().get(id=obj.marketing_group_admin.id)
                user_status = user.user_status
                # UserStatus.BLOCK = 1 (inactive), UserStatus.UNBLOCK = 2 (active)
                if user_status == choices.UserStatus.UNBLOCK:  # 2 = Active
                    return "Active"
                elif user_status == choices.UserStatus.BLOCK:  # 1 = Inactive
                    return "Inactive"
                else:
                    # Handle any unexpected values
                    return f"Unknown ({user_status})"
            except User.DoesNotExist:
                return "User Not Found"
        return "No User"
    get_user_status.short_description = "User Status"
    get_user_status.admin_order_field = "marketing_group_admin__user_status"
    
    
    def get_user_email(self, obj):
        """Display the email of the marketing group admin user"""
        if obj.marketing_group_admin:
            return obj.marketing_group_admin.email
        return "N/A"
    get_user_email.short_description = "User Email"
    get_user_email.admin_order_field = "marketing_group_admin__email"
    
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