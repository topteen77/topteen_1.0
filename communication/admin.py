from django.contrib import admin
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe

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
            ('Timestamps', {
                'fields': ('created', 'modified'),
            }),
        )


admin.site.register(OTP)
admin.site.register(CommunicationLog, CommunicationLogAdmin)
