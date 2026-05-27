from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django import forms
from django.db import models
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.urls import path, reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Count, Q
from core import choices
from .models import (
    Career, CareerFAQ, CareerPath, CareerMedia, Skill, ProspectiveEmploymentArea,
    ProspectiveRecruiter, Profession, CareerPathStep, CareerCluster, RIASECCareer,
    CareerRating, CareerRelatedCareers,
)
from .related_careers_import import import_related_careers_from_csv
from nested_inline.admin import NestedStackedInline, NestedModelAdmin
from modeltranslation.admin import TranslationAdmin,TranslationStackedInline
from .docx_utils import convert_docx_to_html, extract_career_data_from_html

# Register your models here.

class MindmapValidationFilter(SimpleListFilter):
    """Custom filter for mindmap validation status"""
    title = 'Mindmap Validation'
    parameter_name = 'mindmap_validation'
    
    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ('valid', 'Valid'),
            ('errors', 'Has Errors'),
        )
    
    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        if self.value() == 'valid':
            # Filter careers with valid mindmaps
            valid_ids = []
            for career in queryset:
                is_valid, _ = career.validate_mindmap()
                if is_valid:
                    valid_ids.append(career.id)
            return queryset.filter(id__in=valid_ids)
        elif self.value() == 'errors':
            # Filter careers with mindmap errors
            error_ids = []
            for career in queryset:
                is_valid, _ = career.validate_mindmap()
                if not is_valid:
                    error_ids.append(career.id)
            return queryset.filter(id__in=error_ids)
        return queryset


class CareerClusterEmptyFilter(SimpleListFilter):
    """Filter for careers not linked with any cluster (no active cluster links)"""
    title = 'Career Cluster'
    parameter_name = 'career_cluster_empty'

    def lookups(self, request, model_admin):
        return (
            ('empty', 'Blank or null (not linked)'),
            ('has', 'Has cluster(s)'),
        )

    def queryset(self, request, queryset):
        # Count only ACTIVE clusters (CareerCluster uses SoftDeletionManager)
        active_cluster_filter = Q(career_cluster__object_status=choices.ObjectStatus.ACTIVE)
        if self.value() == 'empty':
            # Careers with no active cluster links (career_cluster.count() == 0)
            return queryset.annotate(
                cc_count=Count('career_cluster', filter=active_cluster_filter)
            ).filter(cc_count=0)
        elif self.value() == 'has':
            return queryset.annotate(
                cc_count=Count('career_cluster', filter=active_cluster_filter)
            ).filter(cc_count__gt=0)
        return queryset


class ImageEmptyFilter(SimpleListFilter):
    """Filter for careers with no image (null or blank)"""
    title = 'Image'
    parameter_name = 'image_empty'

    def lookups(self, request, model_admin):
        return (
            ('empty', 'Blank or null (no image)'),
            ('has', 'Has image'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'empty':
            return queryset.filter(Q(image='') | Q(image__isnull=True))
        elif self.value() == 'has':
            return queryset.exclude(Q(image='') | Q(image__isnull=True))
        return queryset


class ImageDuplicateFilter(SimpleListFilter):
    """Filter for careers with duplicate image names (same image used by multiple careers)"""
    title = 'Image duplicate'
    parameter_name = 'image_duplicate'

    def lookups(self, request, model_admin):
        return (
            ('duplicate', 'Same image name (duplicate)'),
            ('unique', 'Unique image name'),
        )

    def queryset(self, request, queryset):
        dupes = Career.objects.exclude(
            Q(image='') | Q(image__isnull=True)
        ).values('image').annotate(c=Count('id')).filter(c__gt=1).values_list('image', flat=True)
        if self.value() == 'duplicate':
            return queryset.filter(image__in=dupes)
        elif self.value() == 'unique':
            return queryset.exclude(Q(image='') | Q(image__isnull=True)).exclude(image__in=dupes)
        return queryset


class CareerPathInline(NestedStackedInline,TranslationStackedInline):
    model = CareerPath
    extra = 1
    fields= ['name']
    readonly_fields=['created','modified']

class CareerMediaInline(NestedStackedInline):
    model = CareerMedia
    extra = 1
    fields= ['type','media']
    readonly_fields=['created','modified']


class CareerClusterSelectWidget(forms.SelectMultiple):
    """Custom widget for career cluster selection in list view"""
    
    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs)
        self.choices = choices
    
    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = []
        if not isinstance(value, (list, tuple)):
            value = [value] if value else []
        
        # Get all career clusters
        clusters = CareerCluster.objects.all().order_by('name')
        
        # Create options
        options = []
        for cluster in clusters:
            selected = 'selected' if cluster.id in value else ''
            options.append(f'<option value="{cluster.id}" {selected}>{cluster.name}</option>')
        
        return format_html(
            '<select name="{}" multiple style="width: 200px; height: 30px;">{}</select>',
            name,
            format_html(''.join(options))
        )


class CareerAdminForm(forms.ModelForm):
    """Custom form for Career admin with automatic DOCX processing"""
    
    # Custom field for DOCX upload (not stored in database)
    docx_file = forms.FileField(
        required=False,
        help_text='''
        <div id="docx-processing-status" style="display: none; margin: 10px 0; padding: 15px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <div id="processing-spinner" style="width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #007cba; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 10px;"></div>
                <span id="processing-text" style="font-weight: bold; color: #007cba;">Processing DOCX file...</span>
            </div>
            <div id="processing-progress" style="width: 100%; background-color: #e9ecef; border-radius: 10px; overflow: hidden;">
                <div id="progress-bar" style="height: 6px; background-color: #007cba; width: 0%; transition: width 0.3s ease;"></div>
            </div>
            <div id="processing-message" style="margin-top: 10px; font-size: 14px; color: #6c757d;"></div>
        </div>
        
        <style>
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        </style>
        
        Upload a DOCX file to automatically populate career name and description fields. This will overwrite existing content.
        ''',
        widget=forms.FileInput(attrs={
            'accept': '.docx',
            'id': 'docx_file_input',
            'onchange': 'processDocxFile(this)'
        })
    )
    
    class Meta:
        model = Career
        fields = '__all__'
        exclude = ['description_json', 'summary']
        widgets = {
            'career_cluster': CareerClusterSelectWidget(),
        }
    
    def clean(self):
        cleaned = super().clean()
        # Enforce image when publishing
        publish_status = cleaned.get('publish_status')
        image = cleaned.get('image')
        try:
            from core import choices as core_choices
            published_value = core_choices.PublishStatus.PUBLISHED
        except Exception:
            published_value = 1
        if publish_status == published_value:
            # Require that an actual file is present
            if not image or not getattr(image, 'name', None):
                self.add_error('image', 'Image is required to publish a career.')
        return cleaned
    def clean_docx_file(self):
        """Validate uploaded DOCX file"""
        docx_file = self.cleaned_data.get('docx_file')
        
        if docx_file:
            # Check file extension
            if not docx_file.name.endswith('.docx'):
                raise forms.ValidationError('Only DOCX files are allowed.')
            
            # Check file size (limit to 10MB)
            if docx_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB.')
        
        return docx_file


class CareerAdmin(admin.ModelAdmin):
    form = CareerAdminForm
    list_display = [
        'id', 'name', 'career_clusters_display', 'related_careers_summary',
        'publish_status_display', 'image_url_display', 'preview_link',
        'mindmap_validation', 'skills_count', 'created_date', 'modified_date',
    ]
    list_filter = ['publish_status', 'created', 'modified', 'career_cluster', CareerClusterEmptyFilter, ImageEmptyFilter, ImageDuplicateFilter, MindmapValidationFilter]
    search_fields = ['name', 'summary', 'description']
    list_per_page = 25
    ordering = ['-created']
    # Using custom AJAX dropdown instead of inline edit
    # list_editable = ['publish_status']
    actions = ['make_published', 'make_draft', 'assign_to_cluster']
    
    inlines = [CareerMediaInline]
    readonly_fields = ['created', 'modified', 'preview_url', 'validation_errors']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'image', 'publish_status')
        }),
        ('Career Cluster Assignment', {
            'fields': ('career_cluster',),
            'description': 'Select one or more career clusters to categorize this career. This helps organize careers in the career library.',
        }),
        ('DOCX Upload', {
            'fields': ('docx_file',),
            'description': 'Upload a DOCX file to automatically populate career name and description fields. This will overwrite existing content.',
            'classes': ('collapse',),
        }),
        ('Preview & Validation', {
            'fields': ('preview_url', 'validation_errors'),
            'classes': ('collapse',),
        }),
        ('Optional Details', {
            'fields': (),
            'classes': ('collapse',),
            'description': 'Optional details have been removed. All content should be in the description field.',
        }),
        ('Related Careers', {
            'fields': ('related_careers',),
            'description': 'Manually curated careers for the public Related Careers section. When set, overrides automatic cluster/course matching.',
        }),
        ('Other Relationships', {
            'fields': ('skills', 'prospective_employment_areas', 'prospective_recruiters', 
                      'career_tags', 'courses', 'career_paths'),
            'classes': ('collapse',),
        }),
        ('Media & Links', {
            'fields': ('video_url', 'videos'),
            'classes': ('collapse',),
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description'),
            'classes': ('collapse',),
        }),
    )
    
    filter_horizontal = ('skills', 'prospective_employment_areas', 'prospective_recruiters', 
                        'career_tags', 'courses', 'career_cluster', 'related_careers',
                        'career_paths', 'videos')
    
    def career_clusters_display(self, obj):
        """Display career clusters with editable dropdown"""
        clusters = obj.career_cluster.all()
        cluster_ids = [str(cluster.id) for cluster in clusters]
        
        # Get all career clusters
        all_clusters = CareerCluster.objects.all().order_by('name')
        
        # Create dropdown options
        options = []
        for cluster in all_clusters:
            selected = 'selected' if str(cluster.id) in cluster_ids else ''
            options.append(f'<option value="{cluster.id}" {selected}>{cluster.name}</option>')
        
        # Create the dropdown HTML
        dropdown_html = format_html(
            '<select name="career_cluster_{}" onchange="updateCareerCluster({}, this.value)" style="width: 200px; font-size: 12px;">'
            '<option value="">-- Select Cluster --</option>'
            '{}'
            '</select>',
            obj.id,
            obj.id,
            format_html(''.join(options))
        )
        
        # Show current clusters as text below dropdown
        current_clusters = ', '.join([cluster.name for cluster in clusters]) if clusters else 'None'
        current_text = format_html('<br><small style="color: #666;">Current: {}</small>', current_clusters)
        
        return format_html('{}{}', dropdown_html, current_text)

    def publish_status_display(self, obj):
        """Display publish status with editable dropdown via AJAX"""
        # Build options from choices
        options_html = [
            f'<option value="{value}" {"selected" if obj.publish_status == value else ""}>{label}</option>'
            for value, label in choices.PublishStatus.CHOICES
        ]
        dropdown_html = format_html(
            '<select name="publish_status_{id}" onchange="updatePublishStatus({id}, this.value, this)" style="width: 150px; font-size: 12px;">{options}</select>',
            id=obj.id,
            options=format_html(''.join(options_html))
        )
        return dropdown_html
    publish_status_display.short_description = 'Publish Status'
    
    career_clusters_display.short_description = "Career Clusters"
    career_clusters_display.admin_order_field = 'career_cluster__name'
    
    def preview_link(self, obj):
        if obj.id and obj.is_valid_for_preview():
            try:
                url = reverse("careers:careerdetail", kwargs={"slug": obj.slug, "career_id": obj.id})
            except Exception:
                url = f"/careers/career/{obj.slug}-{obj.id}-detail/"
            return format_html(
                '<a href="{}" target="_blank" style="color: green;">View</a>',
                url,
            )
        elif obj.id:
            errors = obj.get_validation_errors()
            error_text = '; '.join(errors)
            # Show a red label with inline details and full details in tooltip
            return format_html(
                '<span style="color: red; font-weight:600;" title="{title}">Invalid</span><br>'
                '<small style="color:#b94a48;">{inline}</small>',
                title=error_text,
                inline=error_text
            )
        return '-'
    preview_link.short_description = 'Preview'
    
    def validation_errors(self, obj):
        """Show validation errors in detail"""
        errors = obj.get_validation_errors()
        if not errors:
            return format_html('<span style="color: green;">No validation errors</span>')
        
        error_list = format_html('<ul style="color: red;">')
        for error in errors:
            error_list += format_html('<li>{}</li>', error)
        error_list += format_html('</ul>')
        return error_list
    validation_errors.short_description = 'Validation Errors'
    
    def preview_url(self, obj):
        if obj.id:
            try:
                return reverse("careers:careerdetail", kwargs={"slug": obj.slug, "career_id": obj.id})
            except Exception:
                return f"/careers/career/{obj.slug}-{obj.id}-detail/"
        return 'Save first to generate preview URL'
    
    def skills_count(self, obj):
        return obj.skills.count()
    skills_count.short_description = 'Skills'

    def related_careers_summary(self, obj):
        related = list(obj.related_careers.all()[:8])
        if not related:
            return format_html('<span style="color:#888;">Automatic</span>')
        names = '; '.join(c.name for c in related if c.name)
        extra = obj.related_careers.count() - len(related)
        if extra > 0:
            names += f' (+{extra} more)'
        edit_url = reverse('admin:careers_careerrelatedcareers_change', args=[obj.pk])
        return format_html('{}<br><a href="{}">Edit related</a>', names, edit_url)
    related_careers_summary.short_description = 'Related careers'
    
    def created_date(self, obj):
        return obj.created.strftime('%Y-%m-%d %H:%M') if obj.created else '-'
    created_date.short_description = 'Created'

    def modified_date(self, obj):
        return obj.modified.strftime('%Y-%m-%d %H:%M') if obj.modified else '-'
    modified_date.short_description = 'Modified'
    modified_date.admin_order_field = 'modified'

    def image_url_display(self, obj):
        if obj.image and obj.image.name:
            url = obj.image.url
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, url, url[:50] + '...' if len(url) > 50 else url)
        return '-'
    image_url_display.short_description = 'Image URL'
    
    def mindmap_validation(self, obj):
        """Display mindmap validation status with error icon and hover tooltip"""
        is_valid, errors = obj.validate_mindmap()
        
        if is_valid:
            # Show nothing if validated
            return format_html('')
        else:
            # Show error icon with hover tooltip
            error_text = '; '.join(errors) if errors else 'Mindmap validation failed'
            # Escape HTML in error text for title attribute
            from django.utils.html import escape
            escaped_error = escape(error_text)
            return format_html(
                '<span class="mindmap-validation-error" style="color: #dc3545; cursor: help; display: inline-block;" '
                'title="{}" data-bs-toggle="tooltip" data-bs-placement="top">'
                '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16" style="vertical-align: middle;">'
                '<path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>'
                '<path d="M7.002 11a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 4.995a.905.905 0 1 1 1.8 0l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 4.995z"/>'
                '</svg>'
                '</span>',
                escaped_error
            )
    mindmap_validation.short_description = 'Mindmap'
    mindmap_validation.admin_order_field = 'name'
    
    def make_published(self, request, queryset):
        updated = queryset.update(publish_status=1)
        self.message_user(request, f'{updated} career(s) marked as published.')
    make_published.short_description = "Mark selected careers as published"
    
    def make_draft(self, request, queryset):
        updated = queryset.update(publish_status=0)
        self.message_user(request, f'{updated} career(s) marked as draft.')
    make_draft.short_description = "Mark selected careers as draft"
    
    def assign_to_cluster(self, request, queryset):
        """Bulk action to assign careers to a cluster"""
        if request.POST.get('post'):
            cluster_id = request.POST.get('cluster_id')
            if cluster_id:
                cluster = CareerCluster.objects.get(id=cluster_id)
                for career in queryset:
                    career.career_cluster.add(cluster)
                self.message_user(request, f'{queryset.count()} career(s) assigned to {cluster.name}.')
                return None
        
        # Show form for cluster selection
        clusters = CareerCluster.objects.all().order_by('name')
        return render(request, 'admin/careers/career/assign_cluster.html', {
            'careers': queryset,
            'clusters': clusters,
            'action_name': 'assign_to_cluster',
        })
    assign_to_cluster.short_description = "Assign selected careers to cluster"
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'career_paths' in form.base_fields:
            form.base_fields['career_paths'].required = False
        return form
    
    def update_career_cluster_ajax(self, request):
        """Handle AJAX request to update career cluster"""
        if request.method == 'POST':
            try:
                career_id = request.POST.get('career_id')
                cluster_id = request.POST.get('cluster_id')
                
                if not career_id or not cluster_id:
                    return JsonResponse({'success': False, 'error': 'Missing career_id or cluster_id'})
                
                career = Career.objects.get(id=career_id)
                cluster = CareerCluster.objects.get(id=cluster_id)
                
                # Clear existing clusters and add the new one
                career.career_cluster.clear()
                career.career_cluster.add(cluster)
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Career "{career.name}" assigned to cluster "{cluster.name}"'
                })
                
            except Career.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Career not found'})
            except CareerCluster.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Career cluster not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    def get_urls(self):
        """Add custom URLs for AJAX requests"""
        urls = super().get_urls()
        custom_urls = [
            path('update-cluster-ajax/', self.admin_site.admin_view(self.update_career_cluster_ajax), name='careers_career_update_cluster_ajax'),
            path('update-publish-ajax/', self.admin_site.admin_view(self.update_publish_status_ajax), name='careers_career_update_publish_ajax'),
            path('<path:object_id>/json-preview/', self.admin_site.admin_view(self.json_preview), name='careers_career_json_preview'),
        ]
        return custom_urls + urls

    def update_publish_status_ajax(self, request):
        """Handle AJAX request to update publish status"""
        if request.method == 'POST':
            try:
                career_id = request.POST.get('career_id')
                publish_status = request.POST.get('publish_status')
                if not career_id or publish_status is None:
                    return JsonResponse({'success': False, 'error': 'Missing career_id or publish_status'})
                try:
                    publish_status = int(publish_status)
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid publish status value'})

                # Validate against defined choices
                valid_values = {val for val, _ in choices.PublishStatus.CHOICES}
                if publish_status not in valid_values:
                    return JsonResponse({'success': False, 'error': 'Publish status not allowed'})

                career = Career.objects.get(id=career_id)
                # If attempting to publish, run validation first
                published_value = dict(choices.PublishStatus.CHOICES).get(choices.PublishStatus.PUBLISHED, None)
                # The above line yields a label; use numeric constant instead
                published_value = choices.PublishStatus.PUBLISHED
                if publish_status == published_value:
                    errors = career.get_validation_errors()
                    if errors:
                        return JsonResponse({
                            'success': False,
                            'error': '; '.join(errors),
                            'errors': errors
                        })
                career.publish_status = publish_status
                career.save(update_fields=['publish_status'])
                label = dict(choices.PublishStatus.CHOICES).get(publish_status, publish_status)
                return JsonResponse({'success': True, 'message': f'Publish status set to "{label}"'})
            except Career.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Career not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    def json_preview(self, request, object_id):
        """Handle JSON preview request - returns stored JSON or generates from description"""
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Only POST method allowed'})
        
        try:
            career = Career.objects.get(pk=object_id)
        except Career.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Career not found'})
        
        try:
            # Get description from POST data (current editor content)
            description = request.POST.get('description', '')
            
            # If description is provided, parse it (for preview before save)
            # Otherwise, use stored JSON if available
            if description:
                # Create a temporary career object with the description to parse
                from .career_json_parser import CareerDescriptionJSONParser
                temp_career = Career(id=career.id, name=career.name, slug=career.slug, description=description)
                parser = CareerDescriptionJSONParser(temp_career)
                parser.parse_all_sections()
                
                sections = parser.sections
            elif career.description_json:
                # Use stored JSON
                sections = career.description_json.get('sections', {})
            else:
                # Generate from current description
                json_data = career.generate_description_json()
                if json_data:
                    sections = json_data.get('sections', {})
                else:
                    sections = {}
            
            return JsonResponse({
                'success': True,
                'sections': sections,
                'from_stored': bool(career.description_json and not description)
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error generating JSON preview for career {object_id}: {str(e)}', exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)})
    
    class Media:
        css = {
            'all': ('admin/css/docx_processing.css', 'admin/css/mindmap_validation.css',)
        }
        js = ('admin/js/docx_processing.js', 'admin/js/career_cluster_dropdown.js',)
    
    
class CareerPathAdmin(admin.ModelAdmin):
    list_display = ['id','name']
    readonly_fields=['created','modified']
    
class CareerPathStepAdmin(admin.ModelAdmin):
    list_display = ['id','name']
    readonly_fields=['created','modified']
    
class CareerMediaAdmin(admin.ModelAdmin):
    list_display = ['id','career','type','media']
    readonly_fields=['created','modified']
    
class SkillAdmin(admin.ModelAdmin):
    list_display = ['id','name','created','modified']
    readonly_fields=['created','modified']

class ProspectiveEmploymentAreaAdmin(admin.ModelAdmin):
    list_display = ['id','name','created','modified']
    readonly_fields=['created','modified']
    
class ProspectiveRecruiterAdmin(admin.ModelAdmin):
    list_display = ['id','name','created','modified']
    readonly_fields=['created','modified']

class ProfessionAdmin(admin.ModelAdmin):
    list_display =['id','name','salary','career']
    readonly_fields=['created','modified']

class CareerFAQAdmin(admin.ModelAdmin):
    list_display = ['id','career','question','answer']
    readonly_fields=['created','modified']    

class CareerRatingAdmin(admin.ModelAdmin):
    list_display = ['id','career','user','rating']


def career_cluster_activate_selected(modeladmin, request, queryset):
    updated = queryset.update(object_status=choices.ObjectStatus.ACTIVE)
    modeladmin.message_user(request, f'{updated} career cluster(s) activated.', messages.SUCCESS)


def career_cluster_deactivate_selected(modeladmin, request, queryset):
    updated = queryset.update(object_status=choices.ObjectStatus.INACTIVE)
    modeladmin.message_user(request, f'{updated} career cluster(s) deactivated.', messages.SUCCESS)


career_cluster_activate_selected.short_description = 'Activate selected career clusters'
career_cluster_deactivate_selected.short_description = 'Deactivate selected career clusters'


class CareerClusterAdmin(admin.ModelAdmin):
    """Enhanced CareerCluster admin with better organization. Shows all clusters (active, inactive, deleted)."""
    list_display = ['id', 'name', 'parent', 'careers_count', 'has_track_icon', 'object_status', 'created']
    list_filter = ['parent', 'object_status', 'created']
    search_fields = ['name']
    list_per_page = 25
    ordering = ['name']
    actions = [career_cluster_activate_selected, career_cluster_deactivate_selected]
    
    def get_queryset(self, request):
        """Show all clusters (active, inactive, deleted) in admin."""
        return CareerCluster.all_objects.get_queryset().order_by('name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'parent', 'image', 'object_status'),
        }),
        ('Career track icon (home page scroller)', {
            'fields': ('career_track_icon', 'career_track_icon_s3_url'),
            'description': 'Upload SVG icon; it will be uploaded to S3 and the URL stored. Used on home page "Find Your Perfect Fit!" scroller. If empty, a default icon is shown.',
        }),
    )
    readonly_fields = ['career_track_icon_s3_url']
    
    def save_model(self, request, obj, form, change):
        from django.core.files.uploadedfile import UploadedFile
        from django.conf import settings
        from django.contrib import messages
        career_track_icon_file = form.cleaned_data.get('career_track_icon')
        if career_track_icon_file and isinstance(career_track_icon_file, UploadedFile) and career_track_icon_file.name:
            from core.s3_utils import get_s3_upload_service
            s3_service = get_s3_upload_service()
            if s3_service.is_enabled():
                folder = getattr(settings, 'S3_CAREER_TRACK_ICONS_FOLDER', 'career_track_icons')
                result = s3_service.upload_file(
                    file_obj=career_track_icon_file,
                    folder_path=folder,
                    description=f'Career track icon for cluster: {obj.name or obj.pk}',
                    uploaded_by=request.user.username if request.user.is_authenticated else '',
                )
                if result.get('success'):
                    obj.career_track_icon_s3_url = result.get('s3_url')
                else:
                    messages.warning(request, f'S3 upload skipped: {result.get("error", "Unknown error")}. Icon saved locally only.')
        super().save_model(request, obj, form, change)
    
    def has_track_icon(self, obj):
        return bool(obj.career_track_icon and obj.career_track_icon.name)
    has_track_icon.boolean = True
    has_track_icon.short_description = 'Track icon'
    
    def careers_count(self, obj):
        """Show number of careers in this cluster"""
        count = obj.career_clusters.count()
        if count > 0:
            return format_html(
                '<a href="/admin/careers/career/?career_cluster__id__exact={}" target="_blank">{}</a>',
                obj.id, count
            )
        return count
    careers_count.short_description = "Careers"
    careers_count.admin_order_field = 'career_clusters__count'


class CareerRelatedCareersAdmin(admin.ModelAdmin):
    """Dedicated admin list for managing Career.related_careers + CSV import."""

    change_list_template = 'admin/careers/careerrelatedcareers/change_list.html'
    list_display = ['id', 'name', 'career_clusters_short', 'related_careers_summary', 'related_count']
    list_filter = ['publish_status', 'career_cluster']
    search_fields = ['name', 'id']
    filter_horizontal = ['related_careers']
    ordering = ['name', 'id']
    list_per_page = 50
    fields = ['name', 'related_careers']
    readonly_fields = ['name']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'career_cluster', 'related_careers',
        )

    def career_clusters_short(self, obj):
        names = [c.name for c in obj.career_cluster.all() if c.name]
        return ', '.join(names) if names else '—'
    career_clusters_short.short_description = 'Cluster'

    def related_careers_summary(self, obj):
        related = list(obj.related_careers.all())
        if not related:
            return format_html('<span style="color:#888;">— none (automatic on site) —</span>')
        return '; '.join(c.name for c in related if c.name)
    related_careers_summary.short_description = 'Related careers'

    def related_count(self, obj):
        return obj.related_careers.count()
    related_count.short_description = 'Count'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='careers_careerrelatedcareers_import_csv',
            ),
        ]
        return custom + urls

    def import_csv_view(self, request):
        from django.contrib import messages
        from django.shortcuts import redirect

        if request.method == 'POST':
            upload = request.FILES.get('csv_file')
            dry_run = request.POST.get('dry_run') == 'on'
            clear_empty = request.POST.get('clear_empty') == 'on'
            if not upload:
                messages.error(request, 'Please choose a CSV file.')
            else:
                result = import_related_careers_from_csv(
                    upload,
                    dry_run=dry_run,
                    clear_existing=clear_empty,
                )
                level = messages.SUCCESS if not result.errors else messages.WARNING
                messages.add_message(
                    request,
                    level,
                    result.summary(),
                )
                for err in result.errors[:20]:
                    messages.warning(request, err)
                if not dry_run:
                    return redirect('admin:careers_careerrelatedcareers_changelist')

        return render(request, 'admin/careers/careerrelatedcareers/import_csv.html', {
            **self.admin_site.each_context(request),
            'title': 'Import related careers from CSV',
            'opts': self.model._meta,
        })


admin.site.register(Career, CareerAdmin)
admin.site.register(CareerRelatedCareers, CareerRelatedCareersAdmin)
admin.site.register(Skill,SkillAdmin)
admin.site.register(ProspectiveEmploymentArea,ProspectiveEmploymentAreaAdmin)
admin.site.register(ProspectiveRecruiter,ProspectiveRecruiterAdmin)
admin.site.register(CareerMedia,CareerMediaAdmin)
admin.site.register(CareerPath,CareerPathAdmin)
admin.site.register(CareerPathStep,CareerPathStepAdmin)
admin.site.register(Profession,ProfessionAdmin)
admin.site.register(CareerFAQ,CareerFAQAdmin)
admin.site.register(CareerCluster, CareerClusterAdmin)
admin.site.register(RIASECCareer)
admin.site.register(CareerRating,CareerRatingAdmin)

