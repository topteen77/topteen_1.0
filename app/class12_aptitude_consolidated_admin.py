"""Django admin for Class 12 aptitude consolidated report rows."""

from django.contrib import admin, messages

from app.class12_aptitude_consolidated_io import import_rows_to_db
from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
from app.models import Class12AptitudeConsolidatedReport


@admin.register(Class12AptitudeConsolidatedReport)
class Class12AptitudeConsolidatedReportAdmin(admin.ModelAdmin):
    list_display = (
        'reasoning_combination',
        'code_count',
        'is_active',
        'modified',
    )
    list_filter = ('is_active',)
    search_fields = ('reasoning_combination', 'aptitude_description')
    ordering = ('reasoning_combination',)
    readonly_fields = ('created', 'modified')
    actions = ['import_from_json_file']

    fieldsets = (
        (None, {
            'fields': (
                'reasoning_combination',
                'codes',
                'is_active',
            ),
        }),
        ('Report content', {
            'fields': (
                'aptitude_description',
                'interpretation_narrative',
                'career_clusters',
                'career_pathways',
                'degree_pathways',
            ),
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
        }),
    )

    def code_count(self, obj):
        return len(obj.codes or [])
    code_count.short_description = 'Codes'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_consolidated_lookup_cache()

    @admin.action(description='Import / refresh from class12_aptitude_consolidated_report.json')
    def import_from_json_file(self, request, queryset):
        result = import_rows_to_db(source='json', replace=True)
        if result.get('ok'):
            messages.success(
                request,
                f"Imported {result.get('count', 0)} consolidated aptitude rows.",
            )
        else:
            messages.error(request, result.get('error', 'Import failed.'))
