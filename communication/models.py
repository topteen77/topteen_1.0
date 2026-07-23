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


class MessagingSettings(models.Model):
    """
    Singleton: SMS + WhatsApp (admin-managed).

    ENVIRONMENT / DEBUG stay in .env (shown read-only in admin).
    Only one of SMS or WhatsApp can be active.
    If provider API keys are empty, that service is treated as disabled.
    """

    CHANNEL_DISABLED = ''
    CHANNEL_SMS = 'sms'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_CHOICES = (
        (CHANNEL_DISABLED, 'Disabled (no SMS / WhatsApp sends)'),
        (CHANNEL_SMS, 'SMS only'),
        (CHANNEL_WHATSAPP, 'WhatsApp only'),
    )

    active_channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_DISABLED,
        help_text='Only one of SMS or WhatsApp can be enabled at a time.',
    )
    sms_provider = models.CharField(
        max_length=40,
        default='smartping',
        help_text='Plug-and-play SMS provider (smartping, plivo, …).',
    )
    whatsapp_provider = models.CharField(
        max_length=40,
        default='plivo',
        help_text='Plug-and-play WhatsApp provider (plivo, …).',
    )
    force_send_non_production = models.BooleanField(
        default=False,
        help_text=(
            'Allow real sends outside production (DEBUG / non-production) when using '
            'production sender numbers. Leave off except for short tests.'
        ),
    )
    SENDER_MODE_PRODUCTION = 'production'
    SENDER_MODE_TESTING = 'testing'
    SENDER_MODE_CHOICES = (
<<<<<<< HEAD
        (SENDER_MODE_PRODUCTION, 'Production numbers (live customer traffic)'),
        (SENDER_MODE_TESTING, 'Testing / trial / sandbox numbers only'),
=======
        (SENDER_MODE_PRODUCTION, 'Production (live From numbers + optional Test button)'),
        (SENDER_MODE_TESTING, 'Sandbox / testing only (test button only; blocked on production app)'),
>>>>>>> institutedashboard
    )
    sender_mode = models.CharField(
        max_length=20,
        choices=SENDER_MODE_CHOICES,
        default=SENDER_MODE_PRODUCTION,
        help_text=(
<<<<<<< HEAD
            'Testing numbers (Plivo trial/sandbox, etc.) MUST NOT be used on production. '
            'If set to Testing, sends are blocked when ENVIRONMENT=production and DEBUG=False.'
=======
            'Step 3a: Production = save + Test button (needs From number). '
            'Sandbox = testing button only. Auto-switches to Sandbox when Step 4 finds no From number. '
            'Sandbox is blocked when ENVIRONMENT=production and DEBUG=False.'
        ),
    )
    test_destination = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text=(
            'E.164 phone for admin Test / Sandbox sends (e.g. +9198…). '
            'Plivo sandbox often requires a verified destination number.'
>>>>>>> institutedashboard
        ),
    )

    sms_message_template = models.CharField(
        max_length=500,
        default='{otp} is your verification code for TopTeen',
<<<<<<< HEAD
        help_text='SMS body. Use {otp}. Must match DLT-approved text for India.',
=======
        help_text=(
            'SMS ONLY. Body text with {otp}. Must match DLT-approved SMS text for India. '
            'Not used for WhatsApp.'
        ),
>>>>>>> institutedashboard
    )
    whatsapp_otp_template = models.CharField(
        max_length=200,
        blank=True,
<<<<<<< HEAD
        default='login_otp_verification',
        help_text='Approved WhatsApp auth template name (e.g. login_otp_verification).',
=======
        default='',
        help_text=(
            'WhatsApp Meta/Plivo template name only (e.g. login_otp_verification). '
            'Message body is NOT edited here — it comes from the approved provider template. '
            'Use “Fetch WhatsApp templates from Plivo”.'
        ),
>>>>>>> institutedashboard
    )
    whatsapp_otp_template_lang = models.CharField(
        max_length=20,
        blank=True,
        default='en',
<<<<<<< HEAD
        help_text='Language code exactly as in Plivo/Meta (en or en_US).',
=======
        help_text='Language from the provider template (en / en_US). Filled by fetch.',
    )
    whatsapp_otp_template_status = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='Last fetched Meta status (APPROVED, PENDING, DRAFT, …).',
    )
    whatsapp_otp_template_preview = models.TextField(
        blank=True,
        default='',
        help_text='Read-only preview of the approved template body from Plivo ({{1}} = OTP).',
    )
    plivo_waba_id = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text=(
            'WhatsApp Business Account ID from Plivo Console → WhatsApp. '
            'Required to fetch templates from Plivo.'
        ),
>>>>>>> institutedashboard
    )

    # SmartPing keys
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

    # Plivo keys
    plivo_auth_id = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Required for Plivo. Empty = Plivo disabled.',
    )
    plivo_auth_token = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Required for Plivo. Empty = Plivo disabled.',
    )
    plivo_sms_from = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text=(
            'SMS sender: Plivo number (E.164) or alphanumeric sender ID. '
            'Use “Fetch SMS numbers from Plivo” in admin after saving Auth ID/Token, '
            'or copy from Plivo Console → Phone Numbers.'
        ),
    )
    plivo_whatsapp_from = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text=(
            'WhatsApp sender: WABA-linked number in E.164 (+91…). '
            'Not auto-listed by API — copy from Plivo Console → WhatsApp → your business account.'
        ),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'SMS & WhatsApp settings'
        verbose_name_plural = 'SMS & WhatsApp settings'

    def __str__(self):
        return 'SMS & WhatsApp settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        if self.active_channel not in (
            self.CHANNEL_DISABLED,
            self.CHANNEL_SMS,
            self.CHANNEL_WHATSAPP,
        ):
            self.active_channel = self.CHANNEL_DISABLED
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def sms_enabled(self):
        return self.active_channel == self.CHANNEL_SMS

    @property
    def whatsapp_enabled(self):
        return self.active_channel == self.CHANNEL_WHATSAPP

    def provider_keys_ok(self, provider_key: str, *, for_whatsapp: bool = False) -> bool:
        """True only when required API keys for that provider are present."""
        key = (provider_key or '').strip().lower()
        if key == 'smartping':
            return bool(self.smartping_username.strip() and self.smartping_password.strip())
        if key == 'plivo':
            if not (self.plivo_auth_id.strip() and self.plivo_auth_token.strip()):
                return False
<<<<<<< HEAD
            if for_whatsapp:
                return bool(self.plivo_whatsapp_from.strip() and self.whatsapp_otp_template.strip())
            return bool(self.plivo_sms_from.strip())
        # Unknown provider: treat as not configured
        return False

=======
            sandbox = self.sender_mode == self.SENDER_MODE_TESTING
            if for_whatsapp:
                if not self.whatsapp_otp_template.strip():
                    return False
                # Sandbox may have no owned From yet — admin Test still needs a paste later.
                return sandbox or bool(self.plivo_whatsapp_from.strip())
            return sandbox or bool(self.plivo_sms_from.strip())
        # Unknown provider: treat as not configured
        return False

    def whatsapp_template_is_approved(self) -> bool:
        status = (self.whatsapp_otp_template_status or '').strip().upper()
        return status == 'APPROVED'

>>>>>>> institutedashboard
    def missing_keys_message(self, provider_key: str, *, for_whatsapp: bool = False) -> str:
        key = (provider_key or '').strip().lower()
        if key == 'smartping':
            missing = []
            if not self.smartping_username.strip():
                missing.append('SmartPing username')
            if not self.smartping_password.strip():
                missing.append('SmartPing password')
            return 'Missing: ' + ', '.join(missing) if missing else ''
        if key == 'plivo':
            missing = []
            if not self.plivo_auth_id.strip():
                missing.append('Plivo Auth ID')
            if not self.plivo_auth_token.strip():
                missing.append('Plivo Auth Token')
<<<<<<< HEAD
            if for_whatsapp:
                if not self.plivo_whatsapp_from.strip():
                    missing.append('Plivo WhatsApp From')
                if not self.whatsapp_otp_template.strip():
                    missing.append('WhatsApp OTP template name')
            elif not self.plivo_sms_from.strip():
=======
            sandbox = self.sender_mode == self.SENDER_MODE_TESTING
            if for_whatsapp:
                if not self.whatsapp_otp_template.strip():
                    missing.append('WhatsApp OTP template name')
                if not sandbox and not self.plivo_whatsapp_from.strip():
                    missing.append('Plivo WhatsApp From')
            elif not sandbox and not self.plivo_sms_from.strip():
>>>>>>> institutedashboard
                missing.append('Plivo SMS From')
            return 'Missing: ' + ', '.join(missing) if missing else ''
        return f'Unknown provider {key!r}'

    def is_sms_ready(self) -> bool:
        if not (self.sms_enabled and self.provider_keys_ok(self.sms_provider, for_whatsapp=False)):
            return False
        return self.sender_allowed_in_current_env()

    def is_whatsapp_ready(self) -> bool:
        if not (
            self.whatsapp_enabled
            and self.provider_keys_ok(self.whatsapp_provider, for_whatsapp=True)
        ):
            return False
<<<<<<< HEAD
=======
        if not self.whatsapp_template_is_approved():
            return False
>>>>>>> institutedashboard
        return self.sender_allowed_in_current_env()

    def sender_allowed_in_current_env(self) -> bool:
        """Testing/sandbox senders cannot be used when the app is in production."""
        from django.conf import settings as dj_settings

        env = str(getattr(dj_settings, 'ENVIRONMENT', '') or '').strip().lower()
        is_prod = env == 'production' and not dj_settings.DEBUG
        if self.sender_mode == self.SENDER_MODE_TESTING and is_prod:
            return False
        return True

    def sender_mode_block_reason(self) -> str:
        from django.conf import settings as dj_settings

        env = str(getattr(dj_settings, 'ENVIRONMENT', '') or '').strip().lower()
        is_prod = env == 'production' and not dj_settings.DEBUG
        if self.sender_mode == self.SENDER_MODE_TESTING and is_prod:
            return (
                'Sender mode is Testing/sandbox — blocked on production '
                '(ENVIRONMENT=production, DEBUG=False). Switch Sender mode to '
                'Production numbers after upgrading Plivo / using live numbers.'
            )
        return ''


    def provider_config_for(self, provider_key: str) -> dict:
        key = (provider_key or '').strip().lower()
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
                'whatsapp_from': self.plivo_whatsapp_from,
                'whatsapp_otp_template': self.whatsapp_otp_template,
                'whatsapp_otp_template_lang': self.whatsapp_otp_template_lang,
<<<<<<< HEAD
=======
                'waba_id': self.plivo_waba_id,
>>>>>>> institutedashboard
            }
        return {}

