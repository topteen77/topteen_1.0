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
    apply_no_numbers_fallback,
    flow_steps,
    has_from_number,
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
    """Stepped setup: service → provider → template → prod/sandbox → From → send path."""

    form = MessagingSettingsAdminForm
    change_form_template = 'admin/communication/messagingsettings/change_form.html'
    list_display = ('active_channel', 'sms_provider', 'whatsapp_provider', 'sender_mode', 'updated_at')
    readonly_fields = (
        'updated_at',
        'runtime_status',
        'whatsapp_otp_template_status',
        'whatsapp_otp_template_preview',
    )

    fieldsets = (
        ('Step 1 — Select service', {
            'fields': ('active_channel', 'runtime_status'),
            'description': 'Choose SMS only or WhatsApp only (or Disabled). Only one channel can send.',
        }),
        ('Step 2 — Select provider + API keys', {
            'fields': (
                'sms_provider',
                'whatsapp_provider',
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
            'description': (
                'SMS → Sms provider (+ SmartPing or Plivo keys). '
                'WhatsApp → Whatsapp provider (+ Plivo keys). Empty keys = that service stays off.'
            ),
        }),
        ('Step 3 — Template', {
            'fields': (
                'sms_message_template',
                'plivo_waba_id',
                'whatsapp_otp_template',
                'whatsapp_otp_template_lang',
                'whatsapp_otp_template_status',
                'whatsapp_otp_template_preview',
            ),
            'description': (
                'SMS: edit body with {otp}. '
                'WhatsApp: set WABA ID, then use “Fetch approved templates” (body comes from Meta — must be APPROVED).'
            ),
        }),
        ('Step 3a — Production or Sandbox', {
            'fields': ('sender_mode', 'force_send_non_production', 'test_destination'),
            'description': (
                'Production: Save, then use Test button (live From required). '
                'Sandbox: Test button only — blocked when the app itself is production.'
            ),
        }),
        ('Step 4 — From numbers', {
            'fields': ('plivo_sms_from', 'plivo_whatsapp_from'),
            'description': (
                'Fetch SMS numbers from Plivo, or paste WhatsApp From from Plivo Console → WhatsApp. '
                'If none available, Sandbox mode is forced (Step 5).'
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
            path(
                '<path:object_id>/fetch-plivo-whatsapp-templates/',
                self.admin_site.admin_view(self.fetch_plivo_whatsapp_templates_view),
                name='communication_messagingsettings_fetch_plivo_wa',
            ),
            path(
                '<path:object_id>/send-test/',
                self.admin_site.admin_view(self.send_test_message_view),
                name='communication_messagingsettings_send_test',
            ),
        ]
        return custom + urls

    def fetch_plivo_sms_from_view(self, request, object_id):
        from communication.providers import plivo as plivo_provider

        obj = self.get_object(request, object_id) or MessagingSettings.load()
        if request.method == 'POST':
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
            apply_no_numbers_fallback(obj)
            messages.warning(
                request,
                'Step 4–5: No SMS From numbers on this Plivo account. '
                'Switched to Sandbox / testing. Use the Sandbox test button with a verified destination, '
                'or buy/enable a number in Plivo Console and fetch again.',
            )
            return HttpResponseRedirect(change_url)

        chosen = numbers[0]['number']
        listing = ', '.join(
            f"{n['number']}" + (f" ({n['alias']})" if n.get('alias') else '')
            for n in numbers[:10]
        )
        if not obj.plivo_sms_from.strip():
            obj.plivo_sms_from = chosen
            if obj.sender_mode != MessagingSettings.SENDER_MODE_PRODUCTION:
                obj.sender_mode = MessagingSettings.SENDER_MODE_PRODUCTION
                obj.save(update_fields=['plivo_sms_from', 'sender_mode', 'updated_at'])
            else:
                obj.save(update_fields=['plivo_sms_from', 'updated_at'])
            messages.success(
                request,
                f'Step 4–5: Plivo SMS From set to {chosen} (production path). Numbers: {listing}',
            )
        else:
            messages.info(
                request,
                f'Plivo SMS From is already “{obj.plivo_sms_from}”. Account SMS numbers: {listing}',
            )
        if len(numbers) > 1:
            messages.warning(
                request,
                'Multiple SMS numbers found — confirm the correct sender is selected.',
            )
        return HttpResponseRedirect(change_url)

    def fetch_plivo_whatsapp_templates_view(self, request, object_id):
        """Fetch APPROVED WhatsApp OTP templates from Plivo for the selected WA provider."""
        from communication.providers import plivo as plivo_provider

        obj = self.get_object(request, object_id) or MessagingSettings.load()
        change_url = reverse('admin:communication_messagingsettings_change', args=[obj.pk])

        if (obj.whatsapp_provider or '').strip().lower() != 'plivo':
            messages.error(
                request,
                f'WhatsApp provider is “{obj.whatsapp_provider}” — template fetch is implemented for Plivo. '
                'Set Whatsapp provider to Plivo (and Active channel to WhatsApp when sending).',
            )
            return HttpResponseRedirect(change_url)

        if request.method == 'POST':
            for field in ('plivo_auth_id', 'plivo_auth_token', 'plivo_waba_id'):
                val = (request.POST.get(field) or '').strip()
                if val:
                    setattr(obj, field, val)

        waba_id = (obj.plivo_waba_id or '').strip()
        if not waba_id:
            messages.error(
                request,
                'Step 3: Set Plivo WABA ID first (Plivo Console → WhatsApp), save, then fetch.',
            )
            return HttpResponseRedirect(change_url)

        preferred = (request.POST.get('whatsapp_otp_template') or obj.whatsapp_otp_template or 'login_otp_verification').strip()
        listed = plivo_provider.list_whatsapp_templates(
            waba_id=waba_id,
            config=obj.provider_config_for('plivo'),
            name=preferred or None,
            limit=20,
        )
        if not listed.get('success'):
            listed = plivo_provider.list_whatsapp_templates(
                waba_id=waba_id,
                config=obj.provider_config_for('plivo'),
                limit=20,
            )
        if not listed.get('success'):
            messages.error(request, f"Could not fetch WhatsApp templates: {listed.get('error')}")
            return HttpResponseRedirect(change_url)

        templates = listed.get('templates') or []
        if not templates:
            messages.warning(
                request,
                'No WhatsApp templates returned. Sync/approve templates in Plivo Console → WhatsApp → Templates.',
            )
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
            config=obj.provider_config_for('plivo'),
        )

        obj.whatsapp_otp_template = chosen.get('name') or preferred
        obj.whatsapp_otp_template_lang = (
            (detail.get('language') if detail.get('success') else None)
            or chosen.get('language')
            or obj.whatsapp_otp_template_lang
            or 'en'
        )
        obj.whatsapp_otp_template_status = (
            (detail.get('status') if detail.get('success') else None)
            or chosen.get('status')
            or ''
        )
        if detail.get('success') and detail.get('preview'):
            obj.whatsapp_otp_template_preview = detail['preview']
        elif not obj.whatsapp_otp_template_preview:
            obj.whatsapp_otp_template_preview = (
                '{{1}} is your verification code. For your security, do not share this code.'
            )
        obj.save(update_fields=[
            'whatsapp_otp_template',
            'whatsapp_otp_template_lang',
            'whatsapp_otp_template_status',
            'whatsapp_otp_template_preview',
            'plivo_waba_id',
            'plivo_auth_id',
            'plivo_auth_token',
            'updated_at',
        ])

        summary = ', '.join(
            f"{t.get('name')} [{t.get('status')}/{t.get('category')}/{t.get('language')}]"
            for t in templates_sorted[:8]
        )
        if obj.whatsapp_otp_template_status == 'APPROVED':
            messages.success(
                request,
                f'Step 3 OK: WhatsApp template {obj.whatsapp_otp_template} '
                f'({obj.whatsapp_otp_template_lang}, APPROVED). Available: {summary}',
            )
        else:
            messages.warning(
                request,
                f'Step 3 incomplete: “{obj.whatsapp_otp_template}” status is '
                f'{obj.whatsapp_otp_template_status or "unknown"} (need APPROVED). '
                f'Send for Verification in Plivo/Meta, then fetch again. Available: {summary}',
            )

        # Step 4 hint for WhatsApp From
        if not (obj.plivo_whatsapp_from or '').strip():
            apply_no_numbers_fallback(obj)
            messages.warning(
                request,
                'Step 4–5: No WhatsApp From set. Switched to Sandbox. '
                'Paste the WABA number from Plivo Console → WhatsApp, then switch to Production when ready.',
            )
        return HttpResponseRedirect(change_url)

    def send_test_message_view(self, request, object_id):
        """Admin Test / Sandbox send for the active channel."""
        from communication.com_service import ComService

        obj = self.get_object(request, object_id) or MessagingSettings.load()
        change_url = reverse('admin:communication_messagingsettings_change', args=[obj.pk])

        if request.method != 'POST':
            return HttpResponseRedirect(change_url)

        # Persist destination if posted
        dest = (request.POST.get('test_destination') or obj.test_destination or '').strip()
        if dest and dest != (obj.test_destination or '').strip():
            obj.test_destination = dest
            obj.save(update_fields=['test_destination', 'updated_at'])

        if not dest:
            messages.error(request, 'Enter a Test destination phone (E.164) in Step 3a, then try again.')
            return HttpResponseRedirect(change_url)

        if obj.active_channel not in (MessagingSettings.CHANNEL_SMS, MessagingSettings.CHANNEL_WHATSAPP):
            messages.error(request, 'Step 1: Select SMS or WhatsApp before sending a test.')
            return HttpResponseRedirect(change_url)

        if obj.sender_mode == MessagingSettings.SENDER_MODE_TESTING and is_production_messaging_env():
            messages.error(
                request,
                'Sandbox mode is blocked on production app (ENVIRONMENT=production, DEBUG=False). '
                'Use Production mode with a live From number.',
            )
            return HttpResponseRedirect(change_url)

        if obj.sender_mode == MessagingSettings.SENDER_MODE_PRODUCTION and not has_from_number(obj):
            apply_no_numbers_fallback(obj)
            messages.error(
                request,
                'No From number for Production. Switched to Sandbox — set a From number or use Sandbox test.',
            )
            return HttpResponseRedirect(change_url)

        result = ComService().send_admin_test_otp(dest, cfg=obj)
        if result.get('success'):
            mode_label = 'Sandbox' if obj.sender_mode == MessagingSettings.SENDER_MODE_TESTING else 'Production test'
            messages.success(
                request,
                f'{mode_label} send OK to {dest} via {obj.active_channel}. '
                f"Detail: {result.get('detail') or 'sent'}",
            )
        else:
            messages.error(
                request,
                f"Test send failed: {result.get('error') or 'unknown error'}",
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
        elif not obj.whatsapp_template_is_approved():
            wa_status = (
                f'template {obj.whatsapp_otp_template!r} status '
                f'{obj.whatsapp_otp_template_status or "unknown"!r} (need APPROVED)'
            )
        else:
            wa_status = 'ready'
        steps = flow_steps(obj)
        return {
            'messaging_environment': getattr(django_settings, 'ENVIRONMENT', ''),
            'messaging_debug': django_settings.DEBUG,
            'messaging_is_production': is_production_messaging_env(),
            'messaging_sms_ready': obj.is_sms_ready(),
            'messaging_wa_ready': obj.is_whatsapp_ready(),
            'messaging_sms_status': sms_status,
            'messaging_wa_status': wa_status,
            'messaging_flow_steps': steps,
            'messaging_has_from': has_from_number(obj),
            'messaging_show_production_test': (
                obj.sender_mode == MessagingSettings.SENDER_MODE_PRODUCTION
                and obj.active_channel in ('sms', 'whatsapp')
            ),
            'messaging_show_sandbox_test_only': (
                obj.sender_mode == MessagingSettings.SENDER_MODE_TESTING
                and obj.active_channel in ('sms', 'whatsapp')
            ),
        }

    @admin.display(description='Runtime status')
    def runtime_status(self, obj):
        if not obj:
            return '—'
        lines = [
            f"Env: ENVIRONMENT={getattr(django_settings, 'ENVIRONMENT', '')} DEBUG={django_settings.DEBUG}",
            f"Production messaging: {'yes' if is_production_messaging_env() else 'no'}",
            f"Sender mode: {obj.get_sender_mode_display()}",
            f"From number: {'yes' if has_from_number(obj) else 'no'}",
            f"SMS ready: {'yes' if obj.is_sms_ready() else 'no'}",
            f"WhatsApp ready: {'yes' if obj.is_whatsapp_ready() else 'no'}",
        ]
        block = obj.sender_mode_block_reason()
        if block:
            lines.append(f"Block: {block}")
        return _admin_pre_block('\n'.join(lines))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.sender_mode == MessagingSettings.SENDER_MODE_PRODUCTION and not has_from_number(obj):
            if apply_no_numbers_fallback(obj):
                messages.warning(
                    request,
                    'Step 5: No From number — switched to Sandbox / testing. '
                    'Fetch or paste a From number to use Production.',
                )
                obj.refresh_from_db()
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
        if (
            (obj.is_sms_ready() or obj.is_whatsapp_ready())
            and not is_production_messaging_env()
            and not obj.force_send_non_production
            and obj.sender_mode != MessagingSettings.SENDER_MODE_TESTING
        ):
            messages.info(
                request,
                'Keys look OK, but this is not production — live customer traffic with production '
                'numbers stays blocked (use Test button, Sandbox mode, or Force send non-production).',
            )
        if obj.sender_mode == MessagingSettings.SENDER_MODE_TESTING and is_production_messaging_env():
            messages.error(
                request,
                'Sandbox mode — SMS/WhatsApp will NOT send on this production environment. '
                'Set Production mode after adding live From numbers.',
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
