from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from forum.models import (
    Query,
    Response,
    Category,
    Country,
    KnowledgeBaseEntry,
    PerformanceMetrics,
    AIFeature,
    AICapability,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order']
    list_editable = ['order']


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'flag_emoji']


class ResponseInline(admin.StackedInline):
    model = Response
    extra = 0
    fields = ['response_text', 'confidence_score', 'sources', 'generated_at']
    readonly_fields = ['generated_at']
    can_delete = True


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'short_question',
        'category',
        'status',
        'is_hidden',
        'visibility_badge',
        'created_at',
    ]
    list_filter = ['is_hidden', 'status', 'category', 'created_at', 'source']
    list_editable = ['is_hidden']
    search_fields = ['question_text', 'response__response_text']
    readonly_fields = ['created_at', 'processed_at', 'updated_at', 'hidden_at', 'hidden_by']
    inlines = [ResponseInline]
    actions = ['hide_from_display', 'unhide_on_display', 'delete_selected_posts']
    fieldsets = (
        (
            'Post',
            {
                'fields': (
                    'question_text',
                    'category',
                    'country_context',
                    'status',
                    'source',
                    'response_time_ms',
                )
            },
        ),
        (
            'Display moderation',
            {
                'fields': ('is_hidden', 'hidden_at', 'hidden_by'),
                'description': (
                    'Hidden posts stay in the database but are removed from '
                    'Career Exploration / Trending on the forum.'
                ),
            },
        ),
        (
            'Timestamps',
            {'fields': ('created_at', 'processed_at', 'updated_at')},
        ),
    )

    def short_question(self, obj):
        text = obj.question_text or ''
        return text[:80] + ('…' if len(text) > 80 else '')

    short_question.short_description = 'Question'

    def visibility_badge(self, obj):
        if obj.is_hidden:
            return format_html(
                '<span style="color:#b45309;font-weight:700;">Hidden</span>'
            )
        return format_html(
            '<span style="color:#15803d;font-weight:700;">Visible</span>'
        )

    visibility_badge.short_description = 'Display'

    def save_model(self, request, obj, form, change):
        if 'is_hidden' in form.changed_data:
            if obj.is_hidden:
                obj.hidden_at = timezone.now()
                obj.hidden_by = request.user
            else:
                obj.hidden_at = None
                obj.hidden_by = None
        super().save_model(request, obj, form, change)

    @admin.action(description='Hide selected posts from forum display')
    def hide_from_display(self, request, queryset):
        count = 0
        for query in queryset:
            if not query.is_hidden:
                query.hide(request.user)
                count += 1
        self.message_user(request, f'Hidden {count} post(s) from public display.')

    @admin.action(description='Unhide selected posts (show on forum)')
    def unhide_on_display(self, request, queryset):
        count = 0
        for query in queryset:
            if query.is_hidden:
                query.unhide()
                count += 1
        self.message_user(request, f'Unhid {count} post(s).')

    @admin.action(description='Delete selected posts permanently')
    def delete_selected_posts(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Deleted {count} post(s).')


class StatusFilter(admin.SimpleListFilter):
    """Custom filter to show responses by status (error vs valid)"""
    title = 'Response Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('error', '❌ Error Responses'),
            ('api_error', '🔑 API Key Errors'),
            ('domain_error', '🚫 Domain Boundary Errors'),
            ('paywall', '💳 Paywall / Quota Messages'),
            ('valid', '✅ Valid Responses'),
            ('hidden', '🙈 Query hidden from display'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'error':
            return queryset.filter(response_text__icontains='Error:') | queryset.filter(
                response_text__icontains='I apologize, but I can only assist'
            )
        elif self.value() == 'api_error':
            return queryset.filter(
                response_text__icontains='Error: OpenAI API key not configured'
            )
        elif self.value() == 'domain_error':
            return queryset.filter(
                response_text__icontains='I apologize, but I can only assist'
            )
        elif self.value() == 'paywall':
            return queryset.filter(
                response_text__icontains='Sign in to keep using AI'
            ) | queryset.filter(response_text__icontains='free guest AI allowance')
        elif self.value() == 'valid':
            return (
                queryset.exclude(response_text__icontains='Error:')
                .exclude(response_text__icontains='I apologize, but I can only assist')
                .exclude(response_text__icontains='Sign in to keep using AI')
                .exclude(response_text__icontains='free guest AI allowance')
            )
        elif self.value() == 'hidden':
            return queryset.filter(query__is_hidden=True)
        return queryset


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'query_link',
        'is_error',
        'query_hidden',
        'response_preview',
        'confidence_score',
        'generated_at',
    ]
    list_filter = [StatusFilter, 'generated_at', 'confidence_score', 'query__is_hidden']
    search_fields = ['response_text', 'query__question_text']
    readonly_fields = ['query', 'generated_at', 'is_error', 'response_preview', 'full_response']
    list_per_page = 50
    actions = ['delete_error_responses', 'hide_related_queries', 'unhide_related_queries']

    def get_readonly_fields(self, request, obj=None):
        # Allow staff to edit the answer text
        return ['query', 'generated_at', 'is_error', 'response_preview', 'full_response']

    fieldsets = (
        (
            'Response Information',
            {'fields': ('query', 'is_error', 'confidence_score', 'generated_at')},
        ),
        (
            'Edit answer (shown on forum)',
            {
                'fields': ('response_text', 'response_preview', 'full_response', 'sources'),
                'description': 'Edit response_text to change what visitors see.',
            },
        ),
    )

    def query_link(self, obj):
        if obj.query:
            return format_html(
                '<a href="/admin/forum/query/{}/change/">{}</a>',
                obj.query.id,
                obj.query.question_text[:60]
                + ('...' if len(obj.query.question_text) > 60 else ''),
            )
        return '-'

    query_link.short_description = 'Query'

    def query_hidden(self, obj):
        if obj.query and obj.query.is_hidden:
            return format_html('<span style="color:#b45309;font-weight:700;">Hidden</span>')
        return format_html('<span style="color:#15803d;">Visible</span>')

    query_hidden.short_description = 'Display'

    def is_error(self, obj):
        if not obj.response_text:
            return format_html('<span style="color: gray;">-</span>')
        lower = obj.response_text.lower()
        if 'error: openai api key not configured' in lower:
            return format_html(
                '<span style="color: red; font-weight: bold;">🔑 API ERROR</span>'
            )
        if 'sign in to keep using ai' in lower or 'free guest ai allowance' in lower:
            return format_html(
                '<span style="color: #7c3aed; font-weight: bold;">💳 PAYWALL</span>'
            )
        if 'i apologize, but i can only assist' in lower:
            return format_html(
                '<span style="color: orange; font-weight: bold;">🚫 DOMAIN ERROR</span>'
            )
        if 'error:' in lower:
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ ERROR</span>'
            )
        return format_html('<span style="color: green;">✅ OK</span>')

    is_error.short_description = 'Status'

    def response_preview(self, obj):
        if not obj.response_text:
            return '-'
        preview = obj.response_text[:200]
        if len(obj.response_text) > 200:
            preview += '...'
        return format_html(
            '<div style="max-width: 500px; word-wrap: break-word;">{}</div>', preview
        )

    response_preview.short_description = 'Response Preview'

    def full_response(self, obj):
        if not obj.response_text:
            return '-'
        return format_html(
            '<div style="max-width: 800px; word-wrap: break-word; white-space: pre-wrap;">{}</div>',
            obj.response_text,
        )

    full_response.short_description = 'Full Response'

    @admin.action(description='Hide related forum posts from display')
    def hide_related_queries(self, request, queryset):
        count = 0
        for response in queryset.select_related('query'):
            if response.query and not response.query.is_hidden:
                response.query.hide(request.user)
                count += 1
        self.message_user(request, f'Hidden {count} post(s).')

    @admin.action(description='Unhide related forum posts')
    def unhide_related_queries(self, request, queryset):
        count = 0
        for response in queryset.select_related('query'):
            if response.query and response.query.is_hidden:
                response.query.unhide()
                count += 1
        self.message_user(request, f'Unhid {count} post(s).')

    @admin.action(description='Delete selected error responses (+ queries)')
    def delete_error_responses(self, request, queryset):
        error_count = 0
        for response in queryset:
            if response.response_text and (
                'Error:' in response.response_text
                or 'I apologize, but I can only assist' in response.response_text
                or 'Sign in to keep using AI' in response.response_text
                or 'free guest AI allowance' in response.response_text
            ):
                if response.query:
                    response.query.delete()
                else:
                    response.delete()
                error_count += 1

        if error_count > 0:
            self.message_user(
                request,
                f'Successfully deleted {error_count} error response(s) and their associated queries.',
                level='success',
            )
        else:
            self.message_user(
                request,
                'No error responses found in selected items.',
                level='warning',
            )


@admin.register(KnowledgeBaseEntry)
class KnowledgeBaseEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'country', 'last_updated']
    list_filter = ['category', 'country', 'last_updated']
    search_fields = ['title']


@admin.register(PerformanceMetrics)
class PerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'date',
        'total_queries',
        'ai_generated',
        'database_cached',
        'average_response_time_ms',
        'total_cost_usd',
    ]
    list_filter = ['date']
    readonly_fields = [
        'date',
        'total_queries',
        'ai_generated',
        'database_cached',
        'average_response_time_ms',
        'total_cost_usd',
        'accuracy_rate',
    ]


@admin.register(AIFeature)
class AIFeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'link_url', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'link_url']
    fields = ['name', 'icon', 'description', 'link_url', 'order', 'is_active']


@admin.register(AICapability)
class AICapabilityAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'link_url', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'link_url']
    fields = ['name', 'icon', 'description', 'link_url', 'order', 'is_active']
