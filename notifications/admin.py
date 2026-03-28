from django.contrib import admin

from .models import Notification, NotificationMessageTemplate, NotificationTypeConfig


@admin.register(NotificationTypeConfig)
class NotificationTypeConfigAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'category', 'enabled', 'requires_celery', 'requires_email', 'requires_redis', 'modified')
    list_filter = ('enabled', 'category', 'requires_celery', 'requires_email', 'requires_redis')
    search_fields = ('event_type', 'description')


@admin.register(NotificationMessageTemplate)
class NotificationMessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'is_active', 'modified')
    list_filter = ('is_active',)
    search_fields = ('event_type', 'title_template', 'body_template')
    readonly_fields = ('created', 'modified')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'environment', 'event_type', 'category', 'is_read', 'created')
    list_filter = ('environment', 'is_read', 'category', 'event_type', 'role_hint')
    search_fields = ('recipient__email', 'title', 'body', 'event_type')
    date_hierarchy = 'created'
    autocomplete_fields = ('recipient',)

    def delete_model(self, request, obj):
        """Always hard-delete the row from the database."""
        obj.delete()

    def delete_queryset(self, request, queryset):
        """Bulk admin delete: SQL DELETE, not soft-hide."""
        queryset.delete()

