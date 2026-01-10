from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.conf import settings
        s3_base_url = getattr(settings, 'S3_BUCKET_BASE_URL', 'https://topteenc.s3.ap-northeast-1.amazonaws.com/')
        s3_ebook_folder = getattr(settings, 'S3_EBOOK_FOLDER', 'ebook')
        
        # Set placeholders with S3 base URL
        cover_placeholder = f'{s3_base_url}{s3_ebook_folder}/cover/image.jpg'
        pdf_placeholder = f'{s3_base_url}{s3_ebook_folder}/pdf/book.pdf'
        
        # Update cover image S3 URL field
        if 'cover_image_s3_url' in self.fields:
            self.fields['cover_image_s3_url'].widget.attrs.update({
                'placeholder': cover_placeholder,
                'style': 'width: 100%;'
            })
            self.fields['cover_image_s3_url'].help_text = f'S3 URL for cover image. Example: {cover_placeholder}'
        
        # Update PDF file S3 URL field
        if 'pdf_file_s3_url' in self.fields:
            self.fields['pdf_file_s3_url'].widget.attrs.update({
                'placeholder': pdf_placeholder,
                'style': 'width: 100%;'
            })
            self.fields['pdf_file_s3_url'].help_text = f'S3 URL for PDF file. Example: {pdf_placeholder}'
    
    def clean(self):
        """Validate that either file upload or S3 URL is provided"""
        cleaned_data = super().clean()
        
        # Validate cover image - either file upload OR S3 URL
        cover_image = cleaned_data.get('cover_image')
        cover_image_s3_url = cleaned_data.get('cover_image_s3_url')
        
        # Check if this is a new upload (file object with name attribute)
        is_new_cover_upload = cover_image and hasattr(cover_image, 'name') and cover_image.name
        
        # If editing existing object, check if it already has a cover
        if self.instance and self.instance.pk:
            existing_cover = self.instance.cover_image and self.instance.cover_image.name
            existing_cover_s3 = self.instance.cover_image_s3_url
            # Only require if no existing cover and no new data provided
            if not is_new_cover_upload and not cover_image_s3_url and not existing_cover and not existing_cover_s3:
                raise ValidationError({
                    'cover_image': 'Either upload a cover image file or provide an S3 URL.',
                    'cover_image_s3_url': 'Either upload a cover image file or provide an S3 URL.'
                })
        else:
            # New object - must have either file or S3 URL
            if not is_new_cover_upload and not cover_image_s3_url:
                raise ValidationError({
                    'cover_image': 'Either upload a cover image file or provide an S3 URL.',
                    'cover_image_s3_url': 'Either upload a cover image file or provide an S3 URL.'
                })
        
        # If both are provided, prioritize S3 URL (clear file upload)
        if is_new_cover_upload and cover_image_s3_url:
            cleaned_data['cover_image'] = None
        
        # Validate PDF file - either file upload OR S3 URL
        pdf_file = cleaned_data.get('pdf_file')
        pdf_file_s3_url = cleaned_data.get('pdf_file_s3_url')
        
        # Check if this is a new upload (file object with name attribute)
        is_new_pdf_upload = pdf_file and hasattr(pdf_file, 'name') and pdf_file.name
        
        # If editing existing object, check if it already has a PDF
        if self.instance and self.instance.pk:
            existing_pdf = self.instance.pdf_file and self.instance.pdf_file.name
            existing_pdf_s3 = self.instance.pdf_file_s3_url
            # Only require if no existing PDF and no new data provided
            if not is_new_pdf_upload and not pdf_file_s3_url and not existing_pdf and not existing_pdf_s3:
                raise ValidationError({
                    'pdf_file': 'Either upload a PDF file or provide an S3 URL.',
                    'pdf_file_s3_url': 'Either upload a PDF file or provide an S3 URL.'
                })
        else:
            # New object - must have either file or S3 URL
            if not is_new_pdf_upload and not pdf_file_s3_url:
                raise ValidationError({
                    'pdf_file': 'Either upload a PDF file or provide an S3 URL.',
                    'pdf_file_s3_url': 'Either upload a PDF file or provide an S3 URL.'
                })
        
        # If both are provided, prioritize S3 URL (clear file upload)
        if is_new_pdf_upload and pdf_file_s3_url:
            cleaned_data['pdf_file'] = None
        
        return cleaned_data
    
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
    
    def clean_cover_image_s3_url(self):
        """Validate S3 cover image URL"""
        cover_image_s3_url = self.cleaned_data.get('cover_image_s3_url')
        if cover_image_s3_url:
            # Basic URL validation
            if not (cover_image_s3_url.startswith('http://') or cover_image_s3_url.startswith('https://')):
                raise ValidationError('S3 URL must start with http:// or https://')
        return cover_image_s3_url
    
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
    list_display = ("id", "title", "priority", "publish_status", "object_status", "cover_preview", "file_source_display", "created", "modified")
    list_filter = ("publish_status", "object_status", "created", "modified")
    search_fields = ("title", "description")
    ordering = ("priority", "title")
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'priority', 'publish_status', 'object_status')
        }),
        ('Cover Image', {
            'fields': ('cover_image', 'cover_image_s3_url', 'cover_preview'),
            'description': 'Either upload a cover image file OR provide an S3 URL. S3 URL takes priority if both are provided.'
        }),
        ('PDF File', {
            'fields': ('pdf_file', 'pdf_file_s3_url'),
            'description': 'Either upload a PDF file OR provide an S3 URL. S3 URL takes priority if both are provided.'
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ("created", "modified", "cover_preview")
    list_editable = ("priority", "publish_status")

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


