"""Django admin for Class 12 aptitude consolidated report rows."""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple

from app.class12_aptitude_consolidated_csv import (
    export_consolidated_reports_csv,
    import_consolidated_reports_csv,
)
from app.class12_aptitude_consolidated_io import import_rows_to_db
from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
from app.class12_aptitude_signs_impact import (
    build_sign_impact_ids_for_codes,
    seed_consolidated_sign_impact_ids,
)
from app.models import (
    Class12AptitudeConsolidatedReport,
    Class12AptitudeDailyLifeImpact,
    Class12AptitudeRealLifeSign,
)


class Class12AptitudeConsolidatedReportForm(forms.ModelForm):
    real_life_signs = forms.ModelMultipleChoiceField(
        queryset=Class12AptitudeRealLifeSign.objects.filter(is_active=True).order_by('reasoning_code'),
        required=False,
        widget=FilteredSelectMultiple('Real-life sign areas', is_stacked=False),
        label='Real-life signs',
        help_text='Select reasoning areas. Each area expands to its bullet list on the report.',
    )
    daily_life_impacts = forms.ModelMultipleChoiceField(
        queryset=Class12AptitudeDailyLifeImpact.objects.filter(is_active=True).order_by('reasoning_code'),
        required=False,
        widget=FilteredSelectMultiple('Daily-life impact areas', is_stacked=False),
        label='Daily-life impacts',
        help_text='Select reasoning areas. Each area expands to its bullet list on the report.',
    )

    class Meta:
        model = Class12AptitudeConsolidatedReport
        fields = (
            'reasoning_combination',
            'codes',
            'is_active',
            'aptitude_description',
            'interpretation_narrative',
            'real_life_signs',
            'daily_life_impacts',
            'career_clusters',
            'career_pathways',
            'degree_pathways',
        )
        widgets = {
            'aptitude_description': forms.Textarea(attrs={'rows': 3}),
            'interpretation_narrative': forms.Textarea(attrs={'rows': 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            sign_ids = getattr(self.instance, 'real_life_sign_ids', None) or []
            impact_ids = getattr(self.instance, 'daily_life_impact_ids', None) or []
            self.fields['real_life_signs'].initial = Class12AptitudeRealLifeSign.objects.filter(
                pk__in=sign_ids,
            )
            self.fields['daily_life_impacts'].initial = Class12AptitudeDailyLifeImpact.objects.filter(
                pk__in=impact_ids,
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.real_life_sign_ids = [
            row.pk for row in self.cleaned_data.get('real_life_signs', [])
        ]
        instance.daily_life_impact_ids = [
            row.pk for row in self.cleaned_data.get('daily_life_impacts', [])
        ]
        if commit:
            instance.save()
        return instance


class Class12AptitudeConsolidatedImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV file',
        help_text='Use the exported CSV format. Rows match on reasoning_combination.',
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        label='Update existing rows',
    )


@admin.register(Class12AptitudeConsolidatedReport)
class Class12AptitudeConsolidatedReportAdmin(admin.ModelAdmin):
    form = Class12AptitudeConsolidatedReportForm
    list_display = (
        'reasoning_combination',
        'code_count',
        'sign_area_count',
        'impact_area_count',
        'is_active',
        'modified',
    )
    list_filter = ('is_active',)
    search_fields = ('reasoning_combination', 'aptitude_description')
    ordering = ('reasoning_combination',)
    readonly_fields = ('created', 'modified')
    actions = [
        'import_from_json_file',
        'seed_sign_impact_ids_from_codes',
        'fill_sign_impact_ids_from_codes',
    ]

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
                'real_life_signs',
                'daily_life_impacts',
                'career_clusters',
                'career_pathways',
                'degree_pathways',
            ),
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
        }),
    )

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom = [
            path(
                'export-csv/',
                self.admin_site.admin_view(self.export_csv_view),
                name='app_class12aptitudeconsolidatedreport_export_csv',
            ),
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='app_class12aptitudeconsolidatedreport_import_csv',
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_csv_form'] = Class12AptitudeConsolidatedImportForm()
        return super().changelist_view(request, extra_context=extra_context)

    def export_csv_view(self, request):
        from django.http import HttpResponse

        payload = export_consolidated_reports_csv()
        response = HttpResponse(payload, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="class12_aptitude_consolidated_reports.csv"'
        return response

    def import_csv_view(self, request):
        from django.shortcuts import redirect, render
        from django.urls import reverse

        if request.method == 'POST':
            form = Class12AptitudeConsolidatedImportForm(request.POST, request.FILES)
            if form.is_valid():
                result = import_consolidated_reports_csv(
                    form.cleaned_data['csv_file'],
                    update_existing=form.cleaned_data['update_existing'],
                )
                if not result.get('ok'):
                    messages.error(request, result.get('error', 'Import failed.'))
                else:
                    msg = (
                        f"CSV import complete: {result.get('created', 0)} created, "
                        f"{result.get('updated', 0)} updated, {result.get('skipped', 0)} skipped."
                    )
                    errors = result.get('errors') or []
                    if errors:
                        msg += f" {len(errors)} warning(s)."
                        for warning in errors[:5]:
                            messages.warning(request, warning)
                    messages.success(request, msg)
                return redirect(reverse('admin:app_class12aptitudeconsolidatedreport_changelist'))
            messages.error(request, 'Please choose a valid CSV file.')
        else:
            form = Class12AptitudeConsolidatedImportForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Import Class 12 aptitude consolidated reports (CSV)',
            'opts': self.model._meta,
        }
        return render(
            request,
            'admin/app/class12aptitudeconsolidatedreport/import_csv.html',
            context,
        )

    def code_count(self, obj):
        return len(obj.codes or [])
    code_count.short_description = 'Codes'

    def sign_area_count(self, obj):
        return len(obj.real_life_sign_ids or [])
    sign_area_count.short_description = 'Sign areas'

    def impact_area_count(self, obj):
        return len(obj.daily_life_impact_ids or [])
    impact_area_count.short_description = 'Impact areas'

    def save_model(self, request, obj, form, change):
        if not obj.real_life_sign_ids and not obj.daily_life_impact_ids and obj.codes:
            sign_ids, impact_ids = build_sign_impact_ids_for_codes(list(obj.codes))
            obj.real_life_sign_ids = sign_ids
            obj.daily_life_impact_ids = impact_ids
        super().save_model(request, obj, form, change)
        clear_consolidated_lookup_cache()

    @admin.action(description='Import / refresh from class12_aptitude_consolidated_report.json')
    def import_from_json_file(self, request, queryset):
        result = import_rows_to_db(source='json', replace=True)
        if result.get('ok'):
            seed_consolidated_sign_impact_ids(overwrite=True)
            messages.success(
                request,
                f"Imported {result.get('count', 0)} consolidated aptitude rows.",
            )
        else:
            messages.error(request, result.get('error', 'Import failed.'))

    @admin.action(description='Seed sign/impact areas from codes (skip rows that already have selections)')
    def seed_sign_impact_ids_from_codes(self, request, queryset):
        result = seed_consolidated_sign_impact_ids(
            queryset if queryset.exists() else None,
        )
        if result.get('ok'):
            messages.success(
                request,
                f"Updated sign/impact selections on {result.get('count', 0)} row(s).",
            )
        else:
            messages.error(request, result.get('error', 'Seed failed.'))

    @admin.action(description='Overwrite sign/impact area selections from codes for selected rows')
    def fill_sign_impact_ids_from_codes(self, request, queryset):
        result = seed_consolidated_sign_impact_ids(
            queryset if queryset.exists() else None,
            overwrite=True,
        )
        if result.get('ok'):
            messages.success(
                request,
                f"Refreshed sign/impact selections on {result.get('count', 0)} row(s).",
            )
        else:
            messages.error(request, result.get('error', 'Seed failed.'))
