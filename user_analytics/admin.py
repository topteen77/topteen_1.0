"""
Django Admin integration for user_analytics models.
All analytics models use hard delete in admin so admins can permanently remove data.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from .models import UserActivity, Lead, UserEvent, UserJourney, AnalyticsCache, EnquirySource


def hard_delete_queryset(model_admin, request, queryset):
    """Permanently delete selected objects (for models that inherit BaseModel soft-delete)."""
    for obj in queryset:
        if hasattr(obj, 'delete') and callable(getattr(obj, 'delete')):
            obj.delete(hard_delete=True)
        else:
            obj.delete()


class UserAnalyticsHardDeleteMixin:
    """Mixin so admin 'Delete selected' and single-object delete do hard delete for user_analytics models."""

    def delete_queryset(self, request, queryset):
        hard_delete_queryset(self, request, queryset)

    def delete_model(self, request, obj):
        if hasattr(obj, 'delete') and callable(getattr(obj, 'delete')):
            obj.delete(hard_delete=True)
        else:
            obj.delete()


class ReferrerSourceFilter(admin.SimpleListFilter):
    """One-click filter: Google, Facebook, iapply.io (by utm_source or referrer)."""
    title = 'Referrer source'
    parameter_name = 'referrer_source'

    def lookups(self, request, model_admin):
        return (
            ('google', 'Google'),
            ('facebook', 'Facebook'),
            ('iapply', 'iapply.io'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'google':
            return queryset.filter(Q(utm_source__iexact='google') | Q(referrer__icontains='google'))
        if self.value() == 'facebook':
            return queryset.filter(Q(utm_source__iexact='facebook') | Q(referrer__icontains='facebook'))
        if self.value() == 'iapply':
            return queryset.filter(Q(utm_source__iexact='iapply') | Q(referrer__icontains='iapply.io'))
        return queryset


class URLTypeFilter(admin.SimpleListFilter):
    """Filter by URL type: Local (localhost/test) vs Production/Other. Use to bulk-delete test data."""
    title = 'URL type'
    parameter_name = 'url_type'

    def lookups(self, request, model_admin):
        return (
            ('local', 'Local (localhost, 127.0.0.1, test)'),
            ('production', 'Production / other (e.g. topteen.in)'),
            ('no_url', 'No URL stored (old records)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'local':
            return queryset.filter(
                Q(page_url__icontains='localhost') |
                Q(page_url__icontains='127.0.0.1') |
                Q(page_url__icontains='testserver') |
                Q(page_path__istartswith='/ref-landing/')
            )
        if self.value() == 'production':
            return queryset.filter(page_url__icontains='topteen.in').exclude(page_url__isnull=True).exclude(page_url='')
        if self.value() == 'no_url':
            return queryset.filter(Q(page_url__isnull=True) | Q(page_url=''))
        return queryset


@admin.register(UserActivity)
class UserActivityAdmin(UserAnalyticsHardDeleteMixin, admin.ModelAdmin):
    list_display = ['id', 'user_link', 'page_url_display', 'page_path', 'device_type', 'utm_source', 'traffic_source_category', 'country', 'city', 'created']
    list_filter = [URLTypeFilter, ReferrerSourceFilter, 'device_type', 'utm_source', 'utm_medium', 'traffic_source_category', 'created', 'country']
    search_fields = ['page_path', 'page_title', 'page_url', 'user__email', 'session_id', 'referrer', 'utm_source']
    readonly_fields = ['created', 'modified', 'page_url']
    date_hierarchy = 'created'
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return 'Anonymous'
    user_link.short_description = 'User'

    def page_url_display(self, obj):
        if obj.page_url:
            return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.page_url, obj.page_url[:60] + ('...' if len(obj.page_url) > 60 else ''))
        return obj.page_path or '—'
    page_url_display.short_description = 'URL'
    
    class Meta:
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"


@admin.register(Lead)
class LeadAdmin(UserAnalyticsHardDeleteMixin, admin.ModelAdmin):
    list_display = ['email', 'name', 'source', 'medium', 'is_converted', 'first_visit', 'visit_count']
    list_filter = ['is_converted', 'source', 'medium', 'first_visit']
    search_fields = ['email', 'name', 'phone', 'source']
    readonly_fields = ['first_visit', 'last_visit', 'visit_count']
    date_hierarchy = 'first_visit'
    
    fieldsets = (
        ('Lead Information', {
            'fields': ('email', 'name', 'phone', 'user')
        }),
        ('Source Attribution', {
            'fields': ('source', 'medium', 'campaign', 'referrer', 'landing_page')
        }),
        ('Conversion', {
            'fields': ('is_converted', 'converted_at', 'conversion_value')
        }),
        ('Visit Statistics', {
            'fields': ('first_visit', 'last_visit', 'visit_count')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"


@admin.register(UserEvent)
class UserEventAdmin(UserAnalyticsHardDeleteMixin, admin.ModelAdmin):
    list_display = ['id', 'user_link', 'event_type', 'event_name', 'event_value', 'created']
    list_filter = ['event_type', 'created']
    search_fields = ['event_name', 'user__email', 'session_id']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'created'
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return 'Anonymous'
    user_link.short_description = 'User'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('user', 'event_type', 'event_name', 'event_value')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id', 'content_object')
        }),
        ('Metadata', {
            'fields': ('metadata', 'session_id', 'ip_address', 'user_agent')
        }),
        ('Timestamps', {
            'fields': ('created', 'modified')
        }),
    )
    
    class Meta:
        verbose_name = "User Event"
        verbose_name_plural = "User Events"


class JourneyReferrerSourceFilter(admin.SimpleListFilter):
    """One-click filter: Google, Facebook, iapply.io (by utm_source or referrer)."""
    title = 'Referrer source'
    parameter_name = 'referrer_source'

    def lookups(self, request, model_admin):
        return (
            ('google', 'Google'),
            ('facebook', 'Facebook'),
            ('iapply', 'iapply.io'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'google':
            return queryset.filter(Q(utm_source__iexact='google') | Q(referrer__icontains='google'))
        if self.value() == 'facebook':
            return queryset.filter(Q(utm_source__iexact='facebook') | Q(referrer__icontains='facebook'))
        if self.value() == 'iapply':
            return queryset.filter(Q(utm_source__iexact='iapply') | Q(referrer__icontains='iapply.io'))
        return queryset


@admin.register(UserJourney)
class UserJourneyAdmin(UserAnalyticsHardDeleteMixin, admin.ModelAdmin):
    list_display = ['session_id', 'user_link', 'start_time', 'total_pages', 'total_time', 'device_type', 'utm_source', 'traffic_source_category', 'country', 'converted']
    list_filter = [JourneyReferrerSourceFilter, 'converted', 'device_type', 'utm_source', 'traffic_source_category', 'start_time']
    search_fields = ['session_id', 'user__email', 'entry_page', 'referrer', 'utm_source']
    readonly_fields = ['start_time', 'end_time', 'total_pages', 'total_time']
    date_hierarchy = 'start_time'
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return 'Anonymous'
    user_link.short_description = 'User'
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_id', 'start_time', 'end_time')
        }),
        ('Journey Details', {
            'fields': ('entry_page', 'exit_page', 'total_pages', 'total_time', 'journey_path')
        }),
        ('Source Attribution', {
            'fields': ('referrer', 'utm_source', 'utm_medium', 'utm_campaign', 'traffic_source_category')
        }),
        ('Conversion', {
            'fields': ('converted', 'conversion_event')
        }),
        ('Device & Location', {
            'fields': ('device_type', 'country')
        }),
    )
    
    class Meta:
        verbose_name = "User Journey"
        verbose_name_plural = "User Journeys"


@admin.register(AnalyticsCache)
class AnalyticsCacheAdmin(UserAnalyticsHardDeleteMixin, admin.ModelAdmin):
    list_display = ['cache_key', 'cache_type', 'date_range_start', 'date_range_end', 'updated', 'expires_at']
    list_filter = ['cache_type', 'expires_at']
    search_fields = ['cache_key']
    readonly_fields = ['created', 'updated']
    date_hierarchy = 'date_range_start'
    
    class Meta:
        verbose_name = "Analytics Cache"
        verbose_name_plural = "Analytics Caches"


@admin.register(EnquirySource)
class EnquirySourceAdmin(UserAnalyticsHardDeleteMixin, admin.ModelAdmin):
    list_display = ['name', 'agency_name', 'user_name', 'event', 'token', 'is_active', 'created']
    list_filter = ['is_active', 'agency_name', 'created']
    search_fields = ['name', 'token', 'agency_name', 'user_name', 'event']
    readonly_fields = ['token', 'created', 'modified']
    list_editable = ['is_active']
