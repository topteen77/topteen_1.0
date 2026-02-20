from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html, strip_tags
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.http import JsonResponse
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


class ConfigurationAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','key')
    fields = ['created','modified','key','value']
    # date_hierarchy = 'created'  # Disabled: Requires MySQL timezone tables to be loaded
    list_display = ['id', 'key','value','created','modified']
    sortable_by=['id', 'key','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['key','value']
    list_display_links=['id','key']

    def get_queryset(self, request):
        qs = super(ConfigurationAdmin, self).get_queryset(request)
        return qs.filter(editable=True)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('psychometric-settings/', self.admin_site.admin_view(self.psychometric_settings_view), name='core_configuration_psychometric_settings'),
            path('student-id-settings/', self.admin_site.admin_view(self.student_id_settings_view), name='core_configuration_student_id_settings'),
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
    """Filter vocational courses by accordion validation (uses last validation result from session)."""
    title = 'Accordion'
    parameter_name = 'accordion'

    def lookups(self, request, model_admin):
        return (
            ('', 'All'),
            ('1', 'With accordion errors'),
            ('0', 'No errors'),
        )

    def queryset(self, request, queryset):
        error_pks = request.session.get('vocational_accordion_errors') or []
        if self.value() == '1':
            return queryset.filter(pk__in=error_pks) if error_pks else queryset.none()
        if self.value() == '0':
            return queryset.exclude(pk__in=error_pks)
        return queryset


def _vocational_accordion_blank_sections(course):
    """Return list of section names that are blank (same logic as frontend accordion). Includes Overview from content_json."""
    import re
    errors = []
    data = getattr(course, 'content_json', None) or {}
    # Check overview (hero section) for blank content
    overview = data.get('overview')
    if overview is None or _html_is_effectively_blank(str(overview).strip()):
        errors.append('Overview: blank')
    sections = data.get('sections') or {}
    for heading in VOCATIONAL_ACCORDION_HEADINGS:
        key = re.sub(r'[^a-z0-9]+', '_', heading.lower()).strip('_')
        section = sections.get(key) if isinstance(sections, dict) else None
        if section is None:
            errors.append(f'{heading}: blank')
            continue
        if isinstance(section, str):
            html = section
        else:
            html = (section.get('html') or section.get('content') or section.get('body') or '')
        if _html_is_effectively_blank(html or ''):
            errors.append(f'{heading}: blank')
    return errors


@admin.register(VocationalCourse)
class VocationalCourseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "accordion_validation", "category_name_safe", "priority", "object_status", "preview_link", "image_safe")
    list_filter = (AccordionErrorsFilter, "object_status", "category")
    search_fields = ("name", "category__name")
    ordering = ("category__name", "priority", "name")
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'name', 'slug', 'image', 'priority', 'object_status')
        }),
        ('Content', {
            'fields': ('content_html', 'content_json'),
            'description': 'Edit content_html to generate accordion structure. The content_json field is auto-generated and saved on form submit.'
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ("created", "modified")
    change_form_template = "admin/core/vocationalcourse/change_form.html"
    change_list_template = "admin/core/vocationalcourse/change_list.html"

    class Media:
        css = {
            'all': ('admin/css/hide_content_json.css',)
        }
    
    def save_model(self, request, obj, form, change):
        """Override save_model to handle content_json from POST data"""
        import json
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get content_json from POST data
        # Since we removed it from readonly_fields, it should be in POST
        content_json_str = request.POST.get('content_json', '')
        
        # Debug logging
        if not content_json_str:
            logger.warning(f'No content_json in POST for VocationalCourse {obj.id or "new"}. POST keys: {list(request.POST.keys())[:30]}')
        else:
            logger.info(f'Found content_json in POST. Length: {len(content_json_str)}')
        
        if content_json_str:
            try:
                # Parse and validate JSON
                content_json_data = json.loads(content_json_str)
                obj.content_json = content_json_data
                logger.info(f'Successfully saved content_json for VocationalCourse {obj.id or "new"}. Sections: {len(content_json_data.get("sections", {}))}')
            except (json.JSONDecodeError, ValueError) as e:
                # If JSON is invalid, log error but don't fail the save
                logger.warning(f'Invalid JSON in content_json field: {e}. Content: {content_json_str[:200]}')
                # Keep existing value if updating, otherwise set to None
                if not change:
                    obj.content_json = None
        
        # Call parent save
        super().save_model(request, obj, form, change)
    
    def category_name_safe(self, obj):
        """Display category name without raising if category is missing."""
        try:
            return obj.category.name if obj.category_id and getattr(obj, 'category', None) else '-'
        except Exception:
            return '-'
    category_name_safe.short_description = 'Category'
    category_name_safe.admin_order_field = 'category__name'

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
        """Placeholder for validation result; filled by JS after 'Validate accordion' is run."""
        if not obj or not getattr(obj, 'id', None):
            return '—'
        return format_html(
            '<span class="accordion-validation" data-pk="{}" data-name="{}" title="">—</span>',
            obj.pk,
            obj.name[:50] if obj.name else '',
        )
    accordion_validation.short_description = 'Accordion'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'validate_accordion/',
                self.admin_site.admin_view(self.validate_accordion_view),
                name='core_vocationalcourse_validate_accordion',
            ),
        ]
        return custom + urls

    def validate_accordion_view(self, request):
        """Return JSON mapping course pk -> list of blank section error strings; store error PKs in session for sidebar filter."""
        qs = self.get_queryset(request)
        results = {}
        error_pks = []
        for course in qs:
            errors = _vocational_accordion_blank_sections(course)
            results[str(course.pk)] = errors
            if errors:
                error_pks.append(course.pk)
        request.session['vocational_accordion_errors'] = error_pks
        return JsonResponse({'results': results})


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


