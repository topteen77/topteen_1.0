"""
Stepped messaging setup flow helpers.

Steps:
  1. Select service (SMS / WhatsApp)
  2. Select provider for that service
  3. Fetch/approve template (WhatsApp) or confirm SMS text
  3a. Choose Production vs Sandbox/Testing
  4. Fetch From numbers when provider supports it
  5. No number → sandbox testing only; number present → production sends allowed
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def is_production_messaging_env() -> bool:
    env = str(getattr(settings, 'ENVIRONMENT', '') or '').strip().lower()
    return env == 'production' and not settings.DEBUG


def get_messaging_settings():
    from communication.models import MessagingSettings
    return MessagingSettings.load()


def active_provider(cfg=None) -> str:
    cfg = cfg or get_messaging_settings()
    if cfg.active_channel == 'whatsapp':
        return (cfg.whatsapp_provider or '').strip().lower()
    if cfg.active_channel == 'sms':
        return (cfg.sms_provider or '').strip().lower()
    return ''


def has_from_number(cfg=None) -> bool:
    cfg = cfg or get_messaging_settings()
    prov = active_provider(cfg)
    if cfg.active_channel == 'sms':
        if prov == 'plivo':
            return bool((cfg.plivo_sms_from or '').strip())
        if prov == 'smartping':
            return bool((cfg.smartping_from or '').strip())
    if cfg.active_channel == 'whatsapp':
        if prov == 'plivo':
            return bool((cfg.plivo_whatsapp_from or '').strip())
    return False


def provider_credentials_ok(cfg=None) -> bool:
    """Auth/keys without requiring From number (needed before fetch numbers)."""
    cfg = cfg or get_messaging_settings()
    prov = active_provider(cfg)
    if not prov:
        return False
    if prov == 'smartping':
        return bool(cfg.smartping_username.strip() and cfg.smartping_password.strip())
    if prov == 'plivo':
        return bool(cfg.plivo_auth_id.strip() and cfg.plivo_auth_token.strip())
    return False


def template_ready(cfg=None) -> bool:
    cfg = cfg or get_messaging_settings()
    if cfg.active_channel == 'sms':
        return bool((cfg.sms_message_template or '').strip() and '{otp}' in cfg.sms_message_template)
    if cfg.active_channel == 'whatsapp':
        status = (cfg.whatsapp_otp_template_status or '').strip().upper()
        return bool((cfg.whatsapp_otp_template or '').strip() and status == 'APPROVED')
    return False


def force_send_allowed(cfg=None) -> bool:
    cfg = cfg or get_messaging_settings()
    return bool(cfg.force_send_non_production)


def env_allows_send(cfg=None) -> bool:
    cfg = cfg or get_messaging_settings()
    if is_production_messaging_env():
        if getattr(cfg, 'sender_mode', 'production') == 'testing':
            return False
        return True
    if getattr(cfg, 'sender_mode', 'production') == 'testing':
        return True
    return force_send_allowed(cfg)


def channel_enabled(channel: str, cfg=None) -> bool:
    cfg = cfg or get_messaging_settings()
    channel = (channel or '').strip().lower()
    if channel == 'whatsapp':
        return cfg.is_whatsapp_ready()
    if channel == 'sms':
        return cfg.is_sms_ready()
    return False


def should_send_mobile_message(log_key: str, channel: str = 'sms', cfg=None, check_duplicate=None) -> bool:
    cfg = cfg or get_messaging_settings()
    if not channel_enabled(channel, cfg):
        return False
    if not env_allows_send(cfg):
        return False
    if check_duplicate and check_duplicate(log_key):
        return False
    return True


def skip_send_reason(log_key: str, channel: str = 'sms', cfg=None, check_duplicate=None) -> str:
    cfg = cfg or get_messaging_settings()
    channel = (channel or '').strip().lower()

    if channel == 'sms':
        if not cfg.sms_enabled:
            return f'active_channel is {cfg.active_channel!r} (need sms)'
        if not cfg.provider_keys_ok(cfg.sms_provider, for_whatsapp=False):
            return (
                f'SMS disabled — no/incomplete keys for provider {cfg.sms_provider!r}. '
                f'{cfg.missing_keys_message(cfg.sms_provider, for_whatsapp=False)}'
            )
    elif channel == 'whatsapp':
        if not cfg.whatsapp_enabled:
            return f'active_channel is {cfg.active_channel!r} (need whatsapp)'
        if not cfg.provider_keys_ok(cfg.whatsapp_provider, for_whatsapp=True):
            return (
                f'WhatsApp disabled — no/incomplete keys for provider {cfg.whatsapp_provider!r}. '
                f'{cfg.missing_keys_message(cfg.whatsapp_provider, for_whatsapp=True)}'
            )
        if not cfg.whatsapp_template_is_approved():
            return (
                f'WhatsApp template {cfg.whatsapp_otp_template!r} status is '
                f'{cfg.whatsapp_otp_template_status or "unknown"!r} — must be APPROVED. '
                f'Complete Step 3 (fetch template) after Meta approval.'
            )
    else:
        return f'unknown channel {channel!r}'

    block = cfg.sender_mode_block_reason()
    if block:
        return block

    if not env_allows_send(cfg):
        if is_production_messaging_env():
            return 'blocked on production with testing/sandbox sender mode'
        return (
            'non-production app with production sender mode — use Sandbox mode '
            'or enable Force send non-production for a one-off test'
        )
    if check_duplicate and check_duplicate(log_key):
        return 'duplicate within 30s'
    return 'skipped'


def flow_steps(cfg=None) -> List[Dict[str, Any]]:
    """Return ordered setup steps with done/ready flags for the admin UI."""
    cfg = cfg or get_messaging_settings()
    channel = cfg.active_channel or ''
    prov = active_provider(cfg)
    creds = provider_credentials_ok(cfg)
    tmpl = template_ready(cfg)
    from_ok = has_from_number(cfg)
    mode = cfg.sender_mode or 'production'

    steps = [
        {
            'id': 1,
            'title': 'Select service',
            'done': channel in ('sms', 'whatsapp'),
            'detail': cfg.get_active_channel_display() if channel else 'Not selected',
        },
        {
            'id': 2,
            'title': 'Select provider',
            'done': bool(channel and prov and creds),
            'detail': (
                f'{prov or "—"}'
                + (' (credentials OK)' if creds else ' (add API keys)')
            ) if channel else 'Select service first',
        },
        {
            'id': 3,
            'title': 'Fetch / confirm template',
            'done': bool(channel and tmpl),
            'detail': (
                f'WA {cfg.whatsapp_otp_template} [{cfg.whatsapp_otp_template_status or "?"}]'
                if channel == 'whatsapp'
                else ('SMS text set' if tmpl else 'Set SMS message with {otp}')
            ) if channel else '—',
        },
        {
            'id': '3a',
            'title': 'Production or Sandbox',
            'done': bool(channel and mode in ('production', 'testing')),
            'detail': cfg.get_sender_mode_display(),
            'show_production_test': mode == 'production',
            'show_sandbox_test_only': mode == 'testing',
        },
        {
            'id': 4,
            'title': 'Fetch From numbers',
            'done': from_ok or mode == 'testing',
            'detail': (
                'From number set'
                if from_ok
                else ('No number — use Sandbox testing' if mode == 'testing' else 'Fetch or paste From number')
            ),
        },
        {
            'id': 5,
            'title': 'Send path',
            'done': bool(channel and tmpl and creds and (from_ok or mode == 'testing')),
            'detail': (
                'Production sends (From number available)'
                if (mode == 'production' and from_ok)
                else 'Sandbox / testing messages only'
            ),
        },
    ]
    return steps


def apply_no_numbers_fallback(cfg=None) -> bool:
    """
    If no From number after fetch, force Sandbox/Testing mode.
    Returns True if sender_mode was changed.
    """
    cfg = cfg or get_messaging_settings()
    if has_from_number(cfg):
        return False
    if cfg.sender_mode != cfg.SENDER_MODE_TESTING:
        cfg.sender_mode = cfg.SENDER_MODE_TESTING
        cfg.save(update_fields=['sender_mode', 'updated_at'])
        return True
    return False


def seed_messaging_settings_from_env(obj=None):
    """Fill empty MessagingSettings credential fields from Django settings / .env (once)."""
    from communication.models import MessagingSettings

    obj = obj or MessagingSettings.load()
    changed = False

    def _set_if_empty(field, value):
        nonlocal changed
        if value is None:
            return
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return
        current = getattr(obj, field)
        if isinstance(current, str) and not current.strip():
            setattr(obj, field, value)
            changed = True

    _set_if_empty('sms_provider', getattr(settings, 'SMS_PROVIDER', 'smartping'))
    _set_if_empty('sms_message_template', getattr(settings, 'PLIVO_SMS_MESSAGE_TEMPLATE', None))
    _set_if_empty('sms_message_template', getattr(settings, 'SMARTPING_SMS_MESSAGE_TEMPLATE', None))
    _set_if_empty('whatsapp_otp_template', getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE', None))
    _set_if_empty('whatsapp_otp_template_lang', getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE_LANG', None))

    _set_if_empty('smartping_api_url', getattr(settings, 'SMARTPING_SMS_API_URL', None))
    _set_if_empty('smartping_username', getattr(settings, 'SMARTPING_SMS_USERNAME', None))
    _set_if_empty('smartping_password', getattr(settings, 'SMARTPING_SMS_PASSWORD', None))
    _set_if_empty('smartping_from', getattr(settings, 'SMARTPING_SMS_FROM', None))
    _set_if_empty('smartping_dlt_content_id', getattr(settings, 'SMARTPING_SMS_DLT_CONTENT_ID', None))
    _set_if_empty('smartping_dlt_principal_entity_id', getattr(settings, 'SMARTPING_SMS_DLT_PRINCIPAL_ENTITY_ID', None))
    _set_if_empty('smartping_unicode', getattr(settings, 'SMARTPING_SMS_UNICODE', None))

    _set_if_empty('plivo_auth_id', getattr(settings, 'PLIVO_AUTH_ID', None))
    _set_if_empty('plivo_auth_token', getattr(settings, 'PLIVO_AUTH_TOKEN', None))
    _set_if_empty('plivo_sms_from', getattr(settings, 'PLIVO_SMS_FROM', None))
    _set_if_empty('plivo_whatsapp_from', getattr(settings, 'PLIVO_WHATSAPP_FROM', None))

    if changed:
        obj.save()
        logger.info('MessagingSettings credential fields seeded from environment')
    return obj
