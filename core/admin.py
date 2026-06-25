from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from core.choices import (
    CLASS10_APTITUDE_STREAM_DISPLAY_MODE_CHOICES,
    CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY,
    CLASS10_APTITUDE_STREAM_MODE_COMBINED,
    CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
    CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_CHOICES,
    CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_KEY,
    COURSE_MINDMAP_CONFIG_CHOICES,
    MINDMAP_TYPE_CHOICES,
    coerce_default_mindmap_type,
)
from django.utils import timezone
from django.utils.html import conditional_escape, format_html, strip_tags
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from .models import (
    Configuration,
    City,
    Review,
    State,
    Country,
    CommonFAQ,
    APILog,
    Stories,
    Contact,
    Lead,
    ExtracurricularActivityCategory,
    ExtracurricularActivity,
    ExtracurricularActivitySection,
    VocationalCourseCategory,
    VocationalCourse,
    VocationalCourseReasoningMapping,
    EntranceTestPrepCategory,
    EntranceTestPrepExam,
    EntranceTestPrepExamSection,
    Ebook,
    S3FileUpload,
    FourPillarsAssessment,
    FourPillarsAssessmentScoringGuide,
    FourPillarsAssessmentQuestion,
    FourPillarsAssessmentQuestionOption,
    FourPillarsAssessmentProfile,
    MIAssessmentResult,
    EQAssessmentResult,
    CareerBattleFight,
    CareerBattleEligibilityProfile,
    CounsellingSession,
    DashboardLevelBand,
    DashboardPointRule,
    DashboardTrophyDefinition,
    DashboardStreakConfig,
    StaticPage,
    StaticPageSection,
    PageSEO,
    URLIndexRule,
    ScannedURL,
    GeneratedPage,
)
# Register your models here.



class StudentIdSettingsForm(forms.Form):
    """Form for Student ID and School Student ID prefixes (Admin-managed)."""
    STUDENT_ID_PREFIX = forms.CharField(
        max_length=20,
        required=False,
        label='Student ID prefix',
        help_text='Prefix for direct/school student display ID (e.g. STU → STU000123). Default: STU.',
        initial='STU',
    )
    SCHOOL_STUDENT_ID_PREFIX = forms.CharField(
        max_length=20,
        required=False,
        label='School student ID prefix',
        help_text='Prefix for school/institute student identifier. Display format: Prefix/StudentID (e.g. SCH → SCH/STU000123). Default: SCH.',
        initial='SCH',
    )


class PsychometricSettingsForm(forms.Form):
    """Form for psychometric test site settings (Admin-managed)."""
    ENABLE_ANSWERING_CAREFULLY_WIDGET = forms.BooleanField(
        required=False,
        label='Show "Answering Carefully" widget',
        help_text='Display the "Answering Carefully" / "Rushing Through" widget on test pages.',
    )
    ENABLE_AUTO_FORWARD = forms.BooleanField(
        required=False,
        label='Auto-advance on answer selection',
        help_text='Automatically move to the next question when user selects an answer.',
    )
    SHOW_MISSING_ANSWERS_VALIDATION = forms.BooleanField(
        required=False,
        label='Show validation message (missing answers)',
        help_text='When enabled, shows "Unanswered Questions" confirmation on submit and the missing-answers palette when user clicks "Review Answers". When disabled, submit is allowed without this validation.',
    )


class Class10AptitudeReportSettingsForm(forms.Form):
    """Class 10 intelligence report stream recommendation display (Admin-managed)."""

    CLASS10_APTITUDE_STREAM_DISPLAY_MODE = forms.ChoiceField(
        choices=CLASS10_APTITUDE_STREAM_DISPLAY_MODE_CHOICES,
        required=True,
        label='Stream recommendation basis',
        help_text=(
            'Combined: use Above Average and Average areas together. '
            'Single - Above Average: use Above Average only when present, otherwise Average; '
            'if every area is Below Average, show the improvement note only.'
        ),
    )


class Class12AptitudeReportSettingsForm(forms.Form):
    """Class 11–12 aptitude consolidated interpretation display (Admin-managed)."""

    CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE = forms.ChoiceField(
        choices=CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_CHOICES,
        required=True,
        label='Consolidated interpretation basis',
        help_text=(
            'Combined: use Above Average and Average areas together for the consolidated box. '
            'Single - Above Average: use Above Average only when present, otherwise Average; '
            'if every area is a Growth Area, show the improvement note only.'
        ),
    )


class WebsiteSettingsForm(forms.Form):
    """Form for core website settings (Admin-managed)."""
    ENABLE_CAREER_MINDMAP = forms.BooleanField(
        required=False,
        label='Enable career mindmap',
        help_text='Show career mindmaps on career detail pages, careers chat, and dedicated mindmap page. When disabled, mindmap sections and icons are hidden site-wide.',
    )
    ENABLE_COUNSELOR_COURSE_MINDMAP = forms.BooleanField(
        required=False,
        label='Enable counselor course mindmaps',
        help_text=(
            'When enabled, counselor certification course/part/chapter mindmaps appear when the matching static JSON file exists '
            '(curriculum course map, learning sidebar icons, full-page views, part Mindmap tab). When disabled, all of these are hidden.'
        ),
    )
    DEFAULT_MINDMAP_TYPE = forms.ChoiceField(
        choices=MINDMAP_TYPE_CHOICES,
        required=True,
        label='Default mindmap type',
        help_text=(
            'Radial (6) or classic / career-tree API mindmaps (16–19). '
            '16–17: compact pills; 18–19: colored branches and underlines (counselor-style). '
            'Legacy numeric types in the database are coerced to Radial until you save a new choice.'
        ),
    )
    DEFAULT_course_MINDMAP_TYPE = forms.ChoiceField(
        choices=COURSE_MINDMAP_CONFIG_CHOICES,
        required=True,
        label='Default counselor course mindmap type',
        help_text=(
            'Visualization for counselor certification mindmaps (curriculum, course learning sidebar/tab, full page). '
            'Uses static JSON markdown only; no URL parameter needed. Values 6–7 align with career mindmap “Radial” / “Cards” style where applicable. '
            'Value 8 is the classic horizontal mindmap (pill nodes); value 9 is the classic vertical (top-down) layout.'
        ),
    )
    CHATBOT_DEFAULT_MODE = forms.ChoiceField(
        choices=[
            ('default', 'Default behavior'),
            ('none', 'Hide both bots'),
            ('chat_this_page', 'Show only "Chat this page"'),
            ('career_counsellor', 'Show only "Career Counsellor"'),
            ('both', 'Show both'),
        ],
        required=True,
        label='Default chatbot mode',
        help_text='Fallback mode used when no page rule matches.',
    )
    CHATBOT_PAGE_RULES = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 8, 'style': 'width: 100%; font-family: monospace;'}),
        label='Chatbot page rules (JSON)',
        help_text='JSON array of rules. Example: [{"match":"exact","pattern":"/","mode":"career_counsellor"},{"match":"prefix","pattern":"/four-pillars-of-learning/","mode":"chat_this_page"}]',
    )

    DASHBOARD_TEMPLATE_VERSION = forms.ChoiceField(
        choices=[
            ("v1", "Template v1 (current)"),
            ("v2", "Template v2 (new)"),
        ],
        required=True,
        label="Dashboard template version",
        help_text="Global switch for Institute/Group/Marketing/Counselor dashboards layout templates.",
    )
    TTV2_PAGE_LOADER_ENABLED = forms.BooleanField(
        required=False,
        label="Template v2 page loader (donut %)",
        help_text=(
            "When enabled, v2 dashboard sidebar navigation shows the centralized "
            "loading overlay (percent ring + “Loading page”) while AJAX content loads. "
            "When disabled, pages still load in the background with no overlay."
        ),
    )


DEFAULT_MINDMAP_CONFIG_KEY = 'DEFAULT_MINDMAP_TYPE'
DEFAULT_COURSE_MINDMAP_CONFIG_KEY = 'DEFAULT_course_MINDMAP_TYPE'


class ConfigurationAdminForm(forms.ModelForm):
    """Use labeled dropdowns for mindmap-related configuration keys (same labels as Website settings)."""

    class Meta:
        model = Configuration
        fields = ['key', 'value']

    @staticmethod
    def _default_mindmap_value_to_choice(stored: str) -> str:
        return coerce_default_mindmap_type(stored)

    @staticmethod
    def _course_mindmap_value_to_choice(stored: str) -> str:
        raw = (stored or '').strip()
        if not raw:
            return '8'
        allowed = {c[0] for c in COURSE_MINDMAP_CONFIG_CHOICES}
        if raw in allowed:
            return raw
        nk = raw.lower().replace(' ', '_').replace('-', '_')
        if nk in ('classic_mindmap', 'classic', 'horizontal_classic'):
            return '8'
        return '8'

    @staticmethod
    def _class10_aptitude_mode_to_choice(stored: str) -> str:
        raw = str(stored or '').strip().lower()
        if raw in (CLASS10_APTITUDE_STREAM_MODE_COMBINED, CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY):
            return raw
        if raw in ('single', 'single_above_average', 'above_average', 'above_avg'):
            return CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY
        return CLASS10_APTITUDE_STREAM_MODE_COMBINED

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cfg_key = None
        if getattr(self.instance, 'pk', None):
            cfg_key = (self.instance.key or '').strip()
        elif self.data:
            cfg_key = (self.data.get('key') or '').strip()

        if cfg_key == DEFAULT_MINDMAP_CONFIG_KEY:
            self.fields['value'] = forms.ChoiceField(
                choices=MINDMAP_TYPE_CHOICES,
                label='Value',
                required=True,
                help_text=(
                    'Default layout for the dedicated career mindmap page (and related UI). '
                    'Same options as Core → Configuration → Website settings (Default mindmap type).'
                ),
            )
            if self.instance.pk:
                self.fields['value'].initial = self._default_mindmap_value_to_choice(self.instance.value)
            return

        if cfg_key == DEFAULT_COURSE_MINDMAP_CONFIG_KEY:
            self.fields['value'] = forms.ChoiceField(
                choices=COURSE_MINDMAP_CONFIG_CHOICES,
                label='Value',
                required=True,
                help_text=(
                    'Counselor course mindmap layout (curriculum, learning UI, full page). '
                    'Same options as Core → Configuration → Website settings (mindmap section).'
                ),
            )
            if self.instance.pk:
                self.fields['value'].initial = self._course_mindmap_value_to_choice(self.instance.value)
            return

        if cfg_key == CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY:
            self.fields['value'] = forms.ChoiceField(
                choices=CLASS10_APTITUDE_STREAM_DISPLAY_MODE_CHOICES,
                label='Value',
                required=True,
                help_text=(
                    'Combined: use Above Average and Average together for stream recommendations. '
                    'Single - Above Average: use Above Average first, otherwise Average; '
                    'if all areas are Below Average, show the improvement note only.'
                ),
            )
            if self.instance.pk:
                self.fields['value'].initial = self._class10_aptitude_mode_to_choice(self.instance.value)
            return

        if cfg_key == CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_KEY:
            self.fields['value'] = forms.ChoiceField(
                choices=CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_CHOICES,
                label='Value',
                required=True,
                help_text=(
                    'Combined: use Above Average and Average together for consolidated interpretation. '
                    'Single - Above Average: use Above Average first, otherwise Average; '
                    'if all areas are Growth Area, show the improvement note only.'
                ),
            )
            if self.instance.pk:
                self.fields['value'].initial = self._class10_aptitude_mode_to_choice(self.instance.value)


class ConfigurationAdmin(admin.ModelAdmin):
    form = ConfigurationAdminForm
    # date_hierarchy = 'created'  # Disabled: Requires MySQL timezone tables to be loaded
    list_display = ['id', 'key', 'value_display', 'created', 'modified']
    sortable_by = ['id', 'key', 'created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified', 'created')
    search_fields = ['key', 'value']
    list_display_links = ['id', 'key']

    @admin.display(description='Value')
    def value_display(self, obj):
        if obj.key == DEFAULT_MINDMAP_CONFIG_KEY:
            label_by_value = dict(MINDMAP_TYPE_CHOICES)
            choice_val = ConfigurationAdminForm._default_mindmap_value_to_choice(obj.value)
            return label_by_value.get(choice_val, obj.value)
        if obj.key == DEFAULT_COURSE_MINDMAP_CONFIG_KEY:
            label_by_value = dict(COURSE_MINDMAP_CONFIG_CHOICES)
            choice_val = ConfigurationAdminForm._course_mindmap_value_to_choice(obj.value)
            return label_by_value.get(choice_val, obj.value)
        if obj.key == CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY:
            choice_val = ConfigurationAdminForm._class10_aptitude_mode_to_choice(obj.value)
            return dict(CLASS10_APTITUDE_STREAM_DISPLAY_MODE_CHOICES).get(choice_val, obj.value)
        if obj.key == CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_KEY:
            choice_val = ConfigurationAdminForm._class10_aptitude_mode_to_choice(obj.value)
            return dict(CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_CHOICES).get(choice_val, obj.value)
        return obj.value

    def get_fields(self, request, obj=None):
        if obj is None:
            return ['key', 'value']  # Add form: created/modified are auto, non-editable
        return ['created', 'modified', 'key', 'value']

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []  # Add form: key and value both editable
        return ('created', 'modified', 'key')

    def get_queryset(self, request):
        qs = super(ConfigurationAdmin, self).get_queryset(request)
        return qs.filter(editable=True)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return True

    def save_model(self, request, obj, form, change):
        if not change:
            obj.editable = True
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('psychometric-settings/', self.admin_site.admin_view(self.psychometric_settings_view), name='core_configuration_psychometric_settings'),
            path(
                'class10-aptitude-report-settings/',
                self.admin_site.admin_view(self.class10_aptitude_report_settings_view),
                name='core_configuration_class10_aptitude_report_settings',
            ),
            path(
                'class12-aptitude-report-settings/',
                self.admin_site.admin_view(self.class12_aptitude_report_settings_view),
                name='core_configuration_class12_aptitude_report_settings',
            ),
            path('student-id-settings/', self.admin_site.admin_view(self.student_id_settings_view), name='core_configuration_student_id_settings'),
            path('website-settings/', self.admin_site.admin_view(self.website_settings_view), name='core_configuration_website_settings'),
            path('dashboard-statistics/', self.admin_site.admin_view(self.dashboard_statistics_view), name='core_configuration_dashboard_statistics'),
        ]
        return custom + urls

    def student_id_settings_view(self, request):
        """Custom admin view for Student ID and School Student ID prefix settings."""
        from core.models import Configuration

        if request.method == 'POST':
            form = StudentIdSettingsForm(request.POST)
            if form.is_valid():
                for key, field_name in [
                    ('STUDENT_ID_PREFIX', 'STUDENT_ID_PREFIX'),
                    ('SCHOOL_STUDENT_ID_PREFIX', 'SCHOOL_STUDENT_ID_PREFIX'),
                ]:
                    val = (form.cleaned_data.get(field_name) or '').strip() or ('STU' if key == 'STUDENT_ID_PREFIX' else 'SCH')
                    config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                    config.value = val
                    config.save()
                messages.success(request, 'Student ID settings saved successfully.')
                return redirect('admin:core_configuration_student_id_settings')
        else:
            form = StudentIdSettingsForm(initial={
                'STUDENT_ID_PREFIX': Configuration.get('STUDENT_ID_PREFIX', 'STU', editable=True),
                'SCHOOL_STUDENT_ID_PREFIX': Configuration.get('SCHOOL_STUDENT_ID_PREFIX', 'SCH', editable=True),
            })

        context = {
            **self.admin_site.each_context(request),
            'title': 'Student ID Settings',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/core/configuration/student_id_settings.html', context)

    def psychometric_settings_view(self, request):
        """Custom admin view for Psychometric Test Settings."""
        from core.models import Configuration

        def _config_bool(key):
            try:
                val = Configuration.get(key, default='true', editable=True)
                return str(val).lower() in ('true', '1', 'yes', 'on')
            except Exception:
                return True

        if request.method == 'POST':
            form = PsychometricSettingsForm(request.POST)
            if form.is_valid():
                for key in ['ENABLE_ANSWERING_CAREFULLY_WIDGET', 'ENABLE_AUTO_FORWARD', 'SHOW_MISSING_ANSWERS_VALIDATION']:
                    val = 'true' if form.cleaned_data.get(key, False) else 'false'
                    config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                    config.value = val
                    config.save()
                messages.success(request, 'Psychometric test settings saved successfully.')
                return redirect('admin:core_configuration_psychometric_settings')
        else:
            form = PsychometricSettingsForm(initial={
                'ENABLE_ANSWERING_CAREFULLY_WIDGET': _config_bool('ENABLE_ANSWERING_CAREFULLY_WIDGET'),
                'ENABLE_AUTO_FORWARD': _config_bool('ENABLE_AUTO_FORWARD'),
                'SHOW_MISSING_ANSWERS_VALIDATION': _config_bool('SHOW_MISSING_ANSWERS_VALIDATION'),
            })

        context = {
            **self.admin_site.each_context(request),
            'title': 'Psychometric Test Settings',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/core/configuration/psychometric_settings.html', context)

    def class10_aptitude_report_settings_view(self, request):
        """Custom admin view for Class 10 aptitude report stream display settings."""
        if request.method == 'POST':
            form = Class10AptitudeReportSettingsForm(request.POST)
            if form.is_valid():
                val = (form.cleaned_data.get('CLASS10_APTITUDE_STREAM_DISPLAY_MODE') or '').strip()
                if val not in dict(CLASS10_APTITUDE_STREAM_DISPLAY_MODE_CHOICES):
                    val = CLASS10_APTITUDE_STREAM_MODE_COMBINED
                config, _ = Configuration.objects.get_or_create(
                    key=CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY,
                    defaults={'value': val, 'editable': True},
                )
                config.value = val
                config.save()
                messages.success(request, 'Class 10 aptitude report settings saved successfully.')
                return redirect('admin:core_configuration_class10_aptitude_report_settings')
        else:
            stored = Configuration.get(
                CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY,
                CLASS10_APTITUDE_STREAM_MODE_COMBINED,
                editable=True,
            )
            mode = str(stored or '').strip().lower()
            if mode not in dict(CLASS10_APTITUDE_STREAM_DISPLAY_MODE_CHOICES):
                mode = CLASS10_APTITUDE_STREAM_MODE_COMBINED
            form = Class10AptitudeReportSettingsForm(initial={
                'CLASS10_APTITUDE_STREAM_DISPLAY_MODE': mode,
            })

        context = {
            **self.admin_site.each_context(request),
            'title': 'Class 10 Aptitude Report Settings',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/core/configuration/class10_aptitude_report_settings.html', context)

    def class12_aptitude_report_settings_view(self, request):
        """Custom admin view for Class 12 aptitude consolidated report display settings."""
        from core.models import Configuration

        if request.method == 'POST':
            form = Class12AptitudeReportSettingsForm(request.POST)
            if form.is_valid():
                val = (form.cleaned_data.get('CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE') or '').strip()
                if val not in dict(CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_CHOICES):
                    val = CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY
                config, _ = Configuration.objects.get_or_create(
                    key=CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_KEY,
                    defaults={'value': val, 'editable': True},
                )
                config.value = val
                config.save()
                from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
                clear_consolidated_lookup_cache()
                messages.success(request, 'Class 12 aptitude report settings saved successfully.')
                return redirect('admin:core_configuration_class12_aptitude_report_settings')
        else:
            stored = Configuration.get(
                CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_KEY,
                CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
                editable=True,
            )
            mode = str(stored or '').strip().lower()
            if mode not in dict(CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_CHOICES):
                mode = CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY
            form = Class12AptitudeReportSettingsForm(initial={
                'CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE': mode,
            })

        context = {
            **self.admin_site.each_context(request),
            'title': 'Class 12 Aptitude Report Settings',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/core/configuration/class12_aptitude_report_settings.html', context)

    def website_settings_view(self, request):
        """Custom admin view for Core website settings (e.g. mindmap)."""
        from core.models import Configuration

        def _config_bool(key):
            try:
                val = Configuration.get(key, default='true', editable=True)
                return str(val).lower() in ('true', '1', 'yes', 'on')
            except Exception:
                return True

        if request.method == 'POST':
            form = WebsiteSettingsForm(request.POST)
            if form.is_valid():
                # ENABLE_CAREER_MINDMAP
                key = 'ENABLE_CAREER_MINDMAP'
                val = 'true' if form.cleaned_data.get(key, False) else 'false'
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = val
                config.save()
                # ENABLE_COUNSELOR_COURSE_MINDMAP
                key = 'ENABLE_COUNSELOR_COURSE_MINDMAP'
                val = 'true' if form.cleaned_data.get(key, False) else 'false'
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = val
                config.save()
                # DEFAULT_MINDMAP_TYPE
                key = 'DEFAULT_MINDMAP_TYPE'
                val = coerce_default_mindmap_type((form.cleaned_data.get(key) or '6').strip() or '6')
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = str(val)
                config.save()
                # DEFAULT_course_MINDMAP_TYPE
                key = 'DEFAULT_course_MINDMAP_TYPE'
                val = (form.cleaned_data.get(key) or '7').strip() or '7'
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = str(val)
                config.save()
                # CHATBOT_DEFAULT_MODE
                key = 'CHATBOT_DEFAULT_MODE'
                val = (form.cleaned_data.get(key) or 'default').strip() or 'default'
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = str(val)
                config.save()
                # CHATBOT_PAGE_RULES
                key = 'CHATBOT_PAGE_RULES'
                val = (form.cleaned_data.get(key) or '[]').strip() or '[]'
                # Validate JSON so admin cannot save invalid config
                try:
                    import json
                    parsed = json.loads(val)
                    if not isinstance(parsed, list):
                        raise ValueError("Rules JSON must be a list")
                except Exception as e:
                    form.add_error('CHATBOT_PAGE_RULES', f'Invalid JSON: {e}')
                    context = {
                        **self.admin_site.each_context(request),
                        'title': 'Core website settings',
                        'form': form,
                        'opts': self.model._meta,
                    }
                    return render(request, 'admin/core/configuration/website_settings.html', context)
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = val
                config.save()

                # DASHBOARD_TEMPLATE_VERSION
                key = 'DASHBOARD_TEMPLATE_VERSION'
                val = (form.cleaned_data.get(key) or 'v1').strip() or 'v1'
                if val not in ('v1', 'v2'):
                    val = 'v1'
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = val
                config.save()

                key = 'TTV2_PAGE_LOADER_ENABLED'
                val = 'true' if form.cleaned_data.get(key, False) else 'false'
                config, _ = Configuration.objects.get_or_create(key=key, defaults={'value': val, 'editable': True})
                config.value = val
                config.save()

                messages.success(request, 'Core website settings saved successfully.')
                return redirect('admin:core_configuration_website_settings')
        else:
            default_type = coerce_default_mindmap_type(
                Configuration.get('DEFAULT_MINDMAP_TYPE', '6', editable=True) or '6'
            )
            default_course_mm = Configuration.get('DEFAULT_course_MINDMAP_TYPE', '7', editable=True) or '7'
            dashboard_template_version = (Configuration.get('DASHBOARD_TEMPLATE_VERSION', 'v1', editable=True) or 'v1').strip() or 'v1'
            if dashboard_template_version not in ('v1', 'v2'):
                dashboard_template_version = 'v1'
            form = WebsiteSettingsForm(initial={
                'ENABLE_CAREER_MINDMAP': _config_bool('ENABLE_CAREER_MINDMAP'),
                'ENABLE_COUNSELOR_COURSE_MINDMAP': _config_bool('ENABLE_COUNSELOR_COURSE_MINDMAP'),
                'DEFAULT_MINDMAP_TYPE': default_type,
                'DEFAULT_course_MINDMAP_TYPE': default_course_mm,
                'CHATBOT_DEFAULT_MODE': Configuration.get('CHATBOT_DEFAULT_MODE', 'default', editable=True) or 'default',
                'CHATBOT_PAGE_RULES': Configuration.get('CHATBOT_PAGE_RULES', '[]', editable=True) or '[]',
                'DASHBOARD_TEMPLATE_VERSION': dashboard_template_version,
                'TTV2_PAGE_LOADER_ENABLED': _config_bool('TTV2_PAGE_LOADER_ENABLED'),
            })

        context = {
            **self.admin_site.each_context(request),
            'title': 'Core website settings',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/core/configuration/website_settings.html', context)

    def dashboard_statistics_view(self, request):
        """Landing page for Dashboard Statistics (gamification) section with links to Level Bands, Point Rules, Trophies, Streak Config."""
        from users.models import User
        preview_user = None
        preview_stats = None
        try:
            from core.dashboard_stats import get_student_dashboard_stats

            user_id = request.GET.get("user_id")
            if user_id:
                preview_user = User.objects.filter(id=int(user_id)).first()
            if not preview_user:
                preview_user = User.objects.order_by("-id").first()
            if preview_user:
                preview_stats = get_student_dashboard_stats(preview_user)
        except Exception:
            preview_user = None
            preview_stats = None

        context = {
            **self.admin_site.each_context(request),
            'title': 'Dashboard Statistics (Student dashboard)',
            'opts': self.model._meta,
            'level_bands_url': reverse('admin:gamification_dashboardlevelband_changelist'),
            'point_rules_url': reverse('admin:gamification_dashboardpointrule_changelist'),
            'trophy_defs_url': reverse('admin:gamification_dashboardtrophydefinition_changelist'),
            'streak_config_url': reverse('admin:gamification_dashboardstreakconfig_changelist'),
            'preview_user': preview_user,
            'preview_stats': preview_stats,
        }
        try:
            from core.dashboard_points import get_active_point_rules_total, get_max_achievable_points_by_track
            caps = get_max_achievable_points_by_track()
            context['max_achievable_points'] = caps['post_matric']
            context['max_achievable_points_class10'] = caps['class10']
        except Exception:
            context['max_achievable_points'] = None
            context['max_achievable_points_class10'] = None
        return render(request, 'admin/core/configuration/dashboard_statistics.html', context)


class CityAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','state']
    # date_hierarchy = 'created'  # Disabled: Requires MySQL timezone tables to be loaded
    list_display = ['id', 'name','state','country','modified']
    sortable_by=['id', 'name','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['name','id']
    list_display_links=['id','name']

    def country(self,obj):
        if obj.state and obj.state.country:
            return obj.state.country.name
        return ''


class StateAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','country']
    # date_hierarchy = 'created'  # Disabled: Requires MySQL timezone tables to be loaded
    list_display = ['id', 'name','country','modified']
    sortable_by=['id', 'name','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['name','id']
    list_display_links=['id','name']




class CountryAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','phone_code','short_name','priority','flag']
    # date_hierarchy = 'created'  # Disabled: Requires MySQL timezone tables to be loaded
    list_display = ['id', 'name','short_name','modified']
    sortable_by=['id', 'name','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['name','id']
    list_display_links=['id','name']

class ContactAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','mobile','email','message']
    list_display = ['id','name','email']
    list_display_links=['id','name']
    search_fields=['name','email']
    list_filter = ['created','modified','name','email']

class LeadAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','mobile']
    list_display = ['id','name','mobile']
    list_display_links=['id','name']
    search_fields=['name']
    list_filter = ['created','modified']

class DashboardLevelBandForm(forms.ModelForm):
    class Meta:
        model = DashboardLevelBand
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.dashboard_points import get_min_level_band_points, get_active_point_rules_total
        self.fields['min_points'].widget.attrs.update({
            'min': get_min_level_band_points(),
            'max': get_active_point_rules_total(),
            'class': 'dashboard-level-band-min-points-input',
            'style': 'width: 4.5em; text-align: center;',
        })

    def clean_min_points(self):
        from core.dashboard_points import validate_level_band_min_points
        min_points = self.cleaned_data.get('min_points')
        if min_points is not None:
            error = validate_level_band_min_points(min_points)
            if error:
                raise ValidationError(error)
        return min_points


class DashboardLevelBandAdmin(admin.ModelAdmin):
    form = DashboardLevelBandForm
    list_display = ('id', 'name', 'min_points', 'order', 'points_cap_status', 'modified')
    list_editable = ('name', 'min_points', 'order')
    ordering = ('order', 'min_points')
    search_fields = ('name',)
    change_list_template = 'admin/core/dashboardlevelband/change_list.html'
    change_form_template = 'admin/core/dashboardlevelband/change_form.html'

    class Media:
        css = {'all': ('admin/css/dashboard_level_band_min_points.css',)}
        js = ('admin/js/dashboard_level_band_min_points.js',)

    @admin.display(description='Cap status')
    def points_cap_status(self, obj):
        from core.dashboard_points import (
            get_valid_level_band_min_points,
            get_active_point_rules_total,
            get_min_level_band_points,
        )
        valid = get_valid_level_band_min_points()
        max_pts = get_active_point_rules_total()
        min_pts = get_min_level_band_points()
        if obj.min_points > max_pts:
            return format_html(
                '<span style="color:#ba2121;" title="Exceeds active point rules total ({} pts)">Over max</span>',
                max_pts,
            )
        if obj.min_points < min_pts:
            return format_html(
                '<span style="color:#ba2121;" title="Below account registration ({} pts)">Below min</span>',
                min_pts,
            )
        if obj.min_points not in valid:
            return format_html(
                '<span style="color:#ba2121;" title="Not a cumulative milestone from point rules">Invalid</span>'
            )
        return format_html('<span style="color:#0a0;">OK</span>')

    def changelist_view(self, request, extra_context=None):
        extra_context = self._inject_level_band_point_context(extra_context) or {}
        return super().changelist_view(request, extra_context=extra_context)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = self._inject_level_band_point_context(extra_context) or {}
        return super().changeform_view(request, object_id, form_url, extra_context)

    def _inject_level_band_point_context(self, extra_context):
        from core.dashboard_points import (
            get_cumulative_point_milestones,
            get_registration_points,
            get_min_level_band_points,
            get_valid_level_band_min_points,
            get_max_achievable_points_by_track,
        )
        from core.psychometric_grade import get_rule_applies_to_label
        if extra_context is None:
            extra_context = {}
        caps = get_max_achievable_points_by_track()
        extra_context['max_achievable_points'] = caps['post_matric']
        extra_context['max_achievable_points_class10'] = caps['class10']
        extra_context['min_achievable_points'] = get_min_level_band_points()
        extra_context['registration_points'] = get_registration_points()
        extra_context['point_milestones'] = [
            {
                **milestone,
                'applies_to': get_rule_applies_to_label(milestone['rule_key']),
            }
            for milestone in get_cumulative_point_milestones()
        ]
        extra_context['valid_milestone_points'] = sorted(get_valid_level_band_min_points())
        extra_context['point_rules_url'] = reverse('admin:gamification_dashboardpointrule_changelist')
        return extra_context


class DashboardPointRuleAdmin(admin.ModelAdmin):
    list_display = ('order', 'label_display', 'rule_key', 'points', 'applies_to', 'active', 'modified')
    list_editable = ('order', 'points', 'applies_to', 'active')
    list_display_links = ('label_display', 'rule_key')
    list_filter = ('active', 'applies_to')
    ordering = ('order', 'rule_key')
    search_fields = ('rule_key',)
    change_list_template = 'admin/core/dashboardpointrule/change_list.html'
    readonly_fields = ('created', 'modified')

    @admin.display(description='Rule')
    def label_display(self, obj):
        from core.dashboard_stats import RULE_LABELS
        return RULE_LABELS.get(obj.rule_key, obj.rule_key.replace('_', ' ').title())

    def changelist_view(self, request, extra_context=None):
        from core.dashboard_points import get_active_point_rules_total, get_max_achievable_points_by_track
        from django.db.models import Sum
        extra_context = extra_context or {}
        qs = self.get_queryset(request)
        if request.GET.get('active__exact') == '1':
            qs = qs.filter(active=True)
        elif request.GET.get('active__exact') == '0':
            qs = qs.filter(active=False)
        total = qs.aggregate(total=Sum('points'))['total'] or 0
        extra_context['points_total'] = int(total)
        extra_context['level_bands_url'] = reverse('admin:gamification_dashboardlevelband_changelist')
        caps = get_max_achievable_points_by_track()
        extra_context['max_achievable_points'] = caps['post_matric']
        extra_context['max_achievable_points_class10'] = caps['class10']
        return super().changelist_view(request, extra_context=extra_context)


class DashboardTrophyDefinitionAdmin(admin.ModelAdmin):
    list_display = ('id', 'rule_key', 'label', 'applies_to', 'resolved_applies_to_display', 'active', 'modified')
    list_editable = ('label', 'applies_to', 'active')
    list_filter = ('active', 'applies_to')
    ordering = ('rule_key',)
    search_fields = ('rule_key', 'label')
    readonly_fields = ('created', 'modified', 'resolved_applies_to_display')

    @admin.display(description='Effective applies to')
    def resolved_applies_to_display(self, obj):
        from core.psychometric_grade import get_rule_applies_to_label
        return get_rule_applies_to_label(obj.rule_key, obj.applies_to or '')


class DashboardStreakConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'activity_source', 'event_types', 'modified')
    list_editable = ('activity_source', 'event_types')
    ordering = ('id',)

    def has_add_permission(self, request):
        return not DashboardStreakConfig.objects.exists()
    def has_delete_permission(self, request, obj=None):
        return True


admin.site.register(Configuration,ConfigurationAdmin)
admin.site.register(City,CityAdmin)
admin.site.register(State,StateAdmin)
admin.site.register(Country,CountryAdmin)
admin.site.register(Lead,LeadAdmin)


class ReviewAdmin(admin.ModelAdmin):
    """Admin CRUD for student testimonials (home page success stories). Images upload to S3 media bucket."""
    list_display = ("id", "name", "profession", "priority", "publish_status", "image_thumbnail", "object_status", "created")
    list_filter = ("publish_status", "object_status", "created")
    search_fields = ("name", "profession", "description")
    list_editable = ("priority", "publish_status")
    ordering = ("priority", "created")
    list_display_links = ("id", "name")
    S3_MEDIA_FOLDER = "media/student-testimonials"
    fieldsets = (
        (None, {
            "fields": ("name", "profession", "quote", "description", "image", "image_s3_url", "priority", "publish_status", "object_status"),
            "description": "Student testimonial shown in the “Your Success Is Our Story” section. Quote = short headline (no repetition with description). Upload an image to store it in the S3 media bucket (folder: media/student-testimonials).",
        }),
        ("Timestamps", {
            "fields": ("created", "modified"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created", "modified", "image_s3_url")

    def get_queryset(self, request):
        """Show all testimonials in admin (including inactive/soft-deleted)."""
        return self.model.objects.complete()

    def image_thumbnail(self, obj):
        url = obj.get_image_url()
        if url and url != "/static/images/review-default.png":
            return format_html(
                '<img src="{}" style="max-width: 50px; max-height: 50px; object-fit: cover; border-radius: 4px;" />',
                url,
            )
        return "—"
    image_thumbnail.short_description = "Photo"

    def save_model(self, request, obj, form, change):
        """Upload testimonial image to S3 media bucket; store URL in image_s3_url."""
        from django.core.files.uploadedfile import UploadedFile
        from urllib.parse import urlparse

        cover_image = form.cleaned_data.get("image")
        is_new_upload = cover_image and isinstance(cover_image, UploadedFile) and getattr(cover_image, "name", None)

        if change and obj.pk and is_new_upload and obj.image_s3_url:
            # Replace: delete old file from S3
            from core.s3_utils import get_s3_upload_service
            s3_service = get_s3_upload_service()
            parsed = urlparse(obj.image_s3_url)
            s3_key = parsed.path.lstrip("/")
            if s3_key:
                s3_file = S3FileUpload.objects.filter(s3_url=obj.image_s3_url).first()
                if s3_file:
                    s3_service.delete_file(s3_file.s3_key)
                else:
                    s3_service.delete_file(s3_key)
            obj.image_s3_url = None
        elif change and obj.pk and is_new_upload and not obj.image_s3_url:
            # Had local image only; will replace with S3
            obj.image_s3_url = None

        if is_new_upload:
            from core.s3_utils import get_s3_upload_service
            s3_service = get_s3_upload_service()
            result = s3_service.upload_file(
                file_obj=cover_image,
                folder_path=self.S3_MEDIA_FOLDER,
                description=f"Student testimonial: {obj.name}",
                uploaded_by=getattr(request.user, "username", "") or "",
            )
            if result.get("success"):
                obj.image_s3_url = result["s3_url"]
                obj.image = None
            else:
                messages.error(request, f"Image upload to S3 failed: {result.get('error', 'Unknown error')}")
                return
        super().save_model(request, obj, form, change)


admin.site.register(Review, ReviewAdmin)
admin.site.register(CommonFAQ)
admin.site.register(APILog)
admin.site.register(Stories)
admin.site.register(Contact,ContactAdmin)


@admin.register(CareerBattleFight)
class CareerBattleFightAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'cluster_name', 'winner_display', 'created')
    list_filter = ('created',)
    search_fields = ('title', 'user__email', 'cluster_name')
    readonly_fields = ('user', 'title', 'cluster_name', 'streams', 'parameters', 'result', 'created')
    ordering = ('-created',)

    def winner_display(self, obj):
        return (obj.result or {}).get('winner') or '—'
    winner_display.short_description = 'Winner'


@admin.register(CounsellingSession)
class CounsellingSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_id_short', 'first_message_at', 'last_message_at', 'crisis_flagged')
    list_filter = ('crisis_flagged', 'last_message_at')
    search_fields = ('session_id', 'user__email')
    readonly_fields = ('user', 'session_id', 'first_message_at', 'last_message_at', 'crisis_flagged')
    ordering = ('-last_message_at',)

    def session_id_short(self, obj):
        return (obj.session_id or '')[:20] + '...' if obj.session_id and len(obj.session_id) > 20 else (obj.session_id or '—')
    session_id_short.short_description = 'Session ID'


@admin.register(CareerBattleEligibilityProfile)
class CareerBattleEligibilityProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'education_background', 'stream', 'specific_area', 'study_location', 'updated')
    list_filter = ('education_background', 'stream', 'study_location')
    search_fields = ('user__email', 'stream', 'specific_area')
    readonly_fields = ('updated',)
    ordering = ('-updated',)


@admin.register(MIAssessmentResult)
class MIAssessmentResultAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "primary_style", "style_name", "updated_at")
    list_filter = ("primary_style", "updated_at")
    search_fields = ("user__email", "style_name")
    readonly_fields = ("user", "answers", "counts", "primary_style", "style_name", "style_summary", "created", "updated_at")
    ordering = ("-updated_at",)


@admin.register(EQAssessmentResult)
class EQAssessmentResultAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "ei_total", "band_label", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("user__email",)
    readonly_fields = ("user", "responses", "subscale_scores", "weighted", "ei_total", "pbi", "intrapersonal_eq", "interpersonal_eq", "adaptive_eq", "band_label", "created", "updated_at")
    ordering = ("-updated_at",)


class ExtracurricularActivityInline(admin.TabularInline):
    model = ExtracurricularActivity
    extra = 1
    fields = ("name", "image", "url", "priority", "object_status")
    ordering = ("priority", "name")
    show_change_link = True


@admin.register(ExtracurricularActivityCategory)
class ExtracurricularActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "priority", "object_status", "image")
    list_filter = ("object_status",)
    search_fields = ("name",)
    ordering = ("priority", "name")
    inlines = (ExtracurricularActivityInline,)


class ExtracurricularActivitySectionInline(admin.TabularInline):
    model = ExtracurricularActivitySection
    extra = 0
    fields = ("section_id", "title", "order", "icon", "description", "object_status")
    ordering = ("order",)
    show_change_link = True


@admin.register(ExtracurricularActivity)
class ExtracurricularActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "priority", "object_status", "image")
    list_filter = ("object_status", "category")
    search_fields = ("name", "category__name")
    ordering = ("category__priority", "category__name", "priority", "name")
    fields = ("category", "name", "slug", "image", "url", "content_html", "priority", "object_status", "created", "modified")
    readonly_fields = ("created", "modified")
    inlines = (ExtracurricularActivitySectionInline,)


@admin.register(ExtracurricularActivitySection)
class ExtracurricularActivitySectionAdmin(admin.ModelAdmin):
    list_display = ("id", "activity", "section_id", "title", "order", "object_status")
    list_filter = ("object_status", "section_id")
    search_fields = ("activity__name", "title", "section_id")
    ordering = ("activity__category__priority", "activity__category__name", "activity__priority", "activity__name", "order")
    fields = ("activity", "section_id", "title", "content_html", "order", "icon", "description", "object_status", "created", "modified")
    readonly_fields = ("created", "modified")


class VocationalCourseInline(admin.TabularInline):
    model = VocationalCourse
    extra = 0
    fields = ("name", "image", "priority", "object_status")
    ordering = ("priority", "name")
    show_change_link = True


@admin.register(VocationalCourseCategory)
class VocationalCourseCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "parent", "priority", "object_status", "image")
    list_filter = ("object_status", "parent")
    search_fields = ("name", "parent__name")
    ordering = ("parent__name", "priority", "name")
    inlines = (VocationalCourseInline,)


class EntranceTestPrepExamInline(admin.TabularInline):
    model = EntranceTestPrepExam
    extra = 0
    fields = ("name", "image", "priority", "object_status")
    ordering = ("priority", "name")
    show_change_link = True


def _entrance_test_prep_category_ids_with_descendants(category_ids):
    """Return set of category PKs including all descendants (recursive)."""
    from core.models import EntranceTestPrepCategory
    ids = set(EntranceTestPrepCategory._base_manager.filter(pk__in=category_ids).values_list("pk", flat=True))
    while True:
        children = set(
            EntranceTestPrepCategory._base_manager.filter(parent_id__in=ids).values_list("pk", flat=True)
        )
        if not children or children <= ids:
            break
        ids |= children
    return ids


def _hard_delete_entrance_test_prep_categories(category_ids):
    """Hard delete these categories and all exams/sections under them. category_ids must include descendants."""
    if not category_ids:
        return 0, 0
    ids = set(category_ids)
    # Delete exams (sections CASCADE)
    exam_deleted = EntranceTestPrepExam._base_manager.filter(category_id__in=ids).delete()[0]
    # Delete categories leaf-first (so parent is deleted after its children)
    cat_deleted = 0
    while ids:
        # In our set, which ids have a child that is also in our set?
        has_child_in_set = set(
            EntranceTestPrepCategory._base_manager.filter(
                parent_id__in=ids, pk__in=ids
            ).values_list("parent_id", flat=True)
        )
        leaves = ids - has_child_in_set
        if not leaves:
            break
        EntranceTestPrepCategory._base_manager.filter(pk__in=leaves).delete()
        cat_deleted += len(leaves)
        ids -= leaves
    return exam_deleted, cat_deleted


@admin.register(EntranceTestPrepCategory)
class EntranceTestPrepCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name_link", "parent", "priority", "object_status", "image", "hard_delete_link")
    list_display_links = ("name_link",)
    list_filter = ("object_status", "parent")
    search_fields = ("name", "parent__name")
    ordering = ("parent__name", "priority", "name")
    inlines = (EntranceTestPrepExamInline,)
    actions = ["action_hard_delete_categories"]

    def name_link(self, obj):
        """Link category name to subcategories/exams page instead of change form."""
        url = reverse("admin:core_entrancetestprepcategory_subcategories", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.name)
    name_link.short_description = "Name"
    name_link.admin_order_field = "name"

    def hard_delete_link(self, obj):
        """Link to hard-delete this category and all its descendants and exams."""
        url = reverse("admin:core_entrancetestprepcategory_hard_delete", args=[obj.pk])
        return format_html(
            '<a href="{}" style="color: #ba2121;" title="Hard delete (permanent)">Hard delete</a>',
            url,
        )
    hard_delete_link.short_description = "Hard delete"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/subcategories/",
                self.admin_site.admin_view(self.subcategories_view),
                name="core_entrancetestprepcategory_subcategories",
            ),
            path(
                "<int:pk>/hard-delete/",
                self.admin_site.admin_view(self.hard_delete_category_view),
                name="core_entrancetestprepcategory_hard_delete",
            ),
        ]
        return custom + urls

    def hard_delete_category_view(self, request, pk):
        """Hard delete this category and all descendants and their exams."""
        category = get_object_or_404(EntranceTestPrepCategory._base_manager, pk=pk)
        ids = _entrance_test_prep_category_ids_with_descendants([category.pk])
        exam_deleted, cat_deleted = _hard_delete_entrance_test_prep_categories(ids)
        messages.success(
            request,
            "Hard deleted %s category(ies) and %s exam(s) (permanent)." % (cat_deleted, exam_deleted),
        )
        return redirect("admin:core_entrancetestprepcategory_changelist")

    @admin.action(description="Hard delete selected categories (permanent)")
    def action_hard_delete_categories(self, request, queryset):
        category_ids = list(queryset.values_list("pk", flat=True))
        ids = _entrance_test_prep_category_ids_with_descendants(category_ids)
        exam_deleted, cat_deleted = _hard_delete_entrance_test_prep_categories(ids)
        messages.success(
            request,
            "Hard deleted %s category(ies) and %s exam(s) (permanent)." % (cat_deleted, exam_deleted),
        )

    def subcategories_view(self, request, pk):
        """Show subcategories and exams for this category; exam links open exam page, with Preview button."""
        category = get_object_or_404(EntranceTestPrepCategory, pk=pk)
        subcategories = EntranceTestPrepCategory._base_manager.filter(parent_id=category.pk).order_by("priority", "name")
        exams = EntranceTestPrepExam._base_manager.filter(category_id=category.pk).order_by("priority", "name")
        change_url = reverse("admin:core_entrancetestprepcategory_change", args=[category.pk])
        return render(
            request,
            "admin/core/entrancetestprepcategory/subcategories.html",
            {
                "category": category,
                "subcategories": subcategories,
                "exams": exams,
                "change_url": change_url,
                "opts": self.model._meta,
                "title": f"Subcategories & exams: {category.name}",
            },
        )


class EntranceTestPrepExamSectionInline(admin.TabularInline):
    model = EntranceTestPrepExamSection
    extra = 0
    fields = ("section_id", "title", "order", "object_status")
    ordering = ("order",)
    show_change_link = True


def _draw_exam_artwork(draw, cx, cy, motif, fill_white, fill_soft):
    """Draw exam-related artwork: 0=book, 1=graduation cap, 2=document, 3=lightbulb. Center (cx,cy)."""
    s = 28  # scale
    if motif == 0:  # Open book
        draw.rectangle([cx - s * 2, cy - s, cx - 2, cy + s], outline=fill_white, fill=fill_soft, width=2)
        draw.rectangle([cx + 2, cy - s, cx + s * 2, cy + s], outline=fill_white, fill=fill_soft, width=2)
        draw.line([cx - 2, cy - s, cx - 2, cy + s], fill=fill_white, width=2)
        draw.line([cx + 2, cy - s, cx + 2, cy + s], fill=fill_white, width=2)
        for y in (cy - 8, cy, cy + 8):
            draw.line([cx - s * 2 + 6, y, cx - 4, y], fill=fill_white)
            draw.line([cx + 4, y, cx + s * 2 - 6, y], fill=fill_white)
    elif motif == 1:  # Graduation cap
        draw.polygon([(cx, cy - s - 10), (cx - s - 5, cy + 5), (cx + s + 5, cy + 5)], outline=fill_white, fill=fill_soft, width=2)
        draw.rectangle([cx - s - 8, cy + 2, cx + s + 8, cy + 14], outline=fill_white, fill=fill_soft, width=2)
        draw.ellipse([cx + s - 4, cy + 6, cx + s + 8, cy + 18], outline=fill_white, fill=fill_white)
    elif motif == 2:  # Document with check
        draw.rounded_rectangle([cx - s * 2, cy - s - 5, cx + s * 2, cy + s + 5], radius=6, outline=fill_white, fill=fill_soft, width=2)
        for i, y in enumerate([cy - s + 8, cy - 4, cy + 6, cy + 16]):
            draw.line([cx - s * 2 + 12, y, cx + s * 2 - 12, y], fill=fill_white)
        draw.ellipse([cx + s - 10, cy - s, cx + s * 2 - 8, cy - s + 18], outline=fill_white, fill=fill_soft, width=2)
        draw.line([cx + s - 4, cy - s + 8, cx + s + 2, cy - s + 14], fill=fill_white, width=2)
        draw.line([cx + s + 4, cy - s + 4, cx + s + 2, cy - s + 14], fill=fill_white, width=2)
    else:  # 3: Lightbulb (idea/study)
        draw.ellipse([cx - s, cy - s - 15, cx + s, cy + s - 15], outline=fill_white, fill=fill_soft, width=2)
        draw.rectangle([cx - 12, cy + s - 22, cx + 12, cy + s - 8], outline=fill_white, fill=fill_soft, width=2)
        for dx in (-18, 0, 18):
            draw.line([cx + dx, cy - s - 18, cx + dx + 6, cy - s - 28], fill=fill_white)
            draw.line([cx + dx, cy - s - 18, cx + dx - 6, cy - s - 28], fill=fill_white)


def _generate_exam_placeholder_image(exam, width=400, height=300):
    """Generate a unique placeholder image with exam-related artwork (no category copy). Returns bytes (PNG) or None."""
    try:
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont
        palette = (
            (63, 55, 201), (91, 84, 212), (99, 102, 241),
            (129, 140, 248), (79, 70, 229), (67, 56, 202),
        )
        idx = (exam.pk or hash(exam.name)) % len(palette)
        base_color = palette[idx]
        img = Image.new("RGB", (width, height), color=base_color)
        draw = ImageDraw.Draw(img)
        for i in range(height):
            blend = 1 - (i / height) * 0.12
            r, g, b = int(base_color[0] * blend), int(base_color[1] * blend), int(base_color[2] * blend)
            draw.line([(0, i), (width, i)], fill=(r, g, b))
        fill_white = (255, 255, 255)
        fill_soft = (240, 240, 255)
        motif = (exam.pk or hash(exam.name)) % 4
        cx, cy = width // 2, height // 2 - 25
        _draw_exam_artwork(draw, cx, cy, motif, fill_white, fill_soft)
        label = (exam.name[:26] + "…") if len(exam.name) > 26 else exam.name
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        except Exception:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 26)
            except Exception:
                font = ImageFont.load_default()
        if hasattr(draw, "textbbox"):
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        else:
            tw, th = draw.textsize(label, font=font)
        tx, ty = (width - tw) // 2, height // 2 + 45
        draw.text((tx + 1, ty + 1), label, fill=(30, 30, 50), font=font)
        draw.text((tx, ty), label, fill=(255, 255, 255), font=font)
        try:
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except Exception:
            font_small = ImageFont.load_default()
        draw.text((14, 12), "Entrance Exam", fill=(255, 255, 255), font=font_small)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None


class EntranceTestPrepCategoryWithCountFilter(admin.SimpleListFilter):
    """Category filter showing Level » Category (count) so users can locate category/subcategory easily."""
    title = "Category"
    parameter_name = "category"

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        from django.db.models import Count
        # Categories that have at least one exam in current admin queryset, with count
        counts = (
            qs.values("category_id")
            .annotate(exam_count=Count("id"))
            .order_by("category_id")
        )
        cat_ids = [c["category_id"] for c in counts if c["category_id"]]
        if not cat_ids:
            return []
        count_map = {c["category_id"]: c["exam_count"] for c in counts}
        categories = EntranceTestPrepCategory.objects.filter(
            pk__in=cat_ids
        ).select_related("parent").order_by("parent__name", "name")
        return [
            (str(cat.pk), "{} » {} ({})".format(
                cat.parent.name if cat.parent else "(level)",
                cat.name,
                count_map.get(cat.pk, 0),
            ))
            for cat in categories
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category_id=self.value())
        return queryset


def _normalize_entrance_exam_sections_admin_fast(raw_sections):
    """Same merge + blank filter as the public exam detail page (single source of truth)."""
    from core import views as core_views

    return core_views._normalize_entrance_exam_sections(raw_sections)


def _exam_has_db_sections_no_extra_query(exam):
    """Use prefetch cache when present; avoid per-exam EXISTS() queries."""
    cache = getattr(exam, "_prefetched_objects_cache", None)
    if cache is not None and "sections" in cache:
        return len(cache["sections"]) > 0
    return exam.sections.exists()


class EntranceTestPrepAccordionErrorsFilter(admin.SimpleListFilter):
    """Filter by stored accordion validation (DB; updated by Validate accordion)."""
    title = "Accordion"
    parameter_name = "etp_accordion"

    def lookups(self, request, model_admin):
        # Do not add ("", "All") — Django's SimpleListFilter already renders "All"
        # (removes this parameter); a duplicate "All" confuses which link is selected.
        return (
            ("1", "With accordion errors"),
            ("0", "No errors (validated OK)"),
            ("pending", "Not validated yet"),
        )

    def queryset(self, request, queryset):
        v = self.value()
        if v == "1":
            return queryset.filter(accordion_validation_has_errors=True)
        if v == "0":
            return queryset.filter(
                accordion_validation_checked_at__isnull=False,
                accordion_validation_has_errors=False,
            )
        if v == "pending":
            return queryset.filter(accordion_validation_checked_at__isnull=True)
        return queryset


def _entrance_test_prep_exam_accordion_issues(exam):
    """
    List human-readable issues: blank section bodies (same rules as public _section_html_is_blank),
    and exams with content sources but zero visible accordion panels after normalize.
    Uses the same raw builder and _normalize_entrance_exam_sections as the public page.
    """
    from core import views as core_views

    raw = core_views.build_entrance_test_prep_exam_sections_raw(exam)
    errors = []
    for s in raw:
        label = core_views._strip_heading_numbers(s.get("title") or s.get("section_id") or "Section")
        if core_views._section_html_is_blank(s.get("content_html")):
            errors.append(f"{label}: blank (hidden on site)")
    final = _normalize_entrance_exam_sections_admin_fast(raw)
    cj = getattr(exam, "content_json", None)
    has_source = bool(
        (exam.content_html or "").strip()
        or _exam_has_db_sections_no_extra_query(exam)
        or (isinstance(cj, dict) and bool(cj))
    )
    if not final and has_source:
        errors.append("No visible accordion sections (all blank or unresolved)")
    return errors


@admin.register(EntranceTestPrepExam)
class EntranceTestPrepExamAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "accordion_validation",
        "category_name_safe",
        "priority",
        "object_status",
        "preview_link",
        "image_safe",
        "hard_delete_exam_link",
    )
    list_filter = (EntranceTestPrepAccordionErrorsFilter, "object_status", EntranceTestPrepCategoryWithCountFilter)
    search_fields = ("name", "category__name")
    ordering = ("category__name", "priority", "name")
    actions = ["action_hard_delete_exams"]
    fieldsets = (
        ("Basic Information", {"fields": ("category", "name", "slug", "image", "priority", "object_status")}),
        (
            "Content",
            {
                "fields": ("content_html", "content_json"),
                "description": "Edit content_html to generate accordion structure. Use the Content Editor and 'Generate Accordion from Content' below. The content_json field is auto-saved on form submit.",
            },
        ),
        (
            "Accordion validation (cached)",
            {
                "fields": (
                    "accordion_validation_has_errors",
                    "accordion_validation_checked_at",
                    "accordion_validation_issues",
                ),
                "classes": ("collapse",),
                "description": "Updated when you run Validate accordion on the exam list. Cleared when content_html / content_json or inline sections change.",
            },
        ),
        ("Timestamps", {"fields": ("created", "modified"), "classes": ("collapse",)}),
    )
    readonly_fields = (
        "created",
        "modified",
        "accordion_validation_has_errors",
        "accordion_validation_checked_at",
        "accordion_validation_issues",
    )
    change_form_template = "admin/core/entrancetestprepexam/change_form.html"
    change_list_template = "admin/core/entrancetestprepexam/change_list.html"

    class Media:
        css = {"all": ("admin/css/hide_content_json.css",)}

    def save_model(self, request, obj, form, change):
        import json
        import logging

        logger = logging.getLogger(__name__)
        content_json_str = request.POST.get("content_json", "")
        if content_json_str:
            try:
                obj.content_json = json.loads(content_json_str)
                logger.info(
                    "Saved content_json for EntranceTestPrepExam %s. Sections: %s",
                    obj.id or "new",
                    len((obj.content_json or {}).get("sections", {})),
                )
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Invalid content_json for exam: %s", e)
                if not change:
                    obj.content_json = None
        invalidate = (
            change
            and getattr(form, "changed_data", ())
            and any(f in form.changed_data for f in ("content_html", "content_json"))
        )
        super().save_model(request, obj, form, change)
        if invalidate and obj.pk:
            EntranceTestPrepExam.objects.filter(pk=obj.pk).update(
                accordion_validation_checked_at=None,
                accordion_validation_issues=[],
                accordion_validation_has_errors=False,
            )

    def category_name_safe(self, obj):
        try:
            return obj.category.name if obj.category_id and getattr(obj, "category", None) else "-"
        except Exception:
            return "-"
    category_name_safe.short_description = "Category"
    category_name_safe.admin_order_field = "category__name"

    def image_safe(self, obj):
        try:
            return "Yes" if obj.image else "-"
        except Exception:
            return "-"
    image_safe.short_description = "Image"

    def preview_link(self, obj):
        if not obj or not getattr(obj, "id", None):
            return "-"
        try:
            url = reverse("core:entrance_test_prep_exam_detail", kwargs={"slug": obj.slug})
            return format_html(
                '<a href="{}" target="_blank" style="color: green; font-weight: 600; text-decoration: none;">View</a>',
                url,
            )
        except Exception:
            return "-"
    preview_link.short_description = "Preview"
    preview_link.admin_order_field = "name"

    def accordion_validation(self, obj):
        """Stored DB result; JS refreshes row after Validate accordion."""
        if not obj or not getattr(obj, "id", None):
            return "—"
        checked = obj.accordion_validation_checked_at
        issues = obj.accordion_validation_issues or []
        name_esc = conditional_escape((obj.name or "")[:80])
        if checked is None:
            return format_html(
                '<span class="etp-accordion-validation" data-pk="{}" data-name="{}" title="Run Validate accordion to compute and save">—</span>',
                obj.pk,
                name_esc,
            )
        if issues:
            title = conditional_escape("\n".join(str(x) for x in issues))
            return format_html(
                '<span class="etp-accordion-validation" data-pk="{}" data-name="{}" title="{}">'
                '<span style="color:#ba2121;cursor:help">&#9888;</span></span>',
                obj.pk,
                name_esc,
                title,
            )
        return format_html(
            '<span class="etp-accordion-validation" data-pk="{}" data-name="{}" title="OK (saved)">OK</span>',
            obj.pk,
            name_esc,
        )

    accordion_validation.short_description = "Accordion"
    accordion_validation.admin_order_field = "accordion_validation_has_errors"

    def hard_delete_exam_link(self, obj):
        if not obj or not getattr(obj, "pk", None):
            return "-"
        url = reverse("admin:core_entrancetestprepexam_hard_delete", args=[obj.pk])
        return format_html(
            '<a href="{}" style="color: #ba2121;" title="Hard delete (permanent)">Hard delete</a>',
            url,
        )
    hard_delete_exam_link.short_description = "Hard delete"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "validate_accordion/",
                self.admin_site.admin_view(self.validate_accordion_view),
                name="core_entrancetestprepexam_validate_accordion",
            ),
            path(
                "regenerate-all-json/",
                self.admin_site.admin_view(self.regenerate_all_json_view),
                name="core_entrancetestprepexam_regenerate_all_json",
            ),
            path(
                "<int:pk>/hard-delete/",
                self.admin_site.admin_view(self.hard_delete_exam_view),
                name="core_entrancetestprepexam_hard_delete",
            ),
        ]
        return custom + urls

    def validate_accordion_view(self, request):
        """Run validation, persist per-exam results on the model, return JSON for the list UI."""
        from django.db.models import Prefetch

        try:
            base = self.get_queryset(request)
            pks = list(base.values_list("pk", flat=True))
            section_qs = EntranceTestPrepExamSection.objects.only(
                "exam_id", "section_id", "title", "content_html", "order"
            ).order_by("order", "section_id")
            prefetch = Prefetch("sections", queryset=section_qs)
            results = {}
            now = timezone.now()
            chunk_size = 250
            for i in range(0, len(pks), chunk_size):
                chunk_ids = pks[i : i + chunk_size]
                chunk = (
                    EntranceTestPrepExam.objects.filter(pk__in=chunk_ids)
                    .only("id", "content_html", "content_json")
                    .prefetch_related(prefetch)
                )
                by_id = {e.pk: e for e in chunk}
                for pk in chunk_ids:
                    exam = by_id.get(pk)
                    if not exam:
                        continue
                    try:
                        issues = _entrance_test_prep_exam_accordion_issues(exam)
                    except Exception as e:
                        issues = [f"Validation error: {e}"]
                    results[str(exam.pk)] = issues
                    EntranceTestPrepExam.objects.filter(pk=exam.pk).update(
                        accordion_validation_issues=issues,
                        accordion_validation_has_errors=bool(issues),
                        accordion_validation_checked_at=now,
                    )
            return JsonResponse({"results": results, "saved_count": len(results)})
        except Exception as e:
            return JsonResponse({"error": str(e), "results": {}}, status=500)

    def hard_delete_exam_view(self, request, pk):
        """Hard delete this exam (and its sections)."""
        exam = get_object_or_404(EntranceTestPrepExam._base_manager, pk=pk)
        name = exam.name
        exam.delete(hard_delete=True)
        messages.success(request, f"Hard deleted exam « {name} » (permanent).")
        return redirect("admin:core_entrancetestprepexam_changelist")

    def regenerate_all_json_view(self, request):
        """Delete all content_json and regenerate from content_html for all exams."""
        import re

        def _heading_key(title):
            key = re.sub(r"[^a-z0-9]+", "_", (title or "").lower()).strip("_")
            return key or "section"

        qs = EntranceTestPrepExam._base_manager.all().only("id", "name", "content_html")
        # Explicitly clear all stored JSON first (requested behavior).
        EntranceTestPrepExam._base_manager.update(content_json=None)

        regenerated = 0
        empty = 0
        failed = 0
        for exam in qs.iterator(chunk_size=250):
            try:
                html = (exam.content_html or "").strip()
                if not html:
                    empty += 1
                    continue

                sections = {}
                section_order = []
                open_matches = list(re.finditer(r"<h2\b[^>]*>", html, flags=re.IGNORECASE))
                preamble = html[: open_matches[0].start()].strip() if open_matches else ""

                if open_matches:
                    from bs4 import BeautifulSoup

                    first_key = None
                    for idx, m in enumerate(open_matches):
                        title_start = m.end()
                        tail = html[title_start:]
                        close_m = re.search(r"</h2>", tail, flags=re.IGNORECASE)
                        if not close_m:
                            continue
                        close_pos = title_start + close_m.start()
                        title_html = html[title_start:close_pos]
                        title = BeautifulSoup(title_html, "html.parser").get_text(separator=" ", strip=True) or f"Section {idx + 1}"
                        key = _heading_key(title)
                        base = key
                        suffix = 1
                        while key in sections:
                            key = f"{base}_{suffix}"
                            suffix += 1

                        body_start = close_pos + len(close_m.group(0))
                        body_end = open_matches[idx + 1].start() if idx + 1 < len(open_matches) else len(html)
                        body_html = html[body_start:body_end].strip()
                        sections[key] = {"title": title, "html": body_html}
                        section_order.append(key)
                        if first_key is None:
                            first_key = key

                    # Keep preamble content by prepending to first section.
                    if preamble and first_key and first_key in sections:
                        sections[first_key]["html"] = (preamble + sections[first_key].get("html", "")).strip()
                else:
                    sections["content"] = {"title": "Content", "html": html}
                    section_order = ["content"]

                first_key = section_order[0] if section_order else None
                overview_html = sections.get(first_key, {}).get("html", "") if first_key else ""
                payload = {
                    "programtitle": exam.name or "",
                    "overview": overview_html,
                    "sections": sections,
                    "section_order": section_order,
                }
                EntranceTestPrepExam._base_manager.filter(pk=exam.pk).update(
                    content_json=payload,
                    accordion_validation_checked_at=None,
                    accordion_validation_issues=[],
                    accordion_validation_has_errors=False,
                )
                regenerated += 1
            except Exception:
                failed += 1

        messages.success(
            request,
            f"JSON regenerated: {regenerated} exam(s); empty content_html: {empty}; failed: {failed}.",
        )
        return redirect("admin:core_entrancetestprepexam_changelist")

    @admin.action(description="Hard delete selected exams (permanent)")
    def action_hard_delete_exams(self, request, queryset):
        pks = list(queryset.values_list("pk", flat=True))
        count = EntranceTestPrepExam._base_manager.filter(pk__in=pks).delete()[0]
        messages.success(request, "Hard deleted %s exam(s) (permanent)." % count)


# Section headings used on vocational course detail accordion (must match template20/vocational_course_detail.html)
VOCATIONAL_ACCORDION_HEADINGS = [
    'Eligibility & Admission',
    'Duration & Structure',
    'Curriculum Highlights',
    'Skills Required',
    'Pros & Cons',
    'Internship & Industry Collaborations',
    'Certification & Accreditation',
    'Learning Outcomes',
    'Career Growth & Prospects',
    'Employment Sectors & Employers',
    'Conclusion',
]


def _html_is_effectively_blank(html):
    """
    Return True if section HTML is effectively blank. Covers:
    - Empty or only whitespace.
    - Only empty tags e.g. <p>&nbsp;</p> or <p></p> (after unescape, strip_tags -> empty).
    - No content between h2s: first block is just heading then next heading with nothing in between.
    - Only one h2 then empty tags (no second h2): strip first <h2>...</h2>, remainder is empty.
    """
    import re
    import html as html_module
    raw = (html or '').strip()
    if len(raw) <= 10:
        return True
    # Strip tags and unescape so &nbsp; and empty tags become visible
    text = strip_tags(raw)
    text = html_module.unescape(text)
    text = text.strip()
    if not text or not text.replace('\xa0', ' ').strip():
        return True
    # No content between first </h2> and next <h2>: content between h2s is empty/whitespace only
    between = re.search(r'</h2>\s*(.*?)\s*<h2', raw, re.IGNORECASE | re.DOTALL)
    if between:
        between_html = between.group(1).strip()
        between_text = strip_tags(between_html)
        between_text = html_module.unescape(between_text).strip()
        if not between_text or not between_text.replace('\xa0', ' ').strip():
            return True
    # Only first h2 then empty tags (e.g. <h2>Eligibility</h2><p>&nbsp;</p>), or last section (e.g. Conclusion) with no content after its h2
    after_first_h2 = re.sub(r'^.*?</h2>\s*', '', raw, flags=re.IGNORECASE | re.DOTALL)
    after_text = strip_tags(after_first_h2)
    after_text = html_module.unescape(after_text).strip()
    if not after_text or not after_text.replace('\xa0', ' ').strip():
        return True
    return False


class AccordionErrorsFilter(admin.SimpleListFilter):
    """Filter vocational courses by stored accordion validation (DB; updated by Validate accordion)."""
    title = "Accordion"
    parameter_name = "accordion"

    def lookups(self, request, model_admin):
        return (
            ("1", "With accordion errors"),
            ("0", "No errors (validated OK)"),
            ("pending", "Not validated yet"),
        )

    def queryset(self, request, queryset):
        v = self.value()
        if v == "1":
            return queryset.filter(accordion_validation_has_errors=True)
        if v == "0":
            return queryset.filter(
                accordion_validation_checked_at__isnull=False,
                accordion_validation_has_errors=False,
            )
        if v == "pending":
            return queryset.filter(accordion_validation_checked_at__isnull=True)
        return queryset


def _vocational_accordion_blank_sections(course):
    """Return list of section names that are blank (same logic as frontend accordion)."""
    from core.accordion_utils import vocational_accordion_blank_section_names

    return vocational_accordion_blank_section_names(
        getattr(course, "content_html", None) or "",
        getattr(course, "content_json", None),
    )


class VocationalCourseReasoningMappingInline(admin.TabularInline):
    model = VocationalCourseReasoningMapping
    extra = 1
    fields = ("reasoning_area", "priority", "object_status")


@admin.register(VocationalCourse)
class VocationalCourseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "reasoning_areas_display", "accordion_validation", "category_name_safe", "priority", "object_status", "preview_link", "image_safe")
    list_filter = (AccordionErrorsFilter, "object_status", "category")
    search_fields = ("name", "category__name")
    ordering = ("category__name", "priority", "name")
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'name', 'slug', 'image', 'priority', 'object_status')
        }),
        ('Content', {
            'fields': ('content_html', 'content_json'),
            'description': 'Edit content_html with H2 headings (one section per H2). Accordion preview uses the same parser as the public page. content_json is auto-generated on save.'
        }),
        (
            "Accordion validation (cached)",
            {
                "fields": (
                    "accordion_validation_has_errors",
                    "accordion_validation_checked_at",
                    "accordion_validation_issues",
                ),
                "classes": ("collapse",),
                "description": "Updated when you run Validate accordion on the course list. Cleared when content_html or content_json changes.",
            },
        ),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = (
        "created",
        "modified",
        "accordion_validation_has_errors",
        "accordion_validation_checked_at",
        "accordion_validation_issues",
    )
    change_form_template = "admin/core/vocationalcourse/change_form.html"
    change_list_template = "admin/core/vocationalcourse/change_list.html"
    inlines = (VocationalCourseReasoningMappingInline,)

    class Media:
        css = {
            'all': ('admin/css/hide_content_json.css',)
        }

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        preview_url = None
        if obj and getattr(obj, 'pk', None):
            try:
                preview_url = reverse('core:vocational_course_detail', kwargs={'pk': obj.pk})
            except Exception:
                preview_url = None
        context['vocational_course_frontend_preview_url'] = preview_url
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )
    
    def save_model(self, request, obj, form, change):
        """Override save_model to handle content_json from POST data"""
        import json
        import logging
        
        logger = logging.getLogger(__name__)

        from core.accordion_utils import content_json_from_html

        # Prefer live content_html (same source of truth as career descriptions)
        if obj.content_html and str(obj.content_html).strip():
            obj.content_json = content_json_from_html(obj.content_html, program_title=obj.name)
            logger.info(
                'Regenerated content_json from content_html for VocationalCourse %s. Sections: %s',
                obj.id or 'new',
                len((obj.content_json or {}).get('sections', {})),
            )
        else:
            content_json_str = request.POST.get('content_json', '')
            if not content_json_str:
                logger.warning(
                    'No content_html or content_json for VocationalCourse %s',
                    obj.id or 'new',
                )
            elif content_json_str:
                try:
                    obj.content_json = json.loads(content_json_str)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning('Invalid JSON in content_json field: %s', e)
                    if not change:
                        obj.content_json = None
        
        invalidate = (
            change
            and getattr(form, "changed_data", ())
            and any(f in form.changed_data for f in ("content_html", "content_json"))
        )
        super().save_model(request, obj, form, change)
        if invalidate and obj.pk:
            VocationalCourse.objects.filter(pk=obj.pk).update(
                accordion_validation_checked_at=None,
                accordion_validation_issues=[],
                accordion_validation_has_errors=False,
            )

    def category_name_safe(self, obj):
        """Display category name without raising if category is missing."""
        try:
            return obj.category.name if obj.category_id and getattr(obj, 'category', None) else '-'
        except Exception:
            return '-'
    category_name_safe.short_description = 'Category'
    category_name_safe.admin_order_field = 'category__name'

    def reasoning_areas_display(self, obj):
        from core import choices
        from core.choices import ReasoningArea
        if not obj or not getattr(obj, 'pk', None):
            return '-'
        areas = (
            obj.reasoning_mappings.filter(object_status=choices.ObjectStatus.ACTIVE)
            .order_by('reasoning_area')
            .values_list('reasoning_area', flat=True)
        )
        if not areas:
            return '-'
        return ', '.join(ReasoningArea.label(area) for area in areas)
    reasoning_areas_display.short_description = 'Reasoning areas'

    def image_safe(self, obj):
        """Display image indicator without raising."""
        try:
            return 'Yes' if obj.image else '-'
        except Exception:
            return '-'
    image_safe.short_description = 'Image'

    def preview_link(self, obj):
        """Display preview link that opens frontend page in new tab"""
        if not obj or not getattr(obj, 'id', None):
            return '-'
        try:
            url = reverse("core:vocational_course_detail", kwargs={"pk": obj.pk})
            return format_html(
                '<a href="{}" target="_blank" style="color: green; font-weight: 600; text-decoration: none;">🔍 View</a>',
                url,
            )
        except Exception as e:
            return format_html(
                '<span style="color: red;">Error: {}</span>',
                str(e)[:50]
            )
    preview_link.short_description = 'Preview'
    preview_link.admin_order_field = 'name'

    def accordion_validation(self, obj):
        """Stored DB result; JS refreshes row after Validate accordion."""
        if not obj or not getattr(obj, "id", None):
            return "—"
        checked = obj.accordion_validation_checked_at
        issues = obj.accordion_validation_issues or []
        name_esc = conditional_escape((obj.name or "")[:80])
        if checked is None:
            return format_html(
                '<span class="accordion-validation" data-pk="{}" data-name="{}" title="Run Validate accordion to compute and save">—</span>',
                obj.pk,
                name_esc,
            )
        if issues:
            title = conditional_escape("\n".join(str(x) for x in issues))
            return format_html(
                '<span class="accordion-validation" data-pk="{}" data-name="{}" title="{}">'
                '<span style="color:#ba2121;cursor:help">&#9888;</span></span>',
                obj.pk,
                name_esc,
                title,
            )
        return format_html(
            '<span class="accordion-validation" data-pk="{}" data-name="{}" title="OK (saved)">OK</span>',
            obj.pk,
            name_esc,
        )

    accordion_validation.short_description = "Accordion"
    accordion_validation.admin_order_field = "accordion_validation_has_errors"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'validate_accordion/',
                self.admin_site.admin_view(self.validate_accordion_view),
                name='core_vocationalcourse_validate_accordion',
            ),
            path(
                'export-reasoning-json/',
                self.admin_site.admin_view(vocational_reasoning_export_json_view),
                name='core_vocationalcourse_export_reasoning_json',
            ),
            path(
                'export-reasoning-csv/',
                self.admin_site.admin_view(vocational_reasoning_export_csv_view),
                name='core_vocationalcourse_export_reasoning_csv',
            ),
            path(
                'import-reasoning/',
                self.admin_site.admin_view(vocational_reasoning_import_view),
                name='core_vocationalcourse_import_reasoning',
            ),
        ]
        return custom + urls

    def validate_accordion_view(self, request):
        """Run validation, persist per-course results on the model; return JSON for the list UI."""
        qs = self.get_queryset(request)
        results = {}
        now = timezone.now()
        for course in qs:
            errors = _vocational_accordion_blank_sections(course)
            results[str(course.pk)] = errors
            VocationalCourse.objects.filter(pk=course.pk).update(
                accordion_validation_issues=errors,
                accordion_validation_has_errors=bool(errors),
                accordion_validation_checked_at=now,
            )
        return JsonResponse({"results": results, "saved_count": len(results)})


class VocationalCourseReasoningMappingImportForm(forms.Form):
    file = forms.FileField(label="JSON or CSV mappings file")
    dry_run = forms.BooleanField(required=False, initial=False, label="Dry run (validate only)")
    replace_all = forms.BooleanField(
        required=False,
        initial=False,
        label="Replace all (soft-delete mappings not in file)",
    )


def vocational_reasoning_export_json_view(request):
    from core.vocational_reasoning_io import export_json_bytes
    response = HttpResponse(export_json_bytes(), content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="vocational_reasoning_mappings.json"'
    return response


def vocational_reasoning_export_csv_view(request):
    from core.vocational_reasoning_io import export_csv_zip_bytes
    response = HttpResponse(export_csv_zip_bytes(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="vocational_reasoning_export.zip"'
    return response


def vocational_reasoning_import_view(request, redirect_to="admin:core_vocationalcourse_changelist"):
    from core.vocational_reasoning_io import import_mappings
    from core.models import VocationalCourseReasoningMapping

    if request.method == "POST":
        form = VocationalCourseReasoningMappingImportForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            result = import_mappings(
                upload.read(),
                filename=upload.name,
                dry_run=form.cleaned_data["dry_run"],
                replace_all=form.cleaned_data["replace_all"],
            )
            if result.errors:
                for err in result.errors:
                    messages.error(request, err)
            elif form.cleaned_data["dry_run"]:
                messages.success(
                    request,
                    f"Dry run OK: {result.created} would be created, "
                    f"{result.updated} updated, {result.deleted} deleted.",
                )
            else:
                messages.success(
                    request,
                    f"Import complete: {result.created} created, "
                    f"{result.updated} updated, {result.deleted} deleted.",
                )
                return redirect(redirect_to)
    else:
        form = VocationalCourseReasoningMappingImportForm()

    context = {
        **admin.site.each_context(request),
        "form": form,
        "title": "Import vocational reasoning mappings",
        "opts": VocationalCourseReasoningMapping._meta,
        "redirect_to": redirect_to,
    }
    return render(request, "admin/core/vocationalcoursereasoningmapping/import_form.html", context)


def _vocational_reasoning_import_view_for_mapping_admin(request):
    return vocational_reasoning_import_view(
        request,
        redirect_to="admin:core_vocationalcoursereasoningmapping_changelist",
    )


@admin.register(VocationalCourseReasoningMapping)
class VocationalCourseReasoningMappingAdmin(admin.ModelAdmin):
    list_display = (
        "reasoning_area",
        "vocational_course",
        "course_category",
        "priority",
        "object_status",
        "modified",
    )
    list_filter = ("reasoning_area", "object_status", "vocational_course__category")
    search_fields = ("vocational_course__name", "vocational_course__id")
    ordering = ("reasoning_area", "priority", "vocational_course__name")
    autocomplete_fields = ("vocational_course",)
    change_list_template = "admin/core/vocationalcoursereasoningmapping/change_list.html"

    def course_category(self, obj):
        if obj.vocational_course_id and getattr(obj.vocational_course, "category", None):
            return obj.vocational_course.category.name
        return "-"
    course_category.short_description = "Category"
    course_category.admin_order_field = "vocational_course__category__name"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "export-json/",
                self.admin_site.admin_view(vocational_reasoning_export_json_view),
                name="core_vocationalcoursereasoningmapping_export_json",
            ),
            path(
                "export-csv/",
                self.admin_site.admin_view(vocational_reasoning_export_csv_view),
                name="core_vocationalcoursereasoningmapping_export_csv",
            ),
            path(
                "import/",
                self.admin_site.admin_view(_vocational_reasoning_import_view_for_mapping_admin),
                name="core_vocationalcoursereasoningmapping_import",
            ),
        ]
        return custom + urls


class EbookAdminForm(forms.ModelForm):
    # Form-only fields (not in model)
    clear_cover_image = forms.BooleanField(required=False, label='Clear cover image')
    clear_pdf_file = forms.BooleanField(required=False, label='Clear PDF file')
    
    class Meta:
        model = Ebook
        fields = '__all__'
        exclude = []  # Don't exclude anything, but clear fields are handled separately
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.conf import settings
        s3_base_url = getattr(settings, 'S3_BUCKET_BASE_URL', 'https://topteenc.s3.ap-northeast-1.amazonaws.com/')
        s3_ebook_folder = getattr(settings, 'S3_EBOOK_FOLDER', 'ebook')
        
        # Set placeholders with S3 base URL
        cover_placeholder = f'{s3_base_url}{s3_ebook_folder}/cover/image.jpg'
        pdf_placeholder = f'{s3_base_url}{s3_ebook_folder}/media/book.pdf'
        
        # Update cover image field help text
        if 'cover_image' in self.fields:
            max_size_mb = getattr(settings, 'S3_MAX_FILE_SIZE_MB', 2)
            if self.instance and self.instance.pk:
                self.fields['cover_image'].help_text = f'Upload a new cover image to replace the existing one. Will be automatically uploaded to S3 in ebook/cover/ folder. Max size: {max_size_mb} MB'
            else:
                self.fields['cover_image'].help_text = f'Upload cover image. Will be automatically uploaded to S3 in ebook/cover/ folder. Max size: {max_size_mb} MB'
        
        # Update PDF file field help text
        if 'pdf_file' in self.fields:
            max_size_mb = getattr(settings, 'S3_MAX_FILE_SIZE_MB', 2)
            if self.instance and self.instance.pk:
                self.fields['pdf_file'].help_text = f'Upload a new PDF file to replace the existing one. Will be automatically uploaded to S3 in ebook/media/ folder. Max size: {max_size_mb} MB'
            else:
                self.fields['pdf_file'].help_text = f'Upload PDF file. Will be automatically uploaded to S3 in ebook/media/ folder. Max size: {max_size_mb} MB'
        
        # Make S3 URL fields read-only (auto-populated)
        if 'cover_image_s3_url' in self.fields:
            self.fields['cover_image_s3_url'].widget.attrs.update({
                'readonly': True,
                'style': 'width: 100%; background-color: #f5f5f5;'
            })
            self.fields['cover_image_s3_url'].help_text = 'Auto-populated after uploading cover image. To replace, upload a new file. To remove, click the "Delete" button next to this field.'
        
        if 'pdf_file_s3_url' in self.fields:
            self.fields['pdf_file_s3_url'].widget.attrs.update({
                'readonly': True,
                'style': 'width: 100%; background-color: #f5f5f5;'
            })
            self.fields['pdf_file_s3_url'].help_text = 'Auto-populated after uploading PDF file. To replace, upload a new file. To remove, click the "Delete" button next to this field.'
        
        # Configure form for editing (files are optional when editing)
        if self.instance and self.instance.pk:
            # Make file fields optional when editing (can keep existing or upload new)
            if 'cover_image' in self.fields:
                self.fields['cover_image'].required = False
            
            if 'pdf_file' in self.fields:
                self.fields['pdf_file'].required = False
        
        # Always hide clear checkboxes (we use delete buttons in template instead)
        if 'clear_cover_image' in self.fields:
            self.fields['clear_cover_image'].widget = forms.HiddenInput()
        if 'clear_pdf_file' in self.fields:
            self.fields['clear_pdf_file'].widget = forms.HiddenInput()
    
    def clean(self):
        """Validate file uploads - files will be auto-uploaded to S3"""
        cleaned_data = super().clean()
        
        # Get flags for clearing files
        clear_cover = cleaned_data.get('clear_cover_image', False)
        clear_pdf = cleaned_data.get('clear_pdf_file', False)
        
        # Validate cover image
        cover_image = cleaned_data.get('cover_image')
        cover_image_s3_url = cleaned_data.get('cover_image_s3_url')
        
        # Check if this is a new upload
        is_new_cover_upload = cover_image and hasattr(cover_image, 'name') and cover_image.name
        
        # If editing existing object, files are optional (can keep existing or upload new)
        if self.instance and self.instance.pk:
            existing_cover = self.instance.cover_image and self.instance.cover_image.name
            existing_cover_s3 = self.instance.cover_image_s3_url
            # Only require if clearing existing and no new upload
            if clear_cover and not is_new_cover_upload:
                cleaned_data['cover_image_s3_url'] = None
            elif is_new_cover_upload:
                # New file uploaded, will replace existing
                cleaned_data['cover_image_s3_url'] = None
        else:
            # New object - must have file upload
            if not is_new_cover_upload and not cover_image_s3_url:
                raise ValidationError({
                    'cover_image': 'Please upload a cover image file.'
                })
            # If file is uploaded, clear S3 URL (will be auto-populated)
            if is_new_cover_upload:
                cleaned_data['cover_image_s3_url'] = None
        
        # Validate PDF file
        pdf_file = cleaned_data.get('pdf_file')
        pdf_file_s3_url = cleaned_data.get('pdf_file_s3_url')
        
        # Check if this is a new upload
        is_new_pdf_upload = pdf_file and hasattr(pdf_file, 'name') and pdf_file.name
        
        # If editing existing object, files are optional (can keep existing or upload new)
        if self.instance and self.instance.pk:
            existing_pdf = self.instance.pdf_file and self.instance.pdf_file.name
            existing_pdf_s3 = self.instance.pdf_file_s3_url
            # Only require if clearing existing and no new upload
            if clear_pdf and not is_new_pdf_upload:
                cleaned_data['pdf_file_s3_url'] = None
            elif is_new_pdf_upload:
                # New file uploaded, will replace existing
                cleaned_data['pdf_file_s3_url'] = None
        else:
            # New object - must have file upload
            if not is_new_pdf_upload and not pdf_file_s3_url:
                raise ValidationError({
                    'pdf_file': 'Please upload a PDF file.'
                })
            # If file is uploaded, clear S3 URL (will be auto-populated)
            if is_new_pdf_upload:
                cleaned_data['pdf_file_s3_url'] = None
        
        return cleaned_data
    
    def clean_cover_image(self):
        """Validate cover image size using S3 max file size"""
        cover_image = self.cleaned_data.get('cover_image')
        if cover_image:
            # Check if it's a new upload (has file attribute)
            if hasattr(cover_image, 'size'):
                from django.conf import settings
                from core.s3_utils import get_s3_upload_service
                s3_service = get_s3_upload_service()
                max_size = s3_service.get_max_file_size()
                if cover_image.size > max_size:
                    max_size_mb = max_size / (1024 * 1024)
                    raise ValidationError(f'Cover image size must be under {max_size_mb}MB. Current size: {cover_image.size / (1024 * 1024):.2f}MB')
        return cover_image
    
    def clean_cover_image_s3_url(self):
        """Validate S3 cover image URL"""
        cover_image_s3_url = self.cleaned_data.get('cover_image_s3_url')
        if cover_image_s3_url:
            # Basic URL validation
            if not (cover_image_s3_url.startswith('http://') or cover_image_s3_url.startswith('https://')):
                raise ValidationError('S3 URL must start with http:// or https://')
        return cover_image_s3_url
    
    def clean_pdf_file(self):
        """Validate PDF file size using S3 max file size"""
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file:
            # Check if it's a new upload (has file attribute)
            if hasattr(pdf_file, 'size'):
                from django.conf import settings
                from core.s3_utils import get_s3_upload_service
                s3_service = get_s3_upload_service()
                max_size = s3_service.get_max_file_size()
                if pdf_file.size > max_size:
                    max_size_mb = max_size / (1024 * 1024)
                    raise ValidationError(f'PDF file size must be under {max_size_mb}MB. Current size: {pdf_file.size / (1024 * 1024):.2f}MB')
                # Check file extension
                if not pdf_file.name.lower().endswith('.pdf'):
                    raise ValidationError('Only PDF files are allowed.')
        return pdf_file
    
    def clean_pdf_file_s3_url(self):
        """Validate S3 PDF URL"""
        pdf_file_s3_url = self.cleaned_data.get('pdf_file_s3_url')
        if pdf_file_s3_url:
            # Basic URL validation
            if not (pdf_file_s3_url.startswith('http://') or pdf_file_s3_url.startswith('https://')):
                raise ValidationError('S3 URL must start with http:// or https://')
            # Check if it's a PDF file
            if not pdf_file_s3_url.lower().endswith('.pdf'):
                raise ValidationError('S3 URL must point to a PDF file (.pdf extension)')
        return pdf_file_s3_url


@admin.register(Ebook)
class EbookAdmin(admin.ModelAdmin):
    form = EbookAdminForm
    list_display = ("id", "title_display", "priority", "publish_status", "object_status", "cover_preview", "file_source_display", "created", "modified")
    list_filter = ("publish_status", "object_status", "created", "modified")
    search_fields = ("title", "description")
    ordering = ("priority", "title")
    actions = ['hard_delete_selected']
    change_form_template = 'admin/core/ebook/change_form.html'
    
    def get_form(self, request, obj=None, **kwargs):
        """Override to handle form fields that aren't in the model"""
        form = super().get_form(request, obj, **kwargs)
        # Exclude clear checkboxes from model field validation
        # They're form-only fields added in form.__init__
        if hasattr(form, 'base_fields'):
            # These fields are added dynamically in form.__init__, so they won't be validated against model
            pass
        return form
    
    def get_urls(self):
        """Add custom URLs for file deletion"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/delete-file/', self.admin_site.admin_view(self.delete_file_view), name='core_ebook_delete_file'),
        ]
        return custom_urls + urls
    
    def delete_file_view(self, request, object_id):
        """Handle file deletion via AJAX"""
        from django.http import JsonResponse
        from core.s3_utils import get_s3_upload_service
        from core.models import S3FileUpload
        from urllib.parse import urlparse
        
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
        try:
            ebook = Ebook.objects.get(pk=object_id)
            file_type = request.POST.get('file_type')  # 'cover' or 'pdf'
            file_url = request.POST.get('file_url')
            
            if not file_type or not file_url:
                return JsonResponse({'success': False, 'error': 'Missing file type or URL'})
            
            s3_service = get_s3_upload_service()
            
            # Extract S3 key from URL
            parsed_url = urlparse(file_url)
            s3_key = parsed_url.path.lstrip('/')
            
            if not s3_key:
                return JsonResponse({'success': False, 'error': 'Invalid file URL'})
            
            # Try to delete via S3FileUpload record first
            s3_file = S3FileUpload.objects.filter(s3_url=file_url).first()
            if s3_file:
                result = s3_service.delete_file(s3_file.s3_key)
            else:
                # Fallback: try to delete using extracted key
                result = s3_service.delete_file(s3_key)
            
            if result.get('success'):
                # Clear the S3 URL in the ebook model
                if file_type == 'cover':
                    ebook.cover_image_s3_url = None
                    ebook.save(update_fields=['cover_image_s3_url'])
                elif file_type == 'pdf':
                    ebook.pdf_file_s3_url = None
                    ebook.save(update_fields=['pdf_file_s3_url'])
                
                return JsonResponse({
                    'success': True,
                    'message': 'File deleted successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Failed to delete file from S3')
                })
        except Ebook.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Ebook not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    def get_queryset(self, request):
        """Show all ebooks including soft-deleted ones"""
        qs = self.model.objects.complete()  # Use complete() to get all objects including deleted
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
    
    def title_display(self, obj):
        """Display title with visual indicator for deleted items"""
        from core import choices
        if obj.object_status == choices.ObjectStatus.DELETED:
            return format_html(
                '<span style="text-decoration: line-through; color: #999;">{}</span> <span style="color: #dc3545; font-size: 0.9em;">[DELETED]</span>',
                obj.title
            )
        return obj.title
    title_display.short_description = "Title"
    title_display.admin_order_field = "title"
    def get_fieldsets(self, request, obj=None):
        """Different fieldsets for add vs change"""
        if obj is None:  # Adding new
            return (
                ('Basic Information', {
                    'fields': ('title', 'slug', 'description', 'priority', 'publish_status', 'object_status')
                }),
                ('Cover Image', {
                    'fields': ('cover_image', 'cover_image_s3_url', 'cover_preview'),
                    'description': 'Upload a cover image file. It will be automatically uploaded to S3 in ebook/cover/ folder. S3 URL field is auto-populated.'
                }),
                ('PDF File', {
                    'fields': ('pdf_file', 'pdf_file_s3_url'),
                    'description': 'Upload a PDF file. It will be automatically uploaded to S3 in ebook/media/ folder. S3 URL field is auto-populated.'
                }),
                ('Timestamps', {
                    'fields': ('created', 'modified'),
                    'classes': ('collapse',)
                }),
            )
        else:  # Editing existing
            return (
                ('Basic Information', {
                    'fields': ('title', 'slug', 'description', 'priority', 'publish_status', 'object_status')
                }),
                ('Cover Image', {
                    'fields': ('cover_image', 'cover_image_s3_url', 'cover_preview'),
                    'description': 'Upload a new cover image to replace existing, or click "Delete" button next to the file URL to remove. Files are uploaded to S3 in ebook/cover/ folder.'
                }),
                ('PDF File', {
                    'fields': ('pdf_file', 'pdf_file_s3_url'),
                    'description': 'Upload a new PDF file to replace existing, or click "Delete" button next to the file URL to remove. Files are uploaded to S3 in ebook/media/ folder.'
                }),
                ('Timestamps', {
                    'fields': ('created', 'modified'),
                    'classes': ('collapse',)
                }),
            )
    
    readonly_fields = ("created", "modified", "cover_preview", "cover_image_s3_url", "pdf_file_s3_url")
    list_editable = ("priority", "publish_status")
    
    def save_model(self, request, obj, form, change):
        """Handle file uploads to S3 when saving"""
        from core.s3_utils import get_s3_upload_service
        from core.models import S3FileUpload
        from django.conf import settings
        from django.contrib import messages
        from django.core.files.uploadedfile import UploadedFile
        from urllib.parse import urlparse
        
        s3_service = get_s3_upload_service()
        s3_ebook_folder = getattr(settings, 'S3_EBOOK_FOLDER', 'ebook')
        
        # Get clear flags
        clear_cover = form.cleaned_data.get('clear_cover_image', False)
        clear_pdf = form.cleaned_data.get('clear_pdf_file', False)
        
        # Handle cover image removal or replacement
        if change and obj.pk:
            # If clearing or replacing, delete old file from S3 first
            old_cover_url = obj.cover_image_s3_url
            if (clear_cover or form.cleaned_data.get('cover_image')) and old_cover_url:
                # Delete old cover image from S3
                parsed_url = urlparse(old_cover_url)
                s3_key = parsed_url.path.lstrip('/')
                if s3_key:
                    s3_file = S3FileUpload.objects.filter(s3_url=old_cover_url).first()
                    if s3_file:
                        delete_result = s3_service.delete_file(s3_file.s3_key)
                        if not delete_result.get('success'):
                            messages.error(request, f"Failed to delete old cover image from S3: {delete_result.get('error', 'Unknown error')}")
                            return  # Don't save if old file deletion failed
                    else:
                        delete_result = s3_service.delete_file(s3_key)
                        if not delete_result.get('success'):
                            messages.warning(request, f"Warning: Could not delete old cover image from S3: {delete_result.get('error', 'Unknown error')}")
                
                # Clear the S3 URL if removing
                if clear_cover:
                    obj.cover_image_s3_url = None
        
        # Handle cover image upload (new or replacement)
        cover_image = form.cleaned_data.get('cover_image')
        if cover_image and isinstance(cover_image, UploadedFile) and cover_image.name:
            # Upload cover image to S3
            folder_path = f'{s3_ebook_folder}/cover'
            result = s3_service.upload_file(
                file_obj=cover_image,
                folder_path=folder_path,
                description=f'Cover image for ebook: {obj.title}',
                uploaded_by=request.user.username if request.user.is_authenticated else ''
            )
            
            if result['success']:
                # Set S3 URL
                obj.cover_image_s3_url = result['s3_url']
                # Clear the file field to prevent local save
                form.cleaned_data['cover_image'] = None
                obj.cover_image = None
            else:
                messages.error(request, f"Failed to upload cover image to S3: {result.get('error', 'Unknown error')}")
                return  # Don't save if S3 upload failed
        
        # Handle PDF file removal or replacement
        if change and obj.pk:
            # If clearing or replacing, delete old file from S3 first
            old_pdf_url = obj.pdf_file_s3_url
            if (clear_pdf or form.cleaned_data.get('pdf_file')) and old_pdf_url:
                # Delete old PDF file from S3
                parsed_url = urlparse(old_pdf_url)
                s3_key = parsed_url.path.lstrip('/')
                if s3_key:
                    s3_file = S3FileUpload.objects.filter(s3_url=old_pdf_url).first()
                    if s3_file:
                        delete_result = s3_service.delete_file(s3_file.s3_key)
                        if not delete_result.get('success'):
                            messages.error(request, f"Failed to delete old PDF file from S3: {delete_result.get('error', 'Unknown error')}")
                            return  # Don't save if old file deletion failed
                    else:
                        delete_result = s3_service.delete_file(s3_key)
                        if not delete_result.get('success'):
                            messages.warning(request, f"Warning: Could not delete old PDF file from S3: {delete_result.get('error', 'Unknown error')}")
                
                # Clear the S3 URL if removing
                if clear_pdf:
                    obj.pdf_file_s3_url = None
        
        # Handle PDF file upload (new or replacement)
        pdf_file = form.cleaned_data.get('pdf_file')
        if pdf_file and isinstance(pdf_file, UploadedFile) and pdf_file.name:
            # Upload PDF to S3 in ebook/media folder
            folder_path = f'{s3_ebook_folder}/media'
            result = s3_service.upload_file(
                file_obj=pdf_file,
                folder_path=folder_path,
                description=f'PDF file for ebook: {obj.title}',
                uploaded_by=request.user.username if request.user.is_authenticated else ''
            )
            
            if result['success']:
                # Set S3 URL
                obj.pdf_file_s3_url = result['s3_url']
                # Clear the file field to prevent local save
                form.cleaned_data['pdf_file'] = None
                obj.pdf_file = None
            else:
                messages.error(request, f"Failed to upload PDF file to S3: {result.get('error', 'Unknown error')}")
                return  # Don't save if S3 upload failed
        
        # Save the object (files won't be saved locally since we cleared them)
        super().save_model(request, obj, form, change)

    def cover_preview(self, obj):
        """Display cover image preview in admin"""
        cover_url = obj.get_cover_url()
        if cover_url:
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 200px; object-fit: contain; border: 1px solid #ddd; border-radius: 4px;" />',
                cover_url
            )
        return "No cover image"
    cover_preview.short_description = "Cover Preview"
    
    def file_source_display(self, obj):
        """Display PDF file source (uploaded or S3)"""
        if obj.pdf_file_s3_url:
            return format_html('<span style="color: #28a745;">S3 URL</span>')
        elif obj.pdf_file and obj.pdf_file.name:
            try:
                size = obj.pdf_file.size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.2f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.2f} MB"
                return format_html('<span style="color: #007bff;">Uploaded ({})</span>', size_str)
            except (OSError, ValueError):
                return format_html('<span style="color: #007bff;">Uploaded</span>')
        return "No file"
    file_source_display.short_description = "PDF Source"
    
    def hard_delete_selected(self, request, queryset):
        """Hard delete selected ebooks (permanently remove from database)"""
        from django.contrib import messages
        from core.s3_utils import get_s3_upload_service
        from core.models import S3FileUpload
        from django.conf import settings
        from urllib.parse import urlparse
        from django.db import connection
        
        s3_service = get_s3_upload_service()
        
        # Get all ebooks to delete (convert queryset to list to avoid issues)
        ebooks_to_delete = list(queryset)
        ebooks_successfully_deleted = []
        errors = []
        
        # First, delete all S3 files and track which ebooks can be safely deleted
        for ebook in ebooks_to_delete:
            s3_deletion_errors = []
            
            # Delete PDF file from S3 if it exists
            if ebook.pdf_file_s3_url:
                # Extract S3 key from URL
                parsed_url = urlparse(ebook.pdf_file_s3_url)
                s3_key = parsed_url.path.lstrip('/')
                if s3_key:
                    # Try to delete via S3FileUpload record first
                    s3_file = S3FileUpload.objects.filter(s3_url=ebook.pdf_file_s3_url).first()
                    if s3_file:
                        result = s3_service.delete_file(s3_file.s3_key)
                    else:
                        # Fallback: try to delete using extracted key
                        result = s3_service.delete_file(s3_key)
                    
                    if not result.get('success'):
                        error_msg = result.get('error', 'Unknown error')
                        s3_deletion_errors.append(f"PDF file deletion failed: {error_msg}")
            
            # Delete cover image from S3 if it exists
            if ebook.cover_image_s3_url:
                # Extract S3 key from URL
                parsed_url = urlparse(ebook.cover_image_s3_url)
                s3_key = parsed_url.path.lstrip('/')
                if s3_key:
                    # Try to delete via S3FileUpload record first
                    s3_file = S3FileUpload.objects.filter(s3_url=ebook.cover_image_s3_url).first()
                    if s3_file:
                        result = s3_service.delete_file(s3_file.s3_key)
                    else:
                        # Fallback: try to delete using extracted key
                        result = s3_service.delete_file(s3_key)
                    
                    if not result.get('success'):
                        error_msg = result.get('error', 'Unknown error')
                        s3_deletion_errors.append(f"Cover image deletion failed: {error_msg}")
            
            # Only add to successful list if no S3 deletion errors
            if s3_deletion_errors:
                errors.append({
                    'ebook': ebook,
                    'errors': s3_deletion_errors
                })
            else:
                ebooks_successfully_deleted.append(ebook)
        
        # Only delete database records for ebooks where S3 deletion was successful
        if ebooks_successfully_deleted:
            ebook_ids = [ebook.id for ebook in ebooks_successfully_deleted]
            
            # Use raw SQL to permanently delete records from the database table
            if ebook_ids:
                with connection.cursor() as cursor:
                    # Use parameterized query to prevent SQL injection
                    placeholders = ','.join(['%s'] * len(ebook_ids))
                    cursor.execute(
                        f"DELETE FROM core_ebook WHERE id IN ({placeholders})",
                        ebook_ids
                    )
            
            self.message_user(
                request,
                f'Successfully hard deleted {len(ebooks_successfully_deleted)} ebook(s). Records have been permanently removed from the database table and files from S3.',
                messages.SUCCESS
            )
        
        # Show error messages for ebooks where S3 deletion failed
        if errors:
            for error_info in errors:
                ebook = error_info['ebook']
                error_list = error_info['errors']
                error_message = f"Failed to delete ebook '{ebook.title}' (ID: {ebook.id}): " + "; ".join(error_list)
                self.message_user(
                    request,
                    error_message,
                    messages.ERROR
                )
            self.message_user(
                request,
                f'{len(errors)} ebook(s) were NOT deleted from database due to S3 file deletion errors. Please fix the S3 issues and try again.',
                messages.ERROR
            )
        
        # If no ebooks were successfully deleted, show a general error
        if not ebooks_successfully_deleted and errors:
            self.message_user(
                request,
                'No ebooks were deleted. All S3 file deletions failed. Database records remain unchanged.',
                messages.ERROR
            )
    hard_delete_selected.short_description = "Hard delete selected ebooks (permanently remove)"
    
    def get_actions(self, request):
        """Get available actions"""
        actions = super().get_actions(request)
        # Make sure hard_delete_selected is included
        if 'hard_delete_selected' not in actions:
            actions['hard_delete_selected'] = (
                self.hard_delete_selected,
                'hard_delete_selected',
                self.hard_delete_selected.short_description
            )
        return actions


class S3FileUploadAdminForm(forms.ModelForm):
    """Form for S3 file upload with file upload field"""
    upload_file = forms.FileField(
        required=False,
        help_text="Upload a file to S3 bucket. This will create a new S3FileUpload record."
    )
    folder_path = forms.CharField(
        required=False,
        max_length=500,
        help_text="Optional folder path in S3 (e.g., 'ebook/pdf', 'images/cover'). Leave empty for root."
    )
    
    class Meta:
        model = S3FileUpload
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # When editing existing records, hide upload_file and make fields readonly
        if self.instance and self.instance.pk:
            if 'upload_file' in self.fields:
                del self.fields['upload_file']
            if 'file_name' in self.fields:
                self.fields['file_name'].widget.attrs['readonly'] = True
            if 's3_key' in self.fields:
                self.fields['s3_key'].widget.attrs['readonly'] = True
            if 's3_url' in self.fields:
                self.fields['s3_url'].widget.attrs['readonly'] = True
            if 'file_type' in self.fields:
                self.fields['file_type'].widget.attrs['readonly'] = True
            if 'file_size' in self.fields:
                self.fields['file_size'].widget.attrs['readonly'] = True
            if 'folder_path' in self.fields:
                self.fields['folder_path'].widget.attrs['readonly'] = True
        else:
            # When adding new, make S3 details fields not required
            if 's3_key' in self.fields:
                self.fields['s3_key'].required = False
            if 's3_url' in self.fields:
                self.fields['s3_url'].required = False
            # Make upload_file required when adding
            if 'upload_file' in self.fields:
                self.fields['upload_file'].required = True
    
    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        
        # When adding new record, upload_file is required
        if not self.instance.pk and not cleaned_data.get('upload_file'):
            raise ValidationError('Please upload a file to create a new S3 upload record.')
        
        return cleaned_data


@admin.register(S3FileUpload)
class S3FileUploadAdmin(admin.ModelAdmin):
    form = S3FileUploadAdminForm
    list_display = ('id', 'file_name', 'folder_path_display', 'file_size_display', 'file_type', 's3_url_link', 'uploaded_by', 'created')
    list_filter = ('file_type', 'folder_path', 'created', 'modified')
    search_fields = ('file_name', 's3_key', 's3_url', 'description', 'uploaded_by')
    readonly_fields = ('created', 'modified', 's3_url', 's3_key', 'file_type', 'file_size', 's3_url_preview')
    ordering = ('-created',)
    # date_hierarchy = 'created'  # Disabled: Requires MySQL timezone tables to be loaded
    list_display_links = ('id', 'file_name')
    
    def get_fieldsets(self, request, obj=None):
        """Different fieldsets for add vs change"""
        if obj is None:  # Adding new
            return (
                ('Upload File', {
                    'fields': ('upload_file', 'folder_path', 'description', 'uploaded_by'),
                    'description': 'Upload a file to S3 bucket. The file will be automatically uploaded when you save.'
                }),
            )
        else:  # Editing existing
            return (
                ('File Information', {
                    'fields': ('file_name', 'folder_path', 'description', 'uploaded_by')
                }),
                ('S3 Details', {
                    'fields': ('s3_key', 's3_url', 's3_url_preview', 'file_type', 'file_size'),
                    'classes': ('collapse',)
                }),
                ('Timestamps', {
                    'fields': ('created', 'modified'),
                    'classes': ('collapse',)
                }),
            )
    
    def folder_path_display(self, obj):
        """Display folder path or 'Root' if empty"""
        return obj.folder_path if obj.folder_path else 'Root'
    folder_path_display.short_description = 'Folder'
    
    def file_size_display(self, obj):
        """Display human-readable file size"""
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'
    
    def s3_url_link(self, obj):
        """Display S3 URL as clickable link"""
        if obj.s3_url:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.s3_url, 'View File')
        return '-'
    s3_url_link.short_description = 'S3 URL'
    
    def s3_url_preview(self, obj):
        """Preview S3 URL in detail view"""
        if obj.s3_url:
            # Check if it's an image
            if obj.file_type and obj.file_type.startswith('image/'):
                return format_html(
                    '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;" /></a>',
                    obj.s3_url, obj.s3_url
                )
            else:
                return format_html('<a href="{}" target="_blank">{}</a>', obj.s3_url, obj.s3_url)
        return 'No URL'
    s3_url_preview.short_description = 'Preview'
    
    def save_model(self, request, obj, form, change):
        """Handle file upload when saving"""
        upload_file = form.cleaned_data.get('upload_file')
        folder_path = form.cleaned_data.get('folder_path', '').strip()
        
        if upload_file and not change:  # Only upload on create, not edit
            from core.s3_utils import get_s3_upload_service
            s3_service = get_s3_upload_service()
            
            result = s3_service.upload_file(
                file_obj=upload_file,
                folder_path=folder_path,
                description=obj.description or '',
                uploaded_by=obj.uploaded_by or (request.user.username if request.user.is_authenticated else '')
            )
            
            if result['success']:
                # Update object with S3 details
                obj.s3_url = result['s3_url']
                obj.s3_key = result['s3_key']
                obj.file_name = upload_file.name
                obj.file_type = result.get('content_type', '')
                obj.file_size = result.get('file_size', 0)
                obj.folder_path = folder_path if folder_path else None
                super().save_model(request, obj, form, change)
            else:
                from django.contrib import messages
                messages.error(request, f"Failed to upload file to S3: {result.get('error', 'Unknown error')}")
        else:
            super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        """Check if S3 upload is enabled before allowing add"""
        from core.s3_utils import get_s3_upload_service
        s3_service = get_s3_upload_service()
        if not s3_service.is_enabled():
            return False
        return super().has_add_permission(request)
    
    def changelist_view(self, request, extra_context=None):
        """Add S3 upload status to changelist context"""
        extra_context = extra_context or {}
        from core.s3_utils import get_s3_upload_service
        from core.models import Configuration
        
        s3_service = get_s3_upload_service()
        is_enabled = s3_service.is_enabled()
        
        # Get configuration key for S3 upload
        try:
            config = Configuration.objects.filter(key='S3_UPLOAD_ENABLED').first()
            if not config:
                # Create default configuration
                config = Configuration.objects.create(
                    key='S3_UPLOAD_ENABLED',
                    value='false',
                    editable=True
                )
        except:
            config = None
        
        extra_context['s3_upload_enabled'] = is_enabled
        extra_context['s3_config'] = config
        
        return super().changelist_view(request, extra_context)


# ----- Four Pillars Assessments (admin-editable) -----


def strip_html_from_text(text):
    """Return plain text with HTML tags removed."""
    if not text or not isinstance(text, str):
        return text or ""
    return strip_tags(text).strip()


class FourPillarsAssessmentQuestionOptionForm(forms.ModelForm):
    """Strip HTML from option text on save."""
    class Meta:
        model = FourPillarsAssessmentQuestionOption
        fields = "__all__"

    def clean_text(self):
        value = self.cleaned_data.get("text") or ""
        return strip_html_from_text(value)


class FourPillarsAssessmentQuestionForm(forms.ModelForm):
    """Strip HTML from question text on save."""
    class Meta:
        model = FourPillarsAssessmentQuestion
        fields = "__all__"

    def clean_text(self):
        value = self.cleaned_data.get("text") or ""
        return strip_html_from_text(value)


class FourPillarsAssessmentQuestionOptionInline(admin.TabularInline):
    model = FourPillarsAssessmentQuestionOption
    form = FourPillarsAssessmentQuestionOptionForm
    extra = 0
    fields = ("option_key", "text")
    ordering = ("option_key",)
    verbose_name = "Option (A, B, C or D)"
    verbose_name_plural = "Options (A, B, C, D) – edit option text below"

    def get_extra(self, request, obj=None, **kwargs):
        """Show 4 empty option rows when adding a new question."""
        return 4 if obj is None else 0


class FourPillarsAssessmentQuestionInline(admin.TabularInline):
    model = FourPillarsAssessmentQuestion
    extra = 0
    fields = ("order", "title", "text")
    ordering = ("order",)
    show_change_link = True


class FourPillarsAssessmentProfileInline(admin.TabularInline):
    model = FourPillarsAssessmentProfile
    extra = 0
    fields = ("option_key", "name", "summary", "scoring_heading", "scoring_bullets")
    ordering = ("option_key",)
    show_change_link = True


@admin.register(FourPillarsAssessmentProfile)
class FourPillarsAssessmentProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "assessment", "option_key", "name", "summary_preview")
    list_filter = ("assessment", "option_key")
    search_fields = ("name", "summary", "scoring_heading")
    ordering = ("assessment", "option_key")
    raw_id_fields = ("assessment",)
    fieldsets = (
        (None, {"fields": ("assessment", "option_key", "name", "summary")}),
        ("Scoring Guide card", {"fields": ("scoring_heading", "scoring_bullets")}),
        ("Timestamps", {"fields": ("created", "modified"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created", "modified")

    def summary_preview(self, obj):
        return (obj.summary[:50] + "…") if obj.summary and len(obj.summary) > 50 else (obj.summary or "")
    summary_preview.short_description = "Summary"


@admin.register(FourPillarsAssessmentQuestion)
class FourPillarsAssessmentQuestionAdmin(admin.ModelAdmin):
    form = FourPillarsAssessmentQuestionForm
    list_display = ("id", "assessment", "order", "title", "text_preview")
    list_filter = ("assessment",)
    search_fields = ("title", "text")
    ordering = ("assessment", "order")
    inlines = (FourPillarsAssessmentQuestionOptionInline,)
    raw_id_fields = ("assessment",)
    fieldsets = (
        (None, {"fields": ("assessment", "order", "title", "text")}),
    )

    def text_preview(self, obj):
        raw = obj.text or ""
        plain = strip_html_from_text(raw)
        return (plain[:60] + "…") if len(plain) > 60 else plain
    text_preview.short_description = "Question text"


@admin.register(FourPillarsAssessment)
class FourPillarsAssessmentAdmin(admin.ModelAdmin):
    list_display = ("id", "slug", "title", "is_active", "questions_count", "profiles_count", "guide_link", "modified")
    list_filter = ("is_active",)
    search_fields = ("slug", "title")
    ordering = ("slug",)
    prepopulated_fields = {"slug": ("title",)}
    inlines = (FourPillarsAssessmentProfileInline,)
    fieldsets = (
        (None, {"fields": ("slug", "title", "subtitle", "is_active")}),
        ("Scoring Guide", {"fields": ("scoring_intro", "mixed_results")}),
        ("Timestamps", {"fields": ("created", "modified"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created", "modified")

    def questions_count(self, obj):
        if not obj.pk:
            return "—"
        n = obj.questions.count()
        url = reverse("admin:core_fourpillarsassessmentquestion_changelist") + "?assessment__id__exact=" + str(obj.pk)
        return format_html('<a href="{}">{} question{}</a>', url, n, "s" if n != 1 else "")
    questions_count.short_description = "Questions"

    def profiles_count(self, obj):
        if not obj.pk:
            return "—"
        n = obj.profiles.count()
        url = reverse("admin:core_fourpillarsassessmentprofile_changelist") + "?assessment__id__exact=" + str(obj.pk)
        return format_html('<a href="{}">{} profile{}</a>', url, n, "s" if n != 1 else "")
    profiles_count.short_description = "Profiles"

    def guide_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:core_fourpillarsassessmentscoringguide_change", args=[obj.pk])
        return format_html('<a href="{}">Edit guide</a>', url)
    guide_link.short_description = "Scoring Guide"


@admin.register(FourPillarsAssessmentScoringGuide)
class FourPillarsAssessmentScoringGuideAdmin(admin.ModelAdmin):
    """Edit only the Scoring Guide section (intro + mixed results) separately from the full assessment."""
    list_display = ("id", "slug", "title")
    list_display_links = ("id", "slug", "title")
    search_fields = ("slug", "title")
    ordering = ("slug",)
    readonly_fields = ("slug", "title")
    fieldsets = (
        (None, {"fields": ("slug", "title"), "description": "Which assessment this Scoring Guide belongs to."}),
        ("Scoring Guide section", {
            "fields": ("scoring_intro", "mixed_results"),
            "description": "Intro text and mixed-results note shown in the Scoring Guide block on the assessment page.",
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request)


# --- Static Page CMS & Page SEO (SEO dashboard uses same models) ---


class StaticPageSectionInline(admin.TabularInline):
    model = StaticPageSection
    extra = 0
    ordering = ("order",)


@admin.register(StaticPage)
class StaticPageAdmin(admin.ModelAdmin):
    list_display = ("url_key", "title", "is_active", "modified")
    list_filter = ("is_active",)
    search_fields = ("url_key", "title")
    ordering = ("url_key",)
    inlines = (StaticPageSectionInline,)
    fieldsets = (
        (None, {"fields": ("url_key", "title", "is_active")}),
        ("Content", {"fields": ("content_html", "content_json", "content_css", "content_js")}),
    )

    def has_module_permission(self, request):
        return request.user.is_staff


@admin.register(PageSEO)
class PageSEOAdmin(admin.ModelAdmin):
    list_display = ("url_key", "title", "modified")
    search_fields = ("url_key", "title", "description", "keywords")
    ordering = ("url_key",)
    fieldsets = (
        (None, {"fields": ("url_key",)}),
        ("Meta", {"fields": ("title", "description", "keywords")}),
        ("Open Graph", {"fields": ("og_image",)}),
    )

    def has_module_permission(self, request):
        return request.user.is_staff


@admin.register(URLIndexRule)
class URLIndexRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "path_pattern",
        "match_type",
        "apply_in_robots",
        "apply_x_robots_tag",
        "is_active",
        "modified",
    )
    list_filter = ("match_type", "apply_in_robots", "apply_x_robots_tag", "is_active")
    search_fields = ("name", "path_pattern", "notes")
    ordering = ("path_pattern",)
    fieldsets = (
        (None, {"fields": ("name", "path_pattern", "match_type", "is_active")}),
        ("Apply rule in", {"fields": ("apply_in_robots", "apply_x_robots_tag")}),
        ("Notes", {"fields": ("notes",)}),
    )

    def has_module_permission(self, request):
        return request.user.is_staff


@admin.register(ScannedURL)
class ScannedURLAdmin(admin.ModelAdmin):
    list_display = ("url_path", "created_at", "last_seen_at")
    search_fields = ("url_path",)
    ordering = ("url_path",)
    readonly_fields = ("created_at", "last_seen_at")

    def has_module_permission(self, request):
        return request.user.is_staff


@admin.register(GeneratedPage)
class GeneratedPageAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "is_active", "modified")
    list_filter = ("is_active",)
    search_fields = ("slug", "title")
    ordering = ("-created",)


