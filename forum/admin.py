from django.contrib import admin
from django.utils.html import format_html
from forum.models import Query, Response, Category, Country, KnowledgeBaseEntry, PerformanceMetrics, AIFeature, AICapability


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order']
    list_editable = ['order']


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'flag_emoji']


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'category', 'country_context', 'status', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['question_text']


class StatusFilter(admin.SimpleListFilter):
    """Custom filter to show responses by status (error vs valid)"""
    title = 'Response Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return (
            ('error', '❌ Error Responses'),
            ('api_error', '🔑 API Key Errors'),
            ('domain_error', '🚫 Domain Boundary Errors'),
            ('valid', '✅ Valid Responses'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'error':
            # All error types
            return queryset.filter(
                response_text__icontains='Error:'
            ) | queryset.filter(
                response_text__icontains='I apologize, but I can only assist'
            )
        elif self.value() == 'api_error':
            # API key errors specifically
            return queryset.filter(
                response_text__icontains='Error: OpenAI API key not configured'
            )
        elif self.value() == 'domain_error':
            # Domain boundary errors
            return queryset.filter(
                response_text__icontains='I apologize, but I can only assist'
            )
        elif self.value() == 'valid':
            # Valid responses (exclude all error types)
            return queryset.exclude(
                response_text__icontains='Error:'
            ).exclude(
                response_text__icontains='I apologize, but I can only assist'
            )
        return queryset


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ['id', 'query_link', 'is_error', 'response_preview', 'confidence_score', 'generated_at']
    list_filter = [StatusFilter, 'generated_at', 'confidence_score']
    search_fields = ['response_text', 'query__question_text']
    readonly_fields = ['query', 'generated_at', 'is_error', 'response_preview', 'full_response']
    
    def get_readonly_fields(self, request, obj=None):
        """Make response_text editable only when creating new response"""
        if obj:  # Editing existing object
            return self.readonly_fields + ['response_text']
        return self.readonly_fields
    list_per_page = 50
    actions = ['delete_error_responses']
    
    fieldsets = (
        ('Response Information', {
            'fields': ('query', 'is_error', 'confidence_score', 'generated_at')
        }),
        ('Response Content', {
            'fields': ('response_text', 'response_preview', 'full_response', 'sources'),
            'description': 'Response text is shown for viewing. Use preview and full response for better formatting.'
        }),
    )
    
    def query_link(self, obj):
        """Display query as clickable link"""
        if obj.query:
            return format_html(
                '<a href="/admin/forum/query/{}/change/">{}</a>',
                obj.query.id,
                obj.query.question_text[:60] + '...' if len(obj.query.question_text) > 60 else obj.query.question_text
            )
        return '-'
    query_link.short_description = 'Query'
    
    def is_error(self, obj):
        """Display if response contains error"""
        if not obj.response_text:
            return format_html('<span style="color: gray;">-</span>')
        
        if 'Error: OpenAI API key not configured' in obj.response_text:
            return format_html('<span style="color: red; font-weight: bold;">🔑 API ERROR</span>')
        elif 'I apologize, but I can only assist' in obj.response_text:
            return format_html('<span style="color: orange; font-weight: bold;">🚫 DOMAIN ERROR</span>')
        elif 'Error:' in obj.response_text:
            return format_html('<span style="color: red; font-weight: bold;">❌ ERROR</span>')
        return format_html('<span style="color: green;">✅ OK</span>')
    is_error.short_description = 'Status'
    
    def response_preview(self, obj):
        """Show preview of response text"""
        if not obj.response_text:
            return '-'
        preview = obj.response_text[:200]
        if len(obj.response_text) > 200:
            preview += '...'
        return format_html('<div style="max-width: 500px; word-wrap: break-word;">{}</div>', preview)
    response_preview.short_description = 'Response Preview'
    
    def full_response(self, obj):
        """Show full response text"""
        if not obj.response_text:
            return '-'
        return format_html('<div style="max-width: 800px; word-wrap: break-word; white-space: pre-wrap;">{}</div>', obj.response_text)
    full_response.short_description = 'Full Response'
    
    def delete_error_responses(self, request, queryset):
        """Admin action to delete error responses"""
        error_count = 0
        for response in queryset:
            if response.response_text and (
                'Error:' in response.response_text or
                'I apologize, but I can only assist' in response.response_text
            ):
                # Delete the associated query as well
                if response.query:
                    response.query.delete()
                else:
                    response.delete()
                error_count += 1
        
        if error_count > 0:
            self.message_user(
                request,
                f'Successfully deleted {error_count} error response(s) and their associated queries.',
                level='success'
            )
        else:
            self.message_user(
                request,
                'No error responses found in selected items.',
                level='warning'
            )
    delete_error_responses.short_description = 'Delete selected error responses'


@admin.register(KnowledgeBaseEntry)
class KnowledgeBaseEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'country', 'last_updated']
    list_filter = ['category', 'country', 'last_updated']
    search_fields = ['title']


@admin.register(PerformanceMetrics)
class PerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_queries', 'ai_generated', 'database_cached', 'average_response_time_ms', 'total_cost_usd']
    list_filter = ['date']
    readonly_fields = ['date', 'total_queries', 'ai_generated', 'database_cached', 'average_response_time_ms', 'total_cost_usd', 'accuracy_rate']


@admin.register(AIFeature)
class AIFeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(AICapability)
class AICapabilityAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
