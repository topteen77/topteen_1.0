"""Django admin for aptitude improvement plans (Class 10 / Class 12)."""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from app.aptitude_improvement_plans import (
    CLASS_10,
    CLASS_12,
    parse_improvement_plan_docx,
    seed_class_10_plans_from_class_12,
    upsert_class_12_plans_from_docx,
)
from app.models import AptitudeImprovementPlan


class AptitudeImprovementPlanForm(forms.ModelForm):
    improvement_plan_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 10}),
        help_text='One suggested improvement item per line.',
        label='Suggested improvement plan (one per line)',
    )

    class Meta:
        model = AptitudeImprovementPlan
        fields = (
            'education_level',
            'area_key',
            'growth_area_title',
            'development_goal',
            'practice_frequency',
            'expected_timeline',
            'sort_order',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            items = self.instance.improvement_plan_items or []
            self.fields['improvement_plan_text'].initial = '\n'.join(items)

    def clean(self):
        cleaned = super().clean()
        raw = cleaned.get('improvement_plan_text') or ''
        cleaned['improvement_plan_items'] = [
            line.strip() for line in raw.splitlines() if line.strip()
        ]
        return cleaned

    def save(self, commit=True):
        self.instance.improvement_plan_items = self.cleaned_data.get('improvement_plan_items', [])
        return super().save(commit=commit)


class AptitudeImprovementPlanImportForm(forms.Form):
    docx_file = forms.FileField(
        label='Class 12 improvement plan (.docx)',
        help_text='Upload improvement plan- 12.docx to refresh Class 12 entries.',
    )


@admin.register(AptitudeImprovementPlan)
class AptitudeImprovementPlanAdmin(admin.ModelAdmin):
    form = AptitudeImprovementPlanForm
    list_display = (
        'growth_area_title',
        'education_level',
        'area_key',
        'expected_timeline',
        'sort_order',
        'is_active',
        'modified',
    )
    list_filter = ('education_level', 'is_active')
    search_fields = ('growth_area_title', 'area_key', 'development_goal')
    ordering = ('education_level', 'sort_order', 'growth_area_title')
    readonly_fields = ('created', 'modified')
    fieldsets = (
        (None, {
            'fields': (
                'education_level',
                'area_key',
                'growth_area_title',
                'development_goal',
                'improvement_plan_text',
                'practice_frequency',
                'expected_timeline',
                'sort_order',
                'is_active',
            ),
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created', 'modified'),
        }),
    )
    actions = ['seed_class_10_from_class_12']

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom = [
            path(
                'import-docx/',
                self.admin_site.admin_view(self.import_docx_view),
                name='app_aptitudeimprovementplan_import_docx',
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_docx_form'] = AptitudeImprovementPlanImportForm()
        return super().changelist_view(request, extra_context=extra_context)

    def import_docx_view(self, request):
        from django.shortcuts import redirect, render
        from django.urls import reverse

        if request.method == 'POST':
            form = AptitudeImprovementPlanImportForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.cleaned_data['docx_file']
                import tempfile

                with tempfile.NamedTemporaryFile(suffix='.docx', delete=True) as tmp:
                    for chunk in upload.chunks():
                        tmp.write(chunk)
                    tmp.flush()
                    try:
                        result = upsert_class_12_plans_from_docx(tmp.name)
                    except Exception as exc:
                        messages.error(request, f'Import failed: {exc}')
                        return redirect(reverse('admin:app_aptitudeimprovementplan_changelist'))
                seed = seed_class_10_plans_from_class_12()
                messages.success(
                    request,
                    f"Imported Class 12 plans ({result['created']} created, {result['updated']} updated). "
                    f"Class 10 seed: {seed['created']} created, {seed['updated']} updated.",
                )
                return redirect(reverse('admin:app_aptitudeimprovementplan_changelist'))
            messages.error(request, 'Please choose a valid .docx file.')
        else:
            form = AptitudeImprovementPlanImportForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Import Class 12 improvement plan (.docx)',
            'opts': self.model._meta,
        }
        return render(request, 'admin/app/aptitudeimprovementplan/import_docx.html', context)

    @admin.action(description='Seed Class 10 plans from Class 12 content')
    def seed_class_10_from_class_12(self, request, queryset):
        result = seed_class_10_plans_from_class_12()
        messages.success(
            request,
            f"Class 10 plans: {result['created']} created, {result['updated']} updated.",
        )
