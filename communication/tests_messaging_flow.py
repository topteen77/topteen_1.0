"""Tests for separate SMS / WhatsApp settings readiness and OTP routing."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from communication.models import SmsSettings, WhatsAppSettings
from communication.messaging_config import (
    _sms_live_ready,
    channel_enabled,
    skip_send_reason,
)


def _sms(**kwargs):
    obj = SmsSettings(
        pk=1,
        is_enabled=False,
        provider='plivo',
        message_template='{otp} is your code',
        plivo_auth_id='',
        plivo_auth_token='',
        plivo_sms_from='',
        smartping_username='',
        smartping_password='',
        smartping_from='',
    )
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


def _wa(**kwargs):
    obj = WhatsAppSettings(
        pk=1,
        is_enabled=False,
        provider='plivo',
        plivo_auth_id='',
        plivo_auth_token='',
        waba_id='',
        whatsapp_from='',
        otp_template='',
        otp_template_status='',
    )
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


class SmsSettingsReadyTests(SimpleTestCase):
    def test_model_not_ready_when_disabled(self):
        cfg = _sms(
            is_enabled=False,
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='+9199',
        )
        self.assertTrue(cfg.config_ready_for_test())
        self.assertFalse(cfg.is_ready())

    def test_model_ready_when_enabled_and_complete(self):
        cfg = _sms(
            is_enabled=True,
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='+9199',
            message_template='{otp} x',
        )
        self.assertTrue(cfg.is_ready())

    def test_smartping_needs_from(self):
        cfg = _sms(
            is_enabled=True,
            provider='smartping',
            smartping_username='u',
            smartping_password='p',
            smartping_from='',
        )
        self.assertFalse(cfg.is_ready())
        cfg.smartping_from = 'TOPTEEN'
        self.assertTrue(cfg.is_ready())

    @override_settings(ENVIRONMENT='production', DEBUG=False, SMS_ENABLED=False)
    def test_production_live_ready_with_credentials_even_if_disabled(self):
        cfg = _sms(
            is_enabled=False,
            provider='smartping',
            smartping_username='u',
            smartping_password='p',
            smartping_from='TOPTEEN',
            message_template='{otp} x',
        )
        self.assertTrue(_sms_live_ready(cfg))

    @override_settings(ENVIRONMENT='staging', DEBUG=False, SMS_ENABLED=False, SMS_FORCE_SEND=False)
    def test_staging_live_ready_when_admin_enabled(self):
        cfg = _sms(
            is_enabled=True,
            provider='smartping',
            smartping_username='u',
            smartping_password='p',
            smartping_from='TOPTEEN',
            message_template='{otp} x',
        )
        self.assertTrue(_sms_live_ready(cfg))


class WhatsAppSettingsReadyTests(SimpleTestCase):
    def test_requires_approved_template(self):
        cfg = _wa(
            is_enabled=True,
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            whatsapp_from='+9199',
            otp_template='login_otp_verification',
            otp_template_status='DRAFT',
        )
        self.assertFalse(cfg.config_ready_for_test())
        self.assertFalse(cfg.is_ready())
        cfg.otp_template_status = 'APPROVED'
        self.assertTrue(cfg.config_ready_for_test())
        self.assertTrue(cfg.is_ready())

    def test_sandbox_ok_when_disabled(self):
        cfg = _wa(
            is_enabled=False,
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            whatsapp_from='+9199',
            otp_template='login_otp_verification',
            otp_template_status='APPROVED',
        )
        self.assertTrue(cfg.config_ready_for_test())
        self.assertFalse(cfg.is_ready())


class ChannelRoutingTests(SimpleTestCase):
    @patch('communication.messaging_config.get_whatsapp_settings')
    @patch('communication.messaging_config.get_sms_settings')
    def test_both_ready_prefers_whatsapp_channel_flag(self, mock_sms, mock_wa):
        mock_sms.return_value = _sms(
            is_enabled=True,
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='+91',
        )
        mock_wa.return_value = _wa(
            is_enabled=True,
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            whatsapp_from='+91',
            otp_template='t',
            otp_template_status='APPROVED',
        )
        self.assertTrue(channel_enabled('whatsapp'))
        self.assertTrue(channel_enabled('sms'))

    @patch('communication.messaging_config.get_whatsapp_settings')
    @patch('communication.messaging_config.get_sms_settings')
    def test_skip_reason_when_incomplete(self, mock_sms, mock_wa):
        mock_sms.return_value = _sms(is_enabled=False, plivo_auth_id='', plivo_auth_token='')
        mock_wa.return_value = _wa(is_enabled=False)
        self.assertTrue(skip_send_reason('k', channel='sms'))

    @patch('communication.com_service.ComService.send_mobile_otp')
    @patch('communication.com_service.ComService.send_whatsapp_otp')
    @patch('communication.com_service.ComService._channel_enabled')
    def test_send_otp_sms_type_uses_whatsapp_when_ready(self, mock_ch, mock_wa, mock_sms):
        from communication.com_service import ComService
        from core import choices

        mock_ch.side_effect = lambda c: c == 'whatsapp'
        svc = ComService()
        svc.send_otp(919999999999, choices.CommunicationTypeChooices.SMS)
        mock_wa.assert_called_once()
        mock_sms.assert_not_called()

    @patch('communication.com_service.ComService.send_mobile_otp')
    @patch('communication.com_service.ComService.send_whatsapp_otp')
    @patch('communication.com_service.ComService._channel_enabled')
    def test_send_otp_sms_type_falls_back_to_sms(self, mock_ch, mock_wa, mock_sms):
        from communication.com_service import ComService
        from core import choices

        mock_ch.return_value = False
        mock_sms.return_value = True
        svc = ComService()
        svc.send_otp(919999999999, choices.CommunicationTypeChooices.SMS)
        mock_wa.assert_not_called()
        mock_sms.assert_called_once()


class AdminTestBypassesEnabledTests(SimpleTestCase):
    @patch('communication.providers.get_provider')
    @patch('communication.com_service.ComService._sms_cfg')
    @patch('communication.com_service.ComService.make_log_entry')
    def test_admin_sms_test_when_disabled(self, mock_log, mock_cfg, mock_get):
        from communication.com_service import ComService

        cfg = _sms(
            is_enabled=False,
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='+919800000000',
        )
        mock_cfg.return_value = cfg
        provider = MagicMock()
        provider.supports_sms = True
        provider.send_sms.return_value = {'success': True, 'response': 'ok', 'message_uuid': 'u1'}
        mock_get.return_value = provider

        result = ComService().send_admin_test_otp('+919811111111', channel='sms')
        self.assertTrue(result['success'])
        provider.send_sms.assert_called_once()


class EnvFallbackTests(SimpleTestCase):
    @override_settings(
        ENVIRONMENT='production',
        DEBUG=False,
        SMS_PROVIDER='smartping',
        SMARTPING_SMS_USERNAME='user',
        SMARTPING_SMS_PASSWORD='pass',
        SMARTPING_SMS_FROM='TOPTEEN',
        SMARTPING_SMS_MESSAGE_TEMPLATE='{otp} code',
    )
    def test_env_fallback_when_table_missing(self):
        from django.db import ProgrammingError
        from communication.messaging_config import get_sms_settings, channel_enabled

        with patch(
            'communication.models.SmsSettings.load',
            side_effect=ProgrammingError('no such table'),
        ):
            cfg = get_sms_settings()
            self.assertTrue(getattr(cfg, '_from_env_fallback', False))
            self.assertTrue(cfg.credentials_ok())
            self.assertTrue(channel_enabled('sms'))
