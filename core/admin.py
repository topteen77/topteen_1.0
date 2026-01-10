from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
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
)
# Register your models here.



class ConfigurationAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','key')
    fields = ['created','modified','key','value']
    date_hierarchy = 'created'
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


class CityAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','state']
    date_hierarchy = 'created'
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
    date_hierarchy = 'created'
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
    date_hierarchy = 'created'
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
admin.site.register(Review)
admin.site.register(CommonFAQ)
admin.site.register(APILog)
admin.site.register(Stories)
admin.site.register(Contact,ContactAdmin)


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


@admin.register(VocationalCourse)
class VocationalCourseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "priority", "object_status", "image")
    list_filter = ("object_status", "category")
    search_fields = ("name", "category__name")
    ordering = ("category__name", "priority", "name")
    fields = ("category", "name", "slug", "image", "content_html", "priority", "object_status", "created", "modified")
    readonly_fields = ("created", "modified")


class EbookAdminForm(forms.ModelForm):
    class Meta:
        model = Ebook
        fields = '__all__'
    
    def clean_cover_image(self):
        """Validate cover image size"""
        cover_image = self.cleaned_data.get('cover_image')
        if cover_image:
            # Check if it's a new upload (has file attribute)
            if hasattr(cover_image, 'size'):
                # Limit cover image to 3MB
                max_size = 3 * 1024 * 1024  # 3 MB
                if cover_image.size > max_size:
                    raise ValidationError('Cover image size must be under 3MB. Current size: {:.2f}MB'.format(
                        cover_image.size / (1024 * 1024)
                    ))
        return cover_image
    
    def clean_pdf_file(self):
        """Validate PDF file size"""
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file:
            # Check if it's a new upload (has file attribute)
            if hasattr(pdf_file, 'size'):
                # Limit PDF to 3MB
                max_size = 3 * 1024 * 1024  # 3 MB
                if pdf_file.size > max_size:
                    raise ValidationError('PDF file size must be under 3MB. Current size: {:.2f}MB'.format(
                        pdf_file.size / (1024 * 1024)
                    ))
                # Check file extension
                if not pdf_file.name.lower().endswith('.pdf'):
                    raise ValidationError('Only PDF files are allowed.')
        return pdf_file


@admin.register(Ebook)
class EbookAdmin(admin.ModelAdmin):
    form = EbookAdminForm
    list_display = ("id", "title", "priority", "publish_status", "object_status", "cover_preview", "file_size_display", "created", "modified")
    list_filter = ("publish_status", "object_status", "created", "modified")
    search_fields = ("title", "description")
    ordering = ("priority", "title")
    fields = (
        "title",
        "slug",
        "description",
        "cover_image",
        "cover_preview",
        "pdf_file",
        "priority",
        "publish_status",
        "object_status",
        "created",
        "modified"
    )
    readonly_fields = ("created", "modified", "cover_preview")
    list_editable = ("priority", "publish_status")

    def cover_preview(self, obj):
        """Display cover image preview in admin"""
        if obj.cover_image and obj.cover_image.name:
            from django.utils.html import format_html
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 200px; object-fit: contain;" />',
                obj.cover_image.url
            )
        return "No cover image"
    cover_preview.short_description = "Cover Preview"
    
    def file_size_display(self, obj):
        """Display PDF file size"""
        if obj.pdf_file and obj.pdf_file.name:
            try:
                size = obj.pdf_file.size
                if size < 1024:
                    return f"{size} B"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.2f} KB"
                else:
                    return f"{size / (1024 * 1024):.2f} MB"
            except (OSError, ValueError):
                return "N/A"
        return "No file"
    file_size_display.short_description = "PDF Size"


