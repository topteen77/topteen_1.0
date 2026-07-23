# Separate SMS / WhatsApp settings; migrate data from MessagingSettings

from django.db import migrations, models


def forwards_copy_messaging_settings(apps, schema_editor):
    MessagingSettings = apps.get_model('communication', 'MessagingSettings')
    SmsSettings = apps.get_model('communication', 'SmsSettings')
    WhatsAppSettings = apps.get_model('communication', 'WhatsAppSettings')

    try:
        old = MessagingSettings.objects.filter(pk=1).first()
    except Exception:
        old = None
    if not old:
        SmsSettings.objects.get_or_create(pk=1)
        WhatsAppSettings.objects.get_or_create(pk=1)
        return

    sms_enabled = (old.active_channel or '') == 'sms'
    wa_enabled = (old.active_channel or '') == 'whatsapp'

    SmsSettings.objects.update_or_create(
        pk=1,
        defaults={
            'is_enabled': sms_enabled,
            'provider': old.sms_provider or 'smartping',
            'message_template': old.sms_message_template
            or '{otp} is your verification code for TopTeen',
            'test_destination': getattr(old, 'test_destination', '') or '',
            'smartping_api_url': old.smartping_api_url
            or 'https://pgapi.smartping.ai/fe/api/v1/send',
            'smartping_username': old.smartping_username or '',
            'smartping_password': old.smartping_password or '',
            'smartping_from': old.smartping_from or '',
            'smartping_dlt_content_id': old.smartping_dlt_content_id or '',
            'smartping_dlt_principal_entity_id': old.smartping_dlt_principal_entity_id or '',
            'smartping_unicode': old.smartping_unicode or 'false',
            'plivo_auth_id': old.plivo_auth_id or '',
            'plivo_auth_token': old.plivo_auth_token or '',
            'plivo_sms_from': old.plivo_sms_from or '',
        },
    )
    WhatsAppSettings.objects.update_or_create(
        pk=1,
        defaults={
            'is_enabled': wa_enabled,
            'provider': old.whatsapp_provider or 'plivo',
            'test_destination': getattr(old, 'test_destination', '') or '',
            'plivo_auth_id': old.plivo_auth_id or '',
            'plivo_auth_token': old.plivo_auth_token or '',
            'waba_id': old.plivo_waba_id or '',
            'whatsapp_from': old.plivo_whatsapp_from or '',
            'otp_template': old.whatsapp_otp_template or '',
            'otp_template_lang': old.whatsapp_otp_template_lang or 'en',
            'otp_template_status': old.whatsapp_otp_template_status or '',
            'otp_template_preview': old.whatsapp_otp_template_preview or '',
        },
    )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0015_messaging_test_destination_flow'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmsSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=False, help_text='When on, live SMS OTP can send (also needs credentials + From).')),
                ('provider', models.CharField(default='smartping', help_text='SMS provider (smartping, plivo, …).', max_length=40)),
                ('message_template', models.CharField(default='{otp} is your verification code for TopTeen', help_text='SMS body with {otp}. Must match DLT-approved text for India.', max_length=500)),
                ('test_destination', models.CharField(blank=True, default='', help_text='E.164 phone for admin sandbox test (e.g. +9198…).', max_length=40)),
                ('smartping_api_url', models.URLField(blank=True, default='https://pgapi.smartping.ai/fe/api/v1/send', max_length=500)),
                ('smartping_username', models.CharField(blank=True, default='', max_length=120)),
                ('smartping_password', models.CharField(blank=True, default='', max_length=120)),
                ('smartping_from', models.CharField(blank=True, default='', max_length=40)),
                ('smartping_dlt_content_id', models.CharField(blank=True, default='', max_length=64)),
                ('smartping_dlt_principal_entity_id', models.CharField(blank=True, default='', max_length=64)),
                ('smartping_unicode', models.CharField(blank=True, default='false', max_length=10)),
                ('plivo_auth_id', models.CharField(blank=True, default='', max_length=120)),
                ('plivo_auth_token', models.CharField(blank=True, default='', max_length=120)),
                ('plivo_sms_from', models.CharField(blank=True, default='', help_text='Plivo SMS From (E.164 or alphanumeric). Use Fetch numbers after saving keys.', max_length=40)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'SMS settings',
                'verbose_name_plural': 'SMS settings',
            },
        ),
        migrations.CreateModel(
            name='WhatsAppSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=False, help_text='When on, live WhatsApp OTP can send (also needs APPROVED template + From).')),
                ('provider', models.CharField(default='plivo', help_text='WhatsApp provider (plivo, …).', max_length=40)),
                ('test_destination', models.CharField(blank=True, default='', help_text='E.164 phone for admin sandbox test (e.g. +9198…).', max_length=40)),
                ('plivo_auth_id', models.CharField(blank=True, default='', max_length=120)),
                ('plivo_auth_token', models.CharField(blank=True, default='', max_length=120)),
                ('waba_id', models.CharField(blank=True, default='', help_text='WhatsApp Business Account ID (Plivo Console → WhatsApp).', max_length=120)),
                ('whatsapp_from', models.CharField(blank=True, default='', help_text='WABA-linked sender in E.164 (+91…). Paste from Plivo Console → WhatsApp.', max_length=40)),
                ('otp_template', models.CharField(blank=True, default='', help_text='Meta/Plivo template name (e.g. login_otp_verification). Use Fetch templates.', max_length=200)),
                ('otp_template_lang', models.CharField(blank=True, default='en', max_length=20)),
                ('otp_template_status', models.CharField(blank=True, default='', help_text='Last fetched status (must be APPROVED for live sends).', max_length=40)),
                ('otp_template_preview', models.TextField(blank=True, default='', help_text='Read-only preview from provider ({{1}} = OTP).')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'WhatsApp settings',
                'verbose_name_plural': 'WhatsApp settings',
            },
        ),
        migrations.RunPython(forwards_copy_messaging_settings, backwards_noop),
        migrations.DeleteModel(name='MessagingSettings'),
    ]
