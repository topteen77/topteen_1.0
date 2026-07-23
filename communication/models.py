from django.db import models
from django.conf import settings
from core import choices
# Create your models here.

class CommunicationLog(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    to  = models.CharField(max_length=500)
    body = models.TextField()
    response = models.TextField()
    type =  models.PositiveSmallIntegerField(choices=choices.CommunicationTypeChooices.CHOICES, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['type', '-created'])]

    def __str__(self):
        return "{} ({})".format(self.to,self.get_type_display())

class EmailMessageTemplate(models.Model):
    """
    Admin-editable subject/body for transactional emails.

    Use Python ``str.format`` placeholders, e.g. ``{inviter_name}``, ``{referral_url}``.
    Leave subject/body empty to use the built-in default from code.
    """

    slug = models.CharField(max_length=120, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    subject_template = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=(
            'Email subject line. Leave empty to use the built-in default. '
            'Use {placeholder} style placeholders — see Instructions in admin.'
        ),
    )
    body_html_template = models.TextField(
        blank=True,
        default='',
        help_text=(
            'Full HTML email body. Leave empty to use the built-in default file. '
            'Use the same placeholders as the subject. See admin instructions above the fields.'
        ),
    )
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('slug',)
        verbose_name = 'Email message template'
        verbose_name_plural = 'Email message templates'

    def __str__(self):
        return self.name or self.slug


class OTP(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    user  = models.CharField(max_length=500, db_index=True)
    otp = models.CharField(max_length=10)
    type =  models.PositiveSmallIntegerField(choices=choices.CommunicationTypeChooices.CHOICES, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'type', '-created'])]

    def __str__(self):
        return "{} ({}) : ".format(self.user, self.get_type_display(), self.otp)


class SmsSettings(models.Model):
    """Singleton: SMS provider, credentials, template, sandbox test, enable/disable."""

    is_enabled = models.BooleanField(
        default=False,
        help_text='When on, live SMS OTP can send (also needs credentials + From).',
    )
    provider = models.CharField(
        max_length=40,
        default='smartping',
        help_text='SMS provider (smartping, plivo, …).',
    )
    message_template = models.CharField(
        max_length=500,
        default='{otp} is your verification code for TopTeen',
        help_text='SMS body with {otp}. Must match DLT-approved text for India.',
    )
    test_destination = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='E.164 phone for admin sandbox test (e.g. +9198…).',
    )

    smartping_api_url = models.URLField(
        max_length=500,
        blank=True,
        default='https://pgapi.smartping.ai/fe/api/v1/send',
    )
    smartping_username = models.CharField(max_length=120, blank=True, default='')
    smartping_password = models.CharField(max_length=120, blank=True, default='')
    smartping_from = models.CharField(max_length=40, blank=True, default='')
    smartping_dlt_content_id = models.CharField(max_length=64, blank=True, default='')
    smartping_dlt_principal_entity_id = models.CharField(max_length=64, blank=True, default='')
    smartping_unicode = models.CharField(max_length=10, blank=True, default='false')

    plivo_auth_id = models.CharField(max_length=120, blank=True, default='')
    plivo_auth_token = models.CharField(max_length=120, blank=True, default='')
    plivo_sms_from = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='Plivo SMS From (E.164 or alphanumeric). Use Fetch numbers after saving keys.',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'SMS settings'
        verbose_name_plural = 'SMS settings'

    def __str__(self):
        return 'SMS settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def credentials_ok(self) -> bool:
        key = (self.provider or '').strip().lower()
        if key == 'smartping':
            return bool(self.smartping_username.strip() and self.smartping_password.strip())
        if key == 'plivo':
            return bool(self.plivo_auth_id.strip() and self.plivo_auth_token.strip())
        return False

    def has_from_number(self) -> bool:
        key = (self.provider or '').strip().lower()
        if key == 'smartping':
            return bool(self.smartping_from.strip())
        if key == 'plivo':
            return bool(self.plivo_sms_from.strip())
        return False

    def config_ready_for_test(self) -> bool:
        """Sandbox test: credentials + From (no is_enabled)."""
        if not self.credentials_ok():
            return False
        return self.has_from_number()

    def is_ready(self) -> bool:
        """Live sends: enabled + credentials + From + message template."""
        if not self.is_enabled:
            return False
        if not self.credentials_ok() or not self.has_from_number():
            return False
        tmpl = (self.message_template or '').strip()
        return bool(tmpl and '{otp}' in tmpl)

    def missing_config_message(self) -> str:
        missing = []
        key = (self.provider or '').strip().lower()
        if key == 'smartping':
            if not self.smartping_username.strip():
                missing.append('SmartPing username')
            if not self.smartping_password.strip():
                missing.append('SmartPing password')
            if not self.smartping_from.strip():
                missing.append('SmartPing From')
        elif key == 'plivo':
            if not self.plivo_auth_id.strip():
                missing.append('Plivo Auth ID')
            if not self.plivo_auth_token.strip():
                missing.append('Plivo Auth Token')
            if not self.plivo_sms_from.strip():
                missing.append('Plivo SMS From')
        else:
            return f'Unknown provider {key!r}'
        tmpl = (self.message_template or '').strip()
        if not tmpl or '{otp}' not in tmpl:
            missing.append('message template with {otp}')
        return 'Missing: ' + ', '.join(missing) if missing else ''

    def provider_config(self) -> dict:
        key = (self.provider or '').strip().lower()
        if key == 'smartping':
            return {
                'api_url': self.smartping_api_url,
                'username': self.smartping_username,
                'password': self.smartping_password,
                'from_id': self.smartping_from,
                'dlt_content_id': self.smartping_dlt_content_id,
                'dlt_principal_entity_id': self.smartping_dlt_principal_entity_id,
                'unicode': self.smartping_unicode or 'false',
            }
        if key == 'plivo':
            return {
                'auth_id': self.plivo_auth_id,
                'auth_token': self.plivo_auth_token,
                'sms_from': self.plivo_sms_from,
            }
        return {}


class WhatsAppSettings(models.Model):
    """Singleton: WhatsApp provider, credentials, approved template, sandbox test, enable/disable."""

    is_enabled = models.BooleanField(
        default=False,
        help_text='When on, live WhatsApp OTP can send (also needs APPROVED template + From).',
    )
    provider = models.CharField(
        max_length=40,
        default='plivo',
        help_text='WhatsApp provider (plivo, …).',
    )
    test_destination = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='E.164 phone for admin sandbox test (e.g. +9198…).',
    )

    plivo_auth_id = models.CharField(max_length=120, blank=True, default='')
    plivo_auth_token = models.CharField(max_length=120, blank=True, default='')
    waba_id = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='WhatsApp Business Account ID (Plivo Console → WhatsApp).',
    )
    whatsapp_from = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='WABA-linked sender in E.164 (+91…). Paste from Plivo Console → WhatsApp.',
    )
    otp_template = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Meta/Plivo template name (e.g. login_otp_verification). Use Fetch templates.',
    )
    otp_template_lang = models.CharField(max_length=20, blank=True, default='en')
    otp_template_status = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='Last fetched status (must be APPROVED for live sends).',
    )
    otp_template_preview = models.TextField(
        blank=True,
        default='',
        help_text='Read-only preview from provider ({{1}} = OTP).',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'WhatsApp settings'
        verbose_name_plural = 'WhatsApp settings'

    def __str__(self):
        return 'WhatsApp settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def credentials_ok(self) -> bool:
        key = (self.provider or '').strip().lower()
        if key == 'plivo':
            return bool(self.plivo_auth_id.strip() and self.plivo_auth_token.strip())
        return False

    def template_is_approved(self) -> bool:
        return (self.otp_template_status or '').strip().upper() == 'APPROVED'

    def has_from_number(self) -> bool:
        return bool((self.whatsapp_from or '').strip())

    def config_ready_for_test(self) -> bool:
        """Sandbox test: credentials + APPROVED template + From (no is_enabled)."""
        return bool(
            self.credentials_ok()
            and (self.otp_template or '').strip()
            and self.template_is_approved()
            and self.has_from_number()
        )

    def is_ready(self) -> bool:
        return bool(self.is_enabled and self.config_ready_for_test())

    def missing_config_message(self) -> str:
        missing = []
        key = (self.provider or '').strip().lower()
        if key == 'plivo':
            if not self.plivo_auth_id.strip():
                missing.append('Plivo Auth ID')
            if not self.plivo_auth_token.strip():
                missing.append('Plivo Auth Token')
        else:
            return f'Unknown provider {key!r}'
        if not (self.otp_template or '').strip():
            missing.append('OTP template name')
        elif not self.template_is_approved():
            missing.append(f'template APPROVED (now {self.otp_template_status or "unknown"!r})')
        if not self.has_from_number():
            missing.append('WhatsApp From')
        return 'Missing: ' + ', '.join(missing) if missing else ''

    def provider_config(self) -> dict:
        key = (self.provider or '').strip().lower()
        if key == 'plivo':
            return {
                'auth_id': self.plivo_auth_id,
                'auth_token': self.plivo_auth_token,
                'whatsapp_from': self.whatsapp_from,
                'whatsapp_otp_template': self.otp_template,
                'whatsapp_otp_template_lang': self.otp_template_lang,
                'waba_id': self.waba_id,
            }
        return {}

