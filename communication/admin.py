from django.contrib import admin, messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.conf import settings as django_settings
import html as html_module

from communication.email_preview import render_admin_email_preview
from communication.email_template_registry import get_email_template_meta
from communication.forms import (
    EmailMessageTemplateAdminForm,
    SmsSettingsAdminForm,
    WhatsAppSettingsAdminForm,
)
from communication.messaging_config import (
    seed_sms_settings_from_env,
    seed_whatsapp_settings_from_env,
)
from .models import CommunicationLog, EmailMessageTemplate, OTP, SmsSettings, WhatsAppSettings
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


@admin.register(SmsSettings)
class SmsSettingsAdmin(admin.ModelAdmin):
    """Independent SMS: provider, credentials, From, sandbox test, enable/disable."""

    form = SmsSettingsAdminForm
    change_form_template = 'admin/communication/smssettings/change_form.html'
    list_display = ('is_enabled', 'provider', 'updated_at')
    readonly_fields = ('updated_at', 'runtime_status')

    fieldsets = (
        ('Enable / disable', {
            'fields': ('is_enabled', 'runtime_status'),
            'description': 'Turn on only when ready for live SMS OTP. Sandbox test works without this.',
        }),
        ('Provider + API keys', {
            'fields': (
                'provider',
                'plivo_auth_id',
                'plivo_auth_token',
                'smartping_api_url',
                'smartping_username',
                'smartping_password',
                'smartping_from',
                'smartping_dlt_content_id',
                'smartping_dlt_principal_entity_id',
                'smartping_unicode',
            ),
        }),
        ('Template + From', {
            'fields': ('message_template', 'plivo_sms_from'),
            'description': 'For Plivo: save keys, then Fetch SMS From numbers. SmartPing uses SmartPing From above.',
        }),
        ('Sandbox test', {
            'fields': ('test_destination',),
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
        }),
    )

    def has_add_permission(self, request):
        return not SmsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/fetch-plivo-sms-from/',
                self.admin_site.admin_view(self.fetch_plivo_sms_from_view),
                name='communication_smssettings_fetch_plivo_sms',
            ),
            path(
                '<path:object_id>/send-test/',
                self.admin_site.admin_view(self.send_test_view),
                name='communication_smssettings_send_test',
            ),
        ]
        return custom + urls

    def fetch_plivo_sms_from_view(self, request, object_id):
        from communication.providers import plivo as plivo_provider

        obj = self.get_object(request, object_id) or SmsSettings.load()
        change_url = reverse('admin:communication_smssettings_change', args=[obj.pk])
        if request.method == 'POST':
            for field in ('plivo_auth_id', 'plivo_auth_token'):
                val = (request.POST.get(field) or '').strip()
                if val:
                    setattr(obj, field, val)

        if (obj.provider or '').strip().lower() != 'plivo':
            messages.error(request, 'Set provider to Plivo to fetch SMS numbers.')
            return HttpResponseRedirect(change_url)

        result = plivo_provider.list_account_numbers(
            config=obj.provider_config(),
            services='sms',
        )
        if not result.get('success'):
            messages.error(request, f"Could not fetch Plivo numbers: {result.get('error') or 'unknown'}")
            return HttpResponseRedirect(change_url)

        numbers = result.get('numbers') or []
        if not numbers:
            messages.warning(
                request,
                'No SMS-capable numbers on this Plivo account. Buy/enable a number or enter From manually.',
            )
            return HttpResponseRedirect(change_url)

        chosen = numbers[0]['number']
        listing = ', '.join(
            f"{n['number']}" + (f" ({n['alias']})" if n.get('alias') else '')
            for n in numbers[:10]
        )
        if not obj.plivo_sms_from.strip():
            obj.plivo_sms_from = chosen
            obj.save(update_fields=['plivo_sms_from', 'plivo_auth_id', 'plivo_auth_token', 'updated_at'])
            messages.success(request, f'SMS From set to {chosen}. Numbers: {listing}')
        else:
            messages.info(request, f'SMS From already “{obj.plivo_sms_from}”. Account numbers: {listing}')
        return HttpResponseRedirect(change_url)

    def send_test_view(self, request, object_id):
        from communication.com_service import ComService

        obj = self.get_object(request, object_id) or SmsSettings.load()
        change_url = reverse('admin:communication_smssettings_change', args=[obj.pk])
        if request.method != 'POST':
            return HttpResponseRedirect(change_url)

        dest = (request.POST.get('test_destination') or obj.test_destination or '').strip()
        if dest and dest != (obj.test_destination or '').strip():
            obj.test_destination = dest
            obj.save(update_fields=['test_destination', 'updated_at'])
        if not dest:
            messages.error(request, 'Enter a sandbox test destination phone (E.164).')
            return HttpResponseRedirect(change_url)

        result = ComService().send_admin_test_otp(dest, channel='sms')
        if result.get('success'):
            messages.success(request, f'SMS sandbox test OK to {dest}. {result.get("detail") or ""}')
        else:
            messages.error(request, f'SMS sandbox test failed: {result.get("error") or "unknown"}')
        return HttpResponseRedirect(change_url)

    def changelist_view(self, request, extra_context=None):
        obj = SmsSettings.load()
        seed_sms_settings_from_env(obj)
        return HttpResponseRedirect(reverse('admin:communication_smssettings_change', args=[obj.pk]))

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id) or SmsSettings.load()
        extra_context.update({
            'messaging_environment': getattr(django_settings, 'ENVIRONMENT', ''),
            'messaging_debug': django_settings.DEBUG,
            'sms_is_ready': obj.is_ready(),
            'sms_config_ok': obj.config_ready_for_test(),
            'sms_status': (
                'ready for live sends' if obj.is_ready()
                else ('config OK — enable for live' if obj.config_ready_for_test()
                      else (obj.missing_config_message() or 'incomplete'))
            ),
        })
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    @admin.display(description='Runtime status')
    def runtime_status(self, obj):
        if not obj:
            return '—'
        lines = [
            f"Env: ENVIRONMENT={getattr(django_settings, 'ENVIRONMENT', '')} DEBUG={django_settings.DEBUG}",
            f"Enabled: {'yes' if obj.is_enabled else 'no'}",
            f"Provider: {obj.provider}",
            f"Config for test: {'yes' if obj.config_ready_for_test() else 'no'}",
            f"Live ready: {'yes' if obj.is_ready() else 'no'}",
        ]
        if not obj.is_ready():
            lines.append(obj.missing_config_message() or '')
        return _admin_pre_block('\n'.join(lines))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.is_enabled and not obj.is_ready():
            messages.warning(
                request,
                'SMS enabled but not ready — ' + (obj.missing_config_message() or 'complete configuration'),
            )


@admin.register(WhatsAppSettings)
class WhatsAppSettingsAdmin(admin.ModelAdmin):
    """Independent WhatsApp: provider, credentials, templates, sandbox test, enable/disable."""

    form = WhatsAppSettingsAdminForm
    change_form_template = 'admin/communication/whatsappsettings/change_form.html'
    list_display = ('is_enabled', 'provider', 'otp_template', 'otp_template_status', 'updated_at')
    readonly_fields = ('updated_at', 'runtime_status', 'otp_template_status', 'otp_template_preview')

    fieldsets = (
        ('Enable / disable', {
            'fields': ('is_enabled', 'runtime_status'),
            'description': 'Turn on only when ready for live WhatsApp OTP. Sandbox test works without this.',
        }),
        ('Provider + API keys', {
            'fields': ('provider', 'plivo_auth_id', 'plivo_auth_token', 'waba_id'),
        }),
        ('Approved template + From', {
            'fields': (
                'otp_template',
                'otp_template_lang',
                'otp_template_status',
                'otp_template_preview',
                'whatsapp_from',
            ),
            'description': 'Fetch APPROVED templates from Plivo. Paste WhatsApp From from Plivo Console.',
        }),
        ('Sandbox test', {
            'fields': ('test_destination',),
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
        }),
    )

    def has_add_permission(self, request):
        return not WhatsAppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/fetch-plivo-whatsapp-templates/',
                self.admin_site.admin_view(self.fetch_plivo_whatsapp_templates_view),
                name='communication_whatsappsettings_fetch_plivo_wa',
            ),
            path(
                '<path:object_id>/send-test/',
                self.admin_site.admin_view(self.send_test_view),
                name='communication_whatsappsettings_send_test',
            ),
        ]
        return custom + urls

    def fetch_plivo_whatsapp_templates_view(self, request, object_id):
        from communication.providers import plivo as plivo_provider

        obj = self.get_object(request, object_id) or WhatsAppSettings.load()
        change_url = reverse('admin:communication_whatsappsettings_change', args=[obj.pk])

        if (obj.provider or '').strip().lower() != 'plivo':
            messages.error(request, 'Set provider to Plivo to fetch WhatsApp templates.')
            return HttpResponseRedirect(change_url)

        if request.method == 'POST':
            for field in ('plivo_auth_id', 'plivo_auth_token', 'waba_id'):
                val = (request.POST.get(field) or '').strip()
                if val:
                    setattr(obj, field, val)

        waba_id = (obj.waba_id or '').strip()
        if not waba_id:
            messages.error(request, 'Set WABA ID first, save, then fetch templates.')
            return HttpResponseRedirect(change_url)

        preferred = (request.POST.get('otp_template') or obj.otp_template or 'login_otp_verification').strip()
        listed = plivo_provider.list_whatsapp_templates(
            waba_id=waba_id,
            config=obj.provider_config(),
            name=preferred or None,
            limit=20,
        )
        if not listed.get('success'):
            listed = plivo_provider.list_whatsapp_templates(
                waba_id=waba_id,
                config=obj.provider_config(),
                limit=20,
            )
        if not listed.get('success'):
            messages.error(request, f"Could not fetch WhatsApp templates: {listed.get('error')}")
            return HttpResponseRedirect(change_url)

        templates = listed.get('templates') or []
        if not templates:
            messages.warning(request, 'No WhatsApp templates returned from Plivo.')
            return HttpResponseRedirect(change_url)

        def score(t):
            s = 0
            if (t.get('name') or '') == preferred:
                s += 100
            if (t.get('status') or '') == 'APPROVED':
                s += 50
            if (t.get('category') or '') == 'AUTHENTICATION':
                s += 20
            return s

        templates_sorted = sorted(templates, key=score, reverse=True)
        chosen = templates_sorted[0]
        detail = plivo_provider.get_whatsapp_template(
            waba_id=waba_id,
            template_id=chosen.get('template_id') or '',
            config=obj.provider_config(),
        )

        obj.otp_template = chosen.get('name') or preferred
        obj.otp_template_lang = (
            (detail.get('language') if detail.get('success') else None)
            or chosen.get('language')
            or obj.otp_template_lang
            or 'en'
        )
        obj.otp_template_status = (
            (detail.get('status') if detail.get('success') else None)
            or chosen.get('status')
            or ''
        )
        if detail.get('success') and detail.get('preview'):
            obj.otp_template_preview = detail['preview']
        elif not obj.otp_template_preview:
            obj.otp_template_preview = (
                '{{1}} is your verification code. For your security, do not share this code.'
            )
        obj.save(update_fields=[
            'otp_template',
            'otp_template_lang',
            'otp_template_status',
            'otp_template_preview',
            'waba_id',
            'plivo_auth_id',
            'plivo_auth_token',
            'updated_at',
        ])

        summary = ', '.join(
            f"{t.get('name')} [{t.get('status')}/{t.get('category')}/{t.get('language')}]"
            for t in templates_sorted[:8]
        )
        if obj.otp_template_status == 'APPROVED':
            messages.success(
                request,
                f'Template set: {obj.otp_template} ({obj.otp_template_lang}, APPROVED). Available: {summary}',
            )
        else:
            messages.warning(
                request,
                f'Template “{obj.otp_template}” status is {obj.otp_template_status or "unknown"} '
                f'(need APPROVED). Available: {summary}',
            )
        return HttpResponseRedirect(change_url)

    def send_test_view(self, request, object_id):
        from communication.com_service import ComService

        obj = self.get_object(request, object_id) or WhatsAppSettings.load()
        change_url = reverse('admin:communication_whatsappsettings_change', args=[obj.pk])
        if request.method != 'POST':
            return HttpResponseRedirect(change_url)

        dest = (request.POST.get('test_destination') or obj.test_destination or '').strip()
        if dest and dest != (obj.test_destination or '').strip():
            obj.test_destination = dest
            obj.save(update_fields=['test_destination', 'updated_at'])
        if not dest:
            messages.error(request, 'Enter a sandbox test destination phone (E.164).')
            return HttpResponseRedirect(change_url)

        result = ComService().send_admin_test_otp(dest, channel='whatsapp')
        if result.get('success'):
            messages.success(request, f'WhatsApp sandbox test OK to {dest}. {result.get("detail") or ""}')
        else:
            messages.error(request, f'WhatsApp sandbox test failed: {result.get("error") or "unknown"}')
        return HttpResponseRedirect(change_url)

    def changelist_view(self, request, extra_context=None):
        obj = WhatsAppSettings.load()
        seed_whatsapp_settings_from_env(obj)
        return HttpResponseRedirect(reverse('admin:communication_whatsappsettings_change', args=[obj.pk]))

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id) or WhatsAppSettings.load()
        extra_context.update({
            'messaging_environment': getattr(django_settings, 'ENVIRONMENT', ''),
            'messaging_debug': django_settings.DEBUG,
            'wa_is_ready': obj.is_ready(),
            'wa_config_ok': obj.config_ready_for_test(),
            'wa_status': (
                'ready for live sends' if obj.is_ready()
                else ('config OK — enable for live' if obj.config_ready_for_test()
                      else (obj.missing_config_message() or 'incomplete'))
            ),
        })
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    @admin.display(description='Runtime status')
    def runtime_status(self, obj):
        if not obj:
            return '—'
        lines = [
            f"Env: ENVIRONMENT={getattr(django_settings, 'ENVIRONMENT', '')} DEBUG={django_settings.DEBUG}",
            f"Enabled: {'yes' if obj.is_enabled else 'no'}",
            f"Provider: {obj.provider}",
            f"Template: {obj.otp_template or '—'} [{obj.otp_template_status or '?'}]",
            f"Config for test: {'yes' if obj.config_ready_for_test() else 'no'}",
            f"Live ready: {'yes' if obj.is_ready() else 'no'}",
        ]
        if not obj.is_ready():
            lines.append(obj.missing_config_message() or '')
        return _admin_pre_block('\n'.join(lines))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.is_enabled and not obj.is_ready():
            messages.warning(
                request,
                'WhatsApp enabled but not ready — ' + (obj.missing_config_message() or 'complete configuration'),
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
