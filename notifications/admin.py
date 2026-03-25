from django.contrib import admin

from .models import Notification, NotificationTypeConfig


@admin.register(NotificationTypeConfig)
class NotificationTypeConfigAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'category', 'enabled', 'requires_celery', 'requires_email', 'requires_redis', 'modified')
    list_filter = ('enabled', 'category', 'requires_celery', 'requires_email', 'requires_redis')
    search_fields = ('event_type', 'description')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'event_type', 'category', 'is_read', 'created')
    list_filter = ('is_read', 'category', 'event_type', 'role_hint')
    search_fields = ('recipient__email', 'title', 'body', 'event_type')
    autocomplete_fields = ('recipient',)

