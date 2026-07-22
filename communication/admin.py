from django.contrib import admin, messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.conf import settings as django_settings
import html as html_module

from communication.email_preview import render_admin_email_preview
from communication.email_template_registry import get_email_template_meta
from communication.forms import EmailMessageTemplateAdminForm, MessagingSettingsAdminForm
from communication.messaging_config import (
    is_production_messaging_env,
    seed_messaging_settings_from_env,
)
from .models import CommunicationLog, EmailMessageTemplate, MessagingSettings, OTP
from core import choices


class CommunicationLogAdmin(admin.ModelAdmin):
    readonly_fields = ('created', 'id')
    fields = ['created', 'to', 'body', 'type']
    date_hierarchy = 'created'
    list_display = ['id', 'created', 'to', 'type', 'response']
    sortable_by = ['id', 'to', 'created']
    ordering = ['-id']
    list_filter = ('created', 'type')
    search_fields = ['to', 'body']
    list_display_links = ['id', 'to']

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
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


@admin.register(MessagingSettings)
class MessagingSettingsAdmin(admin.ModelAdmin):
    """Single page: SMS + WhatsApp channel, providers, templates, and API keys."""

    form = MessagingSettingsAdminForm
    change_form_template = 'admin/communication/messagingsettings/change_form.html'
    list_display = ('active_channel', 'sms_provider', 'whatsapp_provider', 'updated_at')
    readonly_fields = ('updated_at', 'runtime_status')

    fieldsets = (
        ('Active channel (only one)', {
            'fields': (
                'active_channel',
                'sender_mode',
                'force_send_non_production',
                'runtime_status',
            ),
            'description': (
                'Pick SMS only, WhatsApp only, or Disabled. '
                'Without API keys the selected service stays disabled. '
                'Testing/sandbox numbers are blocked when the app is in production.'
            ),
        }),
        ('Providers (plug-and-play)', {
            'fields': ('sms_provider', 'whatsapp_provider'),
        }),
        ('Message templates', {
            'fields': (
                'sms_message_template',
                'whatsapp_otp_template',
                'whatsapp_otp_template_lang',
            ),
            'description': (
                'SMS text uses {otp}. WhatsApp uses a Meta-approved template name '
                '(create/approve in Plivo console).'
            ),
        }),
        ('SmartPing keys (SMS)', {
            'fields': (
                'smartping_api_url',
                'smartping_username',
                'smartping_password',
                'smartping_from',
                'smartping_dlt_content_id',
                'smartping_dlt_principal_entity_id',
                'smartping_unicode',
            ),
            'classes': ('collapse',),
            'description': 'Required when SMS provider = SmartPing. Empty keys = SmartPing disabled.',
        }),
        ('Plivo keys (SMS + WhatsApp)', {
            'fields': (
                'plivo_auth_id',
                'plivo_auth_token',
                'plivo_sms_from',
                'plivo_whatsapp_from',
            ),
            'description': (
                'Required when provider = Plivo. Empty Auth ID/Token = Plivo disabled. '
                'After saving Auth ID/Token, use “Fetch SMS numbers from Plivo” below. '
                'WhatsApp From must be pasted from Plivo Console → WhatsApp (WABA number).'
            ),
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
        }),
    )

    def has_add_permission(self, request):
        return not MessagingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/fetch-plivo-sms-from/',
                self.admin_site.admin_view(self.fetch_plivo_sms_from_view),
                name='communication_messagingsettings_fetch_plivo_sms',
            ),
        ]
        return custom + urls

    def fetch_plivo_sms_from_view(self, request, object_id):
        from communication.providers import plivo as plivo_provider

        obj = self.get_object(request, object_id) or MessagingSettings.load()
        # Prefer posted/saved credentials from DB
        if request.method == 'POST':
            # Allow using freshly typed keys from the change form if posted
            auth_id = (request.POST.get('plivo_auth_id') or obj.plivo_auth_id or '').strip()
            auth_token = (request.POST.get('plivo_auth_token') or obj.plivo_auth_token or '').strip()
            if auth_id:
                obj.plivo_auth_id = auth_id
            if auth_token:
                obj.plivo_auth_token = auth_token

        result = plivo_provider.list_account_numbers(
            config=obj.provider_config_for('plivo'),
            services='sms',
        )
        change_url = reverse('admin:communication_messagingsettings_change', args=[obj.pk])

        if not result.get('success'):
            messages.error(request, f"Could not fetch Plivo numbers: {result.get('error') or 'unknown error'}")
            return HttpResponseRedirect(change_url)

        numbers = result.get('numbers') or []
        if not numbers:
            messages.warning(
                request,
                'No SMS-capable numbers found on this Plivo account. '
                'Buy/enable a number in Plivo Console → Phone Numbers, or enter an alphanumeric sender ID manually.',
            )
            return HttpResponseRedirect(change_url)

        # Prefer filling empty field; if already set, still report options
        chosen = numbers[0]['number']
        listing = ', '.join(
            f"{n['number']}" + (f" ({n['alias']})" if n.get('alias') else '')
            for n in numbers[:10]
        )
        if not obj.plivo_sms_from.strip():
            obj.plivo_sms_from = chosen
            obj.save(update_fields=['plivo_sms_from', 'updated_at'])
            messages.success(
                request,
                f'Plivo SMS From set to {chosen}. Account SMS numbers: {listing}',
            )
        else:
            messages.info(
                request,
                f'Plivo SMS From is already “{obj.plivo_sms_from}”. '
                f'Account SMS numbers (copy one if needed): {listing}',
            )
        if len(numbers) > 1:
            messages.warning(
                request,
                'Multiple SMS numbers found — confirm the correct sender is selected.',
            )
        return HttpResponseRedirect(change_url)

    def changelist_view(self, request, extra_context=None):
        obj = MessagingSettings.load()
        seed_messaging_settings_from_env(obj)
        return HttpResponseRedirect(
            reverse('admin:communication_messagingsettings_change', args=[obj.pk])
        )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id) or MessagingSettings.load()
        extra_context.update(self._banner_context(obj))
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def _banner_context(self, obj):
        if not obj.sms_enabled:
            sms_status = f'channel is {obj.get_active_channel_display()}'
        elif not obj.provider_keys_ok(obj.sms_provider, for_whatsapp=False):
            sms_status = obj.missing_keys_message(obj.sms_provider, for_whatsapp=False)
        else:
            sms_status = 'ready'
        if not obj.whatsapp_enabled:
            wa_status = f'channel is {obj.get_active_channel_display()}'
        elif not obj.provider_keys_ok(obj.whatsapp_provider, for_whatsapp=True):
            wa_status = obj.missing_keys_message(obj.whatsapp_provider, for_whatsapp=True)
        else:
            wa_status = 'ready'
        return {
            'messaging_environment': getattr(django_settings, 'ENVIRONMENT', ''),
            'messaging_debug': django_settings.DEBUG,
            'messaging_is_production': is_production_messaging_env(),
            'messaging_sms_ready': obj.is_sms_ready(),
            'messaging_wa_ready': obj.is_whatsapp_ready(),
            'messaging_sms_status': sms_status,
            'messaging_wa_status': wa_status,
        }

    @admin.display(description='Runtime status')
    def runtime_status(self, obj):
        if not obj:
            return '—'
        lines = [
            f"Env: ENVIRONMENT={getattr(django_settings, 'ENVIRONMENT', '')} DEBUG={django_settings.DEBUG}",
            f"Production messaging: {'yes' if is_production_messaging_env() else 'no'}",
            f"Sender mode: {obj.get_sender_mode_display()}",
            f"SMS ready: {'yes' if obj.is_sms_ready() else 'no'}",
            f"WhatsApp ready: {'yes' if obj.is_whatsapp_ready() else 'no'}",
        ]
        block = obj.sender_mode_block_reason()
        if block:
            lines.append(f"Block: {block}")
        return _admin_pre_block('\n'.join(lines))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.sms_enabled and not obj.provider_keys_ok(obj.sms_provider, for_whatsapp=False):
            messages.warning(
                request,
                'SMS channel selected but keys incomplete — SMS stays DISABLED until keys are added. '
                + obj.missing_keys_message(obj.sms_provider, for_whatsapp=False),
            )
        if obj.whatsapp_enabled and not obj.provider_keys_ok(obj.whatsapp_provider, for_whatsapp=True):
            messages.warning(
                request,
                'WhatsApp channel selected but keys incomplete — WhatsApp stays DISABLED until keys are added. '
                + obj.missing_keys_message(obj.whatsapp_provider, for_whatsapp=True),
            )
        if (obj.is_sms_ready() or obj.is_whatsapp_ready()) and not is_production_messaging_env() and not obj.force_send_non_production and obj.sender_mode != MessagingSettings.SENDER_MODE_TESTING:
            messages.info(
                request,
                'Keys look OK, but this is not production — real sends with production '
                'numbers stay blocked (unless Force send non-production is on, or Sender mode is Testing).',
            )
        if obj.sender_mode == MessagingSettings.SENDER_MODE_TESTING and is_production_messaging_env():
            messages.error(
                request,
                'Sender mode is Testing — SMS/WhatsApp will NOT send on this production environment. '
                'Upgrade to live Plivo numbers and set Sender mode to Production.',
            )


@admin.register(EmailMessageTemplate)
class EmailMessageTemplateAdmin(admin.ModelAdmin):
    form = EmailMessageTemplateAdminForm
    change_form_template = 'admin/communication/emailmessagetemplate/change_form.html'
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

    def _build_preview_html(self, obj, slug, subject_template='', body_html_template=''):
        subject, html = render_admin_email_preview(slug, subject_template, body_html_template)
        preview_url = reverse(
            'admin:communication_emailmessagetemplate_preview',
            args=[obj.pk],
        )
        iframe = format_html(
            '<iframe class="email-template-live-preview-frame" srcdoc="{}" '
            'style="width:100%;min-height:560px;border:1px solid #d1d5db;border-radius:8px;background:#fff;" '
            'title="Email preview"></iframe>',
            mark_safe(html_module.escape(html, quote=True)),
        )
        return format_html(
            '<div class="email-template-live-preview-wrap" data-slug="{}" data-preview-url="{}">'
            '<p style="margin:0 0 8px;color:#111111 !important;"><strong>Subject:</strong> {}</p>'
            '<p class="help" style="margin:0 0 12px;color:#444444 !important;">'
            'Full email with shared header/footer from <code>mail/base_email.html</code>. '
            'Sample placeholder values are used.</p>'
            '<button type="button" class="button email-template-preview-refresh" '
            'style="margin-bottom:12px;">Refresh preview from fields above</button>'
            '{}'
            '</div>',
            escape(slug),
            escape(preview_url),
            escape(subject),
            iframe,
        )

    @admin.display(description='Live email preview')
    def email_live_preview(self, obj):
        if not obj or not obj.slug:
            return mark_safe('<p class="help">Save the template to see a live preview.</p>')
        return self._build_preview_html(obj, obj.slug, obj.subject_template, obj.body_html_template)

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
                'description': (
                    'Preview updates automatically as you edit the subject or body above '
                    '(or use Refresh preview). Shows the final email with header, logo, and footer.'
                ),
            }),
            ('Timestamps', {
                'fields': ('created', 'modified'),
            }),
        )


admin.site.register(OTP)
admin.site.register(CommunicationLog, CommunicationLogAdmin)
