"""Django admin for Class 12 aptitude consolidated report rows."""

from django import forms
from django.contrib import admin, messages

from app.class12_aptitude_consolidated_csv import (
    export_consolidated_reports_csv,
    import_consolidated_reports_csv,
)
from app.class12_aptitude_consolidated_io import import_rows_to_db
from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
from app.class12_aptitude_signs_impact import bullets_to_text, text_to_bullets
from app.models import Class12AptitudeConsolidatedReport


class Class12AptitudeConsolidatedReportForm(forms.ModelForm):
    real_life_signs_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 8}),
        label='Real-life signs',
        help_text='One bullet per line (imported from Excel per combination).',
    )
    daily_life_impact_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 8}),
        label='Daily life impact',
        help_text='One bullet per line (imported from Excel per combination).',
    )

    class Meta:
        model = Class12AptitudeConsolidatedReport
        fields = (
            'reasoning_combination',
            'codes',
            'is_active',
            'aptitude_description',
            'interpretation_narrative',
            'real_life_signs_text',
            'daily_life_impact_text',
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
            self.fields['real_life_signs_text'].initial = bullets_to_text(
                self.instance.real_life_signs,
            )
            self.fields['daily_life_impact_text'].initial = bullets_to_text(
                self.instance.daily_life_impact,
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.real_life_signs = text_to_bullets(
            self.cleaned_data.get('real_life_signs_text', ''),
        )
        instance.daily_life_impact = text_to_bullets(
            self.cleaned_data.get('daily_life_impact_text', ''),
        )
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
        'sign_count',
        'impact_count',
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
                'real_life_signs_text',
                'daily_life_impact_text',
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

    def sign_count(self, obj):
        return len(obj.real_life_signs or [])
    sign_count.short_description = 'Signs'

    def impact_count(self, obj):
        return len(obj.daily_life_impact or [])
    impact_count.short_description = 'Impacts'

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
