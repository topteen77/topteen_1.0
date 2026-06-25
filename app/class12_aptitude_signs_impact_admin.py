"""Django admin for Class 12 aptitude real-life signs and daily-life impacts."""

from django import forms
from django.contrib import admin, messages

from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
from app.class12_aptitude_signs_impact import seed_master_signs_impact_from_legacy
from app.models import Class12AptitudeDailyLifeImpact, Class12AptitudeRealLifeSign


class ItemsTextAdminForm(forms.ModelForm):
    class Meta:
        fields = '__all__'
        widgets = {
            'items_text': forms.Textarea(attrs={'rows': 12, 'cols': 100}),
        }


class RealLifeSignAdminForm(ItemsTextAdminForm):
    class Meta(ItemsTextAdminForm.Meta):
        model = Class12AptitudeRealLifeSign


class DailyLifeImpactAdminForm(ItemsTextAdminForm):
    class Meta(ItemsTextAdminForm.Meta):
        model = Class12AptitudeDailyLifeImpact


@admin.register(Class12AptitudeRealLifeSign)
class Class12AptitudeRealLifeSignAdmin(admin.ModelAdmin):
    form = RealLifeSignAdminForm
    list_display = ('id', 'reasoning_code', 'bullet_count', 'is_active', 'modified')
    list_filter = ('is_active',)
    search_fields = ('items_text', 'reasoning_code')
    ordering = ('reasoning_code',)
    readonly_fields = ('id', 'created', 'modified')
    actions = ['seed_from_legacy_json']

    fieldsets = (
        (None, {
            'fields': ('id', 'reasoning_code', 'is_active'),
        }),
        ('Real-life signs', {
            'fields': ('items_text',),
            'description': 'Enter one sign per line.',
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
        }),
    )

    def bullet_count(self, obj):
        return len(obj.bullet_list())
    bullet_count.short_description = 'Bullets'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_consolidated_lookup_cache()

    @admin.action(description='Seed / refresh all areas from legacy aptitude interpretation JSON')
    def seed_from_legacy_json(self, request, queryset):
        result = seed_master_signs_impact_from_legacy(overwrite=True)
        if result.get('ok'):
            messages.success(
                request,
                f"Seeded {result.get('sign_count', 0)} real-life sign area(s) from legacy JSON.",
            )
        else:
            messages.error(request, result.get('error', 'Seed failed.'))


@admin.register(Class12AptitudeDailyLifeImpact)
class Class12AptitudeDailyLifeImpactAdmin(admin.ModelAdmin):
    form = DailyLifeImpactAdminForm
    list_display = ('id', 'reasoning_code', 'bullet_count', 'is_active', 'modified')
    list_filter = ('is_active',)
    search_fields = ('items_text', 'reasoning_code')
    ordering = ('reasoning_code',)
    readonly_fields = ('id', 'created', 'modified')
    actions = ['seed_from_legacy_json']

    fieldsets = (
        (None, {
            'fields': ('id', 'reasoning_code', 'is_active'),
        }),
        ('Daily-life impacts', {
            'fields': ('items_text',),
            'description': 'Enter one impact per line.',
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
        }),
    )

    def bullet_count(self, obj):
        return len(obj.bullet_list())
    bullet_count.short_description = 'Bullets'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_consolidated_lookup_cache()

    @admin.action(description='Seed / refresh all areas from legacy aptitude interpretation JSON')
    def seed_from_legacy_json(self, request, queryset):
        result = seed_master_signs_impact_from_legacy(overwrite=True)
        if result.get('ok'):
            messages.success(
                request,
                f"Seeded {result.get('impact_count', 0)} daily-life impact area(s) from legacy JSON.",
            )
        else:
            messages.error(request, result.get('error', 'Seed failed.'))
