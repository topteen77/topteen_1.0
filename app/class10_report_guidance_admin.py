"""Django admin for Class 10 combined report career guidance."""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from app.models import (
    Class10FutureRelevantCareer,
    Class10PremiumStream,
    Class10PremiumStreamCareer,
    Class10ReportGuidanceSettings,
)
from app.stream_sorter_guidance import clear_stream_sorter_guidance_cache, import_catalog_from_json_file


def _published_career_queryset():
    from careers.models import Career
    from core import choices

    return Career.objects.filter(
        publish_status=choices.PublishStatus.PUBLISHED,
        object_status=choices.ObjectStatus.ACTIVE,
    ).order_by('name')


class Class10PremiumStreamCareerForm(forms.ModelForm):
    class Meta:
        model = Class10PremiumStreamCareer
        fields = ('career', 'sort_order', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['career'].queryset = _published_career_queryset()
        self.fields['career'].required = True
        self.fields['career'].label = 'Career name'

    def clean(self):
        cleaned = super().clean()
        if self.cleaned_data.get('DELETE'):
            return cleaned
        if not cleaned.get('career'):
            raise ValidationError({'career': 'Select a career from the site catalog.'})
        return cleaned


class Class10PremiumStreamCareerInline(admin.TabularInline):
    model = Class10PremiumStreamCareer
    form = Class10PremiumStreamCareerForm
    extra = 1
    fields = ('career', 'sort_order', 'is_active')
    autocomplete_fields = ('career',)
    ordering = ('sort_order',)
    verbose_name = 'Career'
    verbose_name_plural = 'Careers'


class Class10FutureRelevantCareerForm(forms.ModelForm):
    class Meta:
        model = Class10FutureRelevantCareer
        fields = ('career', 'sort_order', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['career'].queryset = _published_career_queryset()
        self.fields['career'].required = True
        self.fields['career'].label = 'Career name'

    def clean_career(self):
        career = self.cleaned_data.get('career')
        if not career:
            raise ValidationError('Select a career from the site catalog.')
        return career


@admin.register(Class10ReportGuidanceSettings)
class Class10ReportGuidanceSettingsAdmin(admin.ModelAdmin):
    list_display = ('stream_wise_title', 'future_relevant_title')
    fields = ('stream_wise_title', 'future_relevant_title')

    def has_add_permission(self, request):
        return not Class10ReportGuidanceSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_stream_sorter_guidance_cache()


@admin.register(Class10PremiumStream)
class Class10PremiumStreamAdmin(admin.ModelAdmin):
    list_display = ('display_label', 'stream_code', 'sort_order', 'is_active', 'career_count')
    list_filter = ('is_active', 'stream_code')
    search_fields = ('display_label', 'stream_code')
    ordering = ('sort_order', 'stream_code')
    inlines = [Class10PremiumStreamCareerInline]
    actions = ['import_from_unique_streams_json']

    def career_count(self, obj):
        return obj.careers.filter(is_active=True).count()
    career_count.short_description = 'Active careers'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_stream_sorter_guidance_cache()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        clear_stream_sorter_guidance_cache()

    @admin.action(description='Import / refresh from class10_stream_sorter_unique_streams.json')
    def import_from_unique_streams_json(self, request, queryset):
        result = import_catalog_from_json_file(replace=True)
        if result.get('ok'):
            messages.success(
                request,
                f"Imported {result.get('streams', 0)} streams and "
                f"{result.get('future_careers', 0)} future-relevant careers.",
            )
        else:
            messages.error(request, result.get('error', 'Import failed.'))


@admin.register(Class10FutureRelevantCareer)
class Class10FutureRelevantCareerAdmin(admin.ModelAdmin):
    form = Class10FutureRelevantCareerForm
    list_display = ('career', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('career__name',)
    ordering = ('sort_order',)
    autocomplete_fields = ('career',)
    fields = ('career', 'sort_order', 'is_active')
    actions = ['import_from_unique_streams_json']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_stream_sorter_guidance_cache()

    @admin.action(description='Import / refresh from class10_stream_sorter_unique_streams.json')
    def import_from_unique_streams_json(self, request, queryset):
        result = import_catalog_from_json_file(replace=True)
        if result.get('ok'):
            messages.success(request, f"Imported {result.get('future_careers', 0)} future-relevant careers.")
        else:
            messages.error(request, result.get('error', 'Import failed.'))

