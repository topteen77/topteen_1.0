"""Verify stepped SMS/WhatsApp messaging setup flow (no live provider calls)."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from communication.messaging_config import (
    apply_no_numbers_fallback,
    flow_steps,
    has_from_number,
    provider_credentials_ok,
    template_ready,
)
from communication.models import MessagingSettings


def _fresh_cfg(**kwargs):
    cfg = MessagingSettings(
        pk=1,
        active_channel='',
        sms_provider='plivo',
        whatsapp_provider='plivo',
        sender_mode=MessagingSettings.SENDER_MODE_PRODUCTION,
        sms_message_template='{otp} is your code',
        whatsapp_otp_template='',
        whatsapp_otp_template_status='',
        plivo_auth_id='',
        plivo_auth_token='',
        plivo_sms_from='',
        plivo_whatsapp_from='',
        plivo_waba_id='',
    )
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class MessagingFlowStepsTests(SimpleTestCase):
    def test_step1_service_selection(self):
        cfg = _fresh_cfg()
        steps = {s['id']: s for s in flow_steps(cfg)}
        self.assertFalse(steps[1]['done'])

        cfg.active_channel = 'whatsapp'
        steps = {s['id']: s for s in flow_steps(cfg)}
        self.assertTrue(steps[1]['done'])
        self.assertIn('WhatsApp', steps[1]['detail'])

    def test_step2_provider_credentials(self):
        cfg = _fresh_cfg(active_channel='sms', sms_provider='plivo')
        self.assertFalse(provider_credentials_ok(cfg))
        steps = {s['id']: s for s in flow_steps(cfg)}
        self.assertFalse(steps[2]['done'])

        cfg.plivo_auth_id = 'MAXXXX'
        cfg.plivo_auth_token = 'token'
        self.assertTrue(provider_credentials_ok(cfg))
        steps = {s['id']: s for s in flow_steps(cfg)}
        self.assertTrue(steps[2]['done'])

    def test_step3_sms_template_vs_whatsapp_approved(self):
        sms = _fresh_cfg(active_channel='sms', sms_message_template='{otp} code')
        self.assertTrue(template_ready(sms))

        wa = _fresh_cfg(
            active_channel='whatsapp',
            whatsapp_otp_template='login_otp_verification',
            whatsapp_otp_template_status='DRAFT',
        )
        self.assertFalse(template_ready(wa))
        wa.whatsapp_otp_template_status = 'APPROVED'
        self.assertTrue(template_ready(wa))

    def test_step3a_production_shows_test_sandbox_shows_only_test(self):
        prod = _fresh_cfg(
            active_channel='sms',
            sender_mode=MessagingSettings.SENDER_MODE_PRODUCTION,
        )
        steps = {s['id']: s for s in flow_steps(prod)}
        self.assertTrue(steps['3a']['show_production_test'])
        self.assertFalse(steps['3a']['show_sandbox_test_only'])

        sand = _fresh_cfg(
            active_channel='sms',
            sender_mode=MessagingSettings.SENDER_MODE_TESTING,
        )
        steps = {s['id']: s for s in flow_steps(sand)}
        self.assertFalse(steps['3a']['show_production_test'])
        self.assertTrue(steps['3a']['show_sandbox_test_only'])

    def test_step4_and_5_no_number_forces_sandbox(self):
        cfg = _fresh_cfg(
            active_channel='sms',
            sms_provider='plivo',
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='',
            sender_mode=MessagingSettings.SENDER_MODE_PRODUCTION,
        )
        self.assertFalse(has_from_number(cfg))

        with patch.object(MessagingSettings, 'save') as mock_save:
            changed = apply_no_numbers_fallback(cfg)
            self.assertTrue(changed)
            self.assertEqual(cfg.sender_mode, MessagingSettings.SENDER_MODE_TESTING)
            mock_save.assert_called_once()

        steps = {s['id']: s for s in flow_steps(cfg)}
        self.assertIn('Sandbox', steps[5]['detail'])

    def test_step5_with_from_number_is_production_path(self):
        cfg = _fresh_cfg(
            active_channel='sms',
            sms_provider='plivo',
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='+919999999999',
            sender_mode=MessagingSettings.SENDER_MODE_PRODUCTION,
            sms_message_template='{otp} x',
        )
        self.assertTrue(has_from_number(cfg))
        steps = {s['id']: s for s in flow_steps(cfg)}
        self.assertIn('Production', steps[5]['detail'])
        self.assertTrue(steps[5]['done'])

    @override_settings(ENVIRONMENT='production', DEBUG=False)
    def test_sandbox_blocked_on_production_app(self):
        cfg = _fresh_cfg(
            active_channel='sms',
            sms_provider='plivo',
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='+9199',
            sender_mode=MessagingSettings.SENDER_MODE_TESTING,
        )
        self.assertFalse(cfg.sender_allowed_in_current_env())
        self.assertTrue(cfg.sender_mode_block_reason())

    @override_settings(ENVIRONMENT='production', DEBUG=False)
    def test_production_mode_allowed_on_production_app(self):
        cfg = _fresh_cfg(
            active_channel='sms',
            sms_provider='plivo',
            plivo_auth_id='MA',
            plivo_auth_token='tok',
            plivo_sms_from='+9199',
            sender_mode=MessagingSettings.SENDER_MODE_PRODUCTION,
            sms_message_template='{otp} x',
        )
        self.assertTrue(cfg.sender_allowed_in_current_env())
        self.assertTrue(cfg.is_sms_ready())
