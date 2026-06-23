from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
import html as html_module

from communication.email_preview import render_admin_email_preview
from communication.email_template_registry import get_email_template_meta
from communication.forms import EmailMessageTemplateAdminForm
from .models import CommunicationLog, EmailMessageTemplate, OTP
from core import choices


# Register your models here.
class CommunicationLogAdmin(admin.ModelAdmin):
    readonly_fields = ('created','id')
    fields = ['created','to','body','type']
    date_hierarchy = 'created'
    list_display = ['id', 'created','to','type','response']
    sortable_by=['id', 'to','created']
    ordering = ['-id']
    # list_editable=['name','email']
    list_filter = ('created','type')
    search_fields=['to','body']
    list_display_links=['id','to']

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type=choices.CommunicationTypeChooices.EMAIL)


def _admin_pre_block(content):
    return format_html(
        '<pre class="email-template-admin-block" '
        'style="color:#111111 !important;background:#ffffff !important;">{}</pre>',
        escape(content),
    )


@admin.register(EmailMessageTemplate)
class EmailMessageTemplateAdmin(admin.ModelAdmin):
    form = EmailMessageTemplateAdminForm
    list_display = ('slug', 'name', 'builtin_template_path', 'is_active', 'modified')
    list_filter = ('is_active',)
    search_fields = ('slug', 'name', 'subject_template', 'body_html_template')
    readonly_fields = (
        'template_instructions',
        'builtin_template_path',
        'sample_subject_preview',
        'sample_body_preview',
        'email_live_preview',
        'created',
        'modified',
    )

    actions = ('reload_from_builtin',)

    class Media:
        css = {
            'all': ('admin/css/email_message_template_admin.css',),
        }
        js = ('admin/js/email_message_template_admin.js',)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:
            readonly.append('slug')
        return readonly

    @admin.display(description='Built-in template file')
    def builtin_template_path(self, obj):
        if not obj:
            return '—'
        path = get_email_template_meta(obj.slug).get('template_path')
        return path or '—'

    @admin.display(description='Instructions')
    def template_instructions(self, obj):
        slug = (obj.slug if obj else '').strip()
        meta = get_email_template_meta(slug)
        lines = [
            'How to use this screen',
            '------------------------',
            f'1. This entry (slug: {slug or "—"}) maps to a system email sent by the platform.',
            '2. Paste or edit Subject template and Body HTML template below.',
            '3. Keep placeholders exactly as shown — they are replaced when the email is sent.',
            '4. Edit the Body HTML template below (message content only). Shared TopTeen header, logo, and footer are added automatically from mail/base_email.html when the email is sent.',
            '5. Set Is active to off to disable the custom template and fall back to defaults.',
            '',
            'Default subject (when Subject template is empty):',
            meta.get('default_subject') or '(none)',
            '',
        ]
        placeholder_help = meta.get('placeholder_help')
        if placeholder_help:
            lines.extend(['Placeholders', '------------', placeholder_help])
        lines.extend([
            '',
            'Important',
            '---------',
            '- Use {placeholder} style — not Django template tags like {{ name }}.',
            '- Do not rename slug after creation; code references it when sending mail.',
            '- Edit message body only. Header, logo, and footer are always added from mail/base_email.html when sent.',
            '- Copy sample subject/body below when available, then customize.',
        ])
        return _admin_pre_block('\n'.join(lines))

    @admin.display(description='Sample subject (copy into Subject template)')
    def sample_subject_preview(self, obj):
        sample = get_email_template_meta(obj.slug if obj else '').get('sample_subject')
        if not sample:
            return mark_safe('<p class="help">No sample subject for this template.</p>')
        return _admin_pre_block(sample)

    @admin.display(description='Sample body HTML (copy into Body HTML template)')
    def sample_body_preview(self, obj):
        sample = get_email_template_meta(obj.slug if obj else '').get('sample_body_html')
        if not sample:
            return mark_safe('<p class="help">No sample body for this template.</p>')
        return _admin_pre_block(sample)

    def _build_preview_html(self, slug, subject_template='', body_html_template=''):
        subject, html = render_admin_email_preview(slug, subject_template, body_html_template)
        iframe = format_html(
            '<iframe class="email-template-live-preview-frame" srcdoc="{}" '
            'style="width:100%;min-height:560px;border:1px solid #d1d5db;border-radius:8px;background:#fff;" '
            'title="Email preview"></iframe>',
            mark_safe(html_module.escape(html, quote=True)),
        )
        return format_html(
            '<div class="email-template-live-preview-wrap" data-slug="{}">'
            '<p style="margin:0 0 8px;color:#111111 !important;"><strong>Subject:</strong> {}</p>'
            '<p class="help" style="margin:0 0 12px;color:#444444 !important;">'
            'Full email with shared header/footer from <code>mail/base_email.html</code>. '
            'Sample placeholder values are used.</p>'
            '<button type="button" class="button email-template-preview-refresh" '
            'style="margin-bottom:12px;">Refresh preview from fields above</button>'
            '{}'
            '</div>',
            escape(slug),
            escape(subject),
            iframe,
        )

    @admin.display(description='Live email preview')
    def email_live_preview(self, obj):
        if not obj or not obj.slug:
            return mark_safe('<p class="help">Save the template to see a live preview.</p>')
        return self._build_preview_html(obj.slug, obj.subject_template, obj.body_html_template)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/preview/',
                self.admin_site.admin_view(self.preview_email_template),
                name='communication_emailmessagetemplate_preview',
            ),
        ]
        return custom_urls + urls

    def preview_email_template(self, request, object_id):
        obj = self.get_object(request, object_id)
        if not obj:
            return JsonResponse({'error': 'Template not found'}, status=404)
        subject_template = request.POST.get('subject_template', obj.subject_template)
        body_html_template = request.POST.get('body_html_template', obj.body_html_template)
        subject, html = render_admin_email_preview(
            obj.slug,
            subject_template,
            body_html_template,
        )
        return JsonResponse({'subject': subject, 'html': html})

    @admin.action(description='Reload subject/body from built-in template file')
    def reload_from_builtin(self, request, queryset):
        from communication.builtin_email_content import populate_template_defaults
        updated = 0
        for obj in queryset:
            if populate_template_defaults(obj, force=True):
                updated += 1
        self.message_user(
            request,
            f'Reloaded {updated} template(s) from built-in HTML files.',
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            from communication.builtin_email_content import populate_template_defaults
            populate_template_defaults(obj, force=False)

    def get_fieldsets(self, request, obj=None):
        instruction_fields = (
            'template_instructions',
            'builtin_template_path',
            'sample_subject_preview',
            'sample_body_preview',
        )
        meta = get_email_template_meta(obj.slug if obj else '')
        if not meta.get('sample_subject') and not meta.get('sample_body_html'):
            instruction_fields = ('template_instructions', 'builtin_template_path')

        return (
            (None, {
                'fields': ('slug', 'name', 'is_active'),
            }),
            ('Instructions & samples', {
                'fields': instruction_fields,
                'description': (
                    'Body HTML is the message content only. Header (logo) and footer (copyright, links) '
                    'come from the shared template mail/base_email.html.'
                ),
            }),
            ('Email content (editable)', {
                'fields': ('subject_template', 'body_html_template'),
                'description': (
                    'Edit message body only — do not add logo/header/footer here; they are injected automatically. '
                    'For links in CKEditor use http://{url_no_scheme} when available, or full URLs like {url}.'
                ),
            }),
            ('Live preview', {
                'fields': ('email_live_preview',),
                'description': 'Preview shows the final email with header, logo, and footer applied.',
            }),
            ('Timestamps', {
                'fields': ('created', 'modified'),
            }),
        )


admin.site.register(OTP)
admin.site.register(CommunicationLog, CommunicationLogAdmin)
