"""
Admin interface for Combined Report Mapping System
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from .models import ClusterMapping, RoleMapping, PathwayMapping, AptitudeCombinationMapping


@admin.register(ClusterMapping)
class ClusterMappingAdmin(admin.ModelAdmin):
    list_display = ('excel_name', 'get_db_cluster', 'is_mapped', 'get_mapping_status', 'get_db_cluster_link', 'notes_preview', 'updated_at')
    list_filter = ('is_mapped', 'created_at', 'updated_at')
    search_fields = ('excel_name', 'db_cluster__name', 'notes')
    list_editable = ('is_mapped',)
    readonly_fields = ('created_at', 'updated_at', 'get_mapping_status')
    fields = ('excel_name', 'db_cluster', 'is_mapped', 'notes', 'created_at', 'updated_at')
    raw_id_fields = ('db_cluster',)
    
    def get_db_cluster(self, obj):
        if obj.db_cluster:
            return obj.db_cluster.name
        return format_html('<span style="color: red; font-weight: bold;">UNMAPPED</span>')
    get_db_cluster.short_description = 'Database Cluster'
    
    def get_mapping_status(self, obj):
        if obj.is_mapped:
            return format_html('<span style="color: green; font-weight: bold;">✓ MAPPED</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ UNMAPPED</span>')
    get_mapping_status.short_description = 'Status'
    
    def get_db_cluster_link(self, obj):
        if obj.db_cluster:
            url = reverse('admin:careers_careercluster_change', args=[obj.db_cluster.pk])
            return format_html('<a href="{}" target="_blank">View DB Cluster</a>', url)
        return '-'
    get_db_cluster_link.short_description = 'Link'
    
    def notes_preview(self, obj):
        if obj.notes:
            return obj.notes[:50] + '...' if len(obj.notes) > 50 else obj.notes
        return '-'
    notes_preview.short_description = 'Notes'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Highlight unmapped items
        return qs.select_related('db_cluster')
    
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if hasattr(response, 'context_data'):
            # Add statistics
            total = ClusterMapping.objects.count()
            mapped = ClusterMapping.objects.filter(is_mapped=True).count()
            unmapped = total - mapped
            response.context_data['mapping_stats'] = {
                'total': total,
                'mapped': mapped,
                'unmapped': unmapped,
                'percentage': round((mapped / total * 100) if total > 0 else 0, 1)
            }
        return response


@admin.register(RoleMapping)
class RoleMappingAdmin(admin.ModelAdmin):
    list_display = ('excel_name', 'get_db_role', 'is_mapped', 'get_mapping_status', 'get_db_role_link', 'notes_preview', 'updated_at')
    list_filter = ('is_mapped', 'created_at', 'updated_at')
    search_fields = ('excel_name', 'db_role__name', 'notes')
    list_editable = ('is_mapped',)
    readonly_fields = ('created_at', 'updated_at', 'get_mapping_status')
    fields = ('excel_name', 'db_role', 'is_mapped', 'notes', 'created_at', 'updated_at')
    raw_id_fields = ('db_role',)
    
    def get_db_role(self, obj):
        if obj.db_role:
            return obj.db_role.name
        return format_html('<span style="color: red; font-weight: bold;">UNMAPPED</span>')
    get_db_role.short_description = 'Database Role'
    
    def get_mapping_status(self, obj):
        if obj.is_mapped:
            return format_html('<span style="color: green; font-weight: bold;">✓ MAPPED</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ UNMAPPED</span>')
    get_mapping_status.short_description = 'Status'
    
    def get_db_role_link(self, obj):
        if obj.db_role:
            url = reverse('admin:careers_career_change', args=[obj.db_role.pk])
            return format_html('<a href="{}" target="_blank">View DB Role</a>', url)
        return '-'
    get_db_role_link.short_description = 'Link'
    
    def notes_preview(self, obj):
        if obj.notes:
            return obj.notes[:50] + '...' if len(obj.notes) > 50 else obj.notes
        return '-'
    notes_preview.short_description = 'Notes'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('db_role')
    
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if hasattr(response, 'context_data'):
            total = RoleMapping.objects.count()
            mapped = RoleMapping.objects.filter(is_mapped=True).count()
            unmapped = total - mapped
            response.context_data['mapping_stats'] = {
                'total': total,
                'mapped': mapped,
                'unmapped': unmapped,
                'percentage': round((mapped / total * 100) if total > 0 else 0, 1)
            }
        return response


@admin.register(PathwayMapping)
class PathwayMappingAdmin(admin.ModelAdmin):
    list_display = ('excel_name', 'get_db_pathway', 'is_mapped', 'get_mapping_status', 'get_db_pathway_link', 'notes_preview', 'updated_at')
    list_filter = ('is_mapped', 'created_at', 'updated_at')
    search_fields = ('excel_name', 'db_pathway__name', 'notes')
    list_editable = ('is_mapped',)
    readonly_fields = ('created_at', 'updated_at', 'get_mapping_status')
    fields = ('excel_name', 'db_pathway', 'is_mapped', 'notes', 'created_at', 'updated_at')
    raw_id_fields = ('db_pathway',)
    
    def get_db_pathway(self, obj):
        if obj.db_pathway:
            return obj.db_pathway.name
        return format_html('<span style="color: red; font-weight: bold;">UNMAPPED</span>')
    get_db_pathway.short_description = 'Database Pathway'
    
    def get_mapping_status(self, obj):
        if obj.is_mapped:
            return format_html('<span style="color: green; font-weight: bold;">✓ MAPPED</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ UNMAPPED</span>')
    get_mapping_status.short_description = 'Status'
    
    def get_db_pathway_link(self, obj):
        if obj.db_pathway:
            url = reverse('admin:app_course_change', args=[obj.db_pathway.pk])
            return format_html('<a href="{}" target="_blank">View DB Pathway</a>', url)
        return '-'
    get_db_pathway_link.short_description = 'Link'
    
    def notes_preview(self, obj):
        if obj.notes:
            return obj.notes[:50] + '...' if len(obj.notes) > 50 else obj.notes
        return '-'
    notes_preview.short_description = 'Notes'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('db_pathway')
    
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if hasattr(response, 'context_data'):
            total = PathwayMapping.objects.count()
            mapped = PathwayMapping.objects.filter(is_mapped=True).count()
            unmapped = total - mapped
            response.context_data['mapping_stats'] = {
                'total': total,
                'mapped': mapped,
                'unmapped': unmapped,
                'percentage': round((mapped / total * 100) if total > 0 else 0, 1)
            }
        return response


class ClusterInline(admin.TabularInline):
    model = AptitudeCombinationMapping.clusters.through
    extra = 0
    verbose_name = "Cluster"
    verbose_name_plural = "Clusters"


class RoleInline(admin.TabularInline):
    model = AptitudeCombinationMapping.roles.through
    extra = 0
    verbose_name = "Role"
    verbose_name_plural = "Roles"


class PathwayInline(admin.TabularInline):
    model = AptitudeCombinationMapping.pathways.through
    extra = 0
    verbose_name = "Pathway"
    verbose_name_plural = "Pathways"


@admin.register(AptitudeCombinationMapping)
class AptitudeCombinationMappingAdmin(admin.ModelAdmin):
    list_display = ('aptitude_code', 'aptitude_areas', 'get_cluster_count', 'get_role_count', 'get_pathway_count', 'get_completion_status', 'updated_at')
    list_filter = ('is_complete', 'created_at', 'updated_at')
    search_fields = ('aptitude_code', 'aptitude_areas')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('aptitude_code', 'aptitude_areas', 'is_complete', 'notes')
        }),
        ('Mappings', {
            'fields': ('clusters', 'roles', 'pathways'),
            'description': 'Select clusters, roles, and pathways from the master mappings'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ('clusters', 'roles', 'pathways')
    
    def get_cluster_count(self, obj):
        count = obj.clusters.count()
        if count == 0:
            return format_html('<span style="color: red; font-weight: bold;">0 (ERROR)</span>')
        return count
    get_cluster_count.short_description = 'Clusters'
    
    def get_role_count(self, obj):
        count = obj.roles.count()
        if count == 0:
            return format_html('<span style="color: red; font-weight: bold;">0 (ERROR)</span>')
        return count
    get_role_count.short_description = 'Roles'
    
    def get_pathway_count(self, obj):
        count = obj.pathways.count()
        if count == 0:
            return format_html('<span style="color: red; font-weight: bold;">0 (ERROR)</span>')
        return count
    get_pathway_count.short_description = 'Pathways'
    
    def get_completion_status(self, obj):
        if obj.is_complete:
            return format_html('<span style="color: green; font-weight: bold;">✓ COMPLETE</span>')
        return format_html('<span style="color: orange; font-weight: bold;">⚠ INCOMPLETE</span>')
    get_completion_status.short_description = 'Status'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('clusters', 'roles', 'pathways')
    
    def log_change(self, request, obj, message):
        """Override to ensure ASCII-safe object_repr for MySQL compatibility"""
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        
        # Create ASCII-safe representation
        status = "[COMPLETE]" if obj.is_complete else "[INCOMPLETE]"
        object_repr = f"{status} {obj.aptitude_code}: {obj.aptitude_areas}"
        # Ensure no Unicode characters
        object_repr = object_repr.encode('ascii', 'ignore').decode('ascii')
        
        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=object_repr,
            action_flag=CHANGE,
            change_message=message,
        )
