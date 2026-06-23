from django.contrib import admin
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe

from communication.email_templates import (
    REFERRAL_EMAIL_SLUG,
    REFERRAL_PLACEHOLDER_HELP,
    REFERRAL_SAMPLE_BODY_HTML,
    REFERRAL_SAMPLE_SUBJECT,
)
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
    list_display = ('slug', 'name', 'is_active', 'modified')
    list_filter = ('is_active',)
    search_fields = ('slug', 'name', 'subject_template', 'body_html_template')
    readonly_fields = (
        'template_instructions',
        'sample_subject_preview',
        'sample_body_preview',
        'created',
        'modified',
    )

    class Media:
        css = {
            'all': ('admin/css/email_message_template_admin.css',),
        }
        js = ('admin/js/email_message_template_admin.js',)

    @admin.display(description='Instructions')
    def template_instructions(self, obj):
        slug = (obj.slug if obj else '') or REFERRAL_EMAIL_SLUG
        lines = [
            'How to use this screen',
            '------------------------',
            '1. Open the template with slug: refer_friend (Refer a friend invitation).',
            '2. Paste or edit the Subject template and Body HTML template below.',
            '3. Keep placeholders exactly as shown — they are replaced automatically when a user sends an invite.',
            '4. Leave both fields empty to use the built-in default email from the codebase.',
            '5. Set Is active to off to disable the custom template and fall back to defaults.',
            '',
            REFERRAL_PLACEHOLDER_HELP,
            '',
            'Important',
            '---------',
            '- Use {inviter_name} style placeholders — not Django template tags like {{ name }}.',
            '- Do not rename slug "refer_friend" for the invite-a-friend email.',
            '- Copy the sample subject/body below into the editable fields, then customize.',
        ]
        if slug != REFERRAL_EMAIL_SLUG:
            lines.extend([
                '',
                'Note: Placeholder samples above apply to slug "refer_friend". '
                'Other slugs may use different variables in future.',
            ])
        return _admin_pre_block('\n'.join(lines))

    @admin.display(description='Sample subject (copy into Subject template)')
    def sample_subject_preview(self, obj):
        if obj and obj.slug != REFERRAL_EMAIL_SLUG:
            return mark_safe('<p class="help">No sample for this slug yet.</p>')
        return _admin_pre_block(REFERRAL_SAMPLE_SUBJECT)

    @admin.display(description='Sample body HTML (copy into Body HTML template)')
    def sample_body_preview(self, obj):
        if obj and obj.slug != REFERRAL_EMAIL_SLUG:
            return mark_safe('<p class="help">No sample for this slug yet.</p>')
        return _admin_pre_block(REFERRAL_SAMPLE_BODY_HTML)

    def get_fieldsets(self, request, obj=None):
        instruction_fields = (
            'template_instructions',
            'sample_subject_preview',
            'sample_body_preview',
        )
        if obj and obj.slug != REFERRAL_EMAIL_SLUG:
            instruction_fields = ('template_instructions',)

        return (
            (None, {
                'fields': ('slug', 'name', 'is_active'),
            }),
            ('Instructions & samples', {
                'fields': instruction_fields,
                'description': (
                    'Refer-a-friend email uses slug <strong>refer_friend</strong>. '
                    'Copy the samples into the fields in the next section.'
                ),
            }),
            ('Email content (editable)', {
                'fields': ('subject_template', 'body_html_template'),
                'description': (
                    'For links in CKEditor use <code>http://{referral_url}</code> (no https in placeholder). '
                    'Or use <code>{referral_url_full}</code> directly in href.'
                ),
            }),
            ('Timestamps', {
                'fields': ('created', 'modified'),
            }),
        )


admin.site.register(OTP)
admin.site.register(CommunicationLog, CommunicationLogAdmin)
