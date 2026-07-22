"""
Helpers to load admin MessagingSettings and decide when sends are allowed.

ENVIRONMENT and DEBUG always come from Django settings (.env), never from admin.
Missing provider API keys → that service is disabled even if the channel is selected.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def is_production_messaging_env() -> bool:
    env = str(getattr(settings, 'ENVIRONMENT', '') or '').strip().lower()
    return env == 'production' and not settings.DEBUG


def get_messaging_settings():
    from communication.models import MessagingSettings
    return MessagingSettings.load()


def channel_enabled(channel: str, cfg=None) -> bool:
    """Channel selected AND provider keys present."""
    cfg = cfg or get_messaging_settings()
    channel = (channel or '').strip().lower()
    if channel == 'whatsapp':
        return cfg.is_whatsapp_ready()
    if channel == 'sms':
        return cfg.is_sms_ready()
    return False


def force_send_allowed(cfg=None) -> bool:
    cfg = cfg or get_messaging_settings()
    return bool(cfg.force_send_non_production)


def env_allows_send(cfg=None) -> bool:
    """
    Production env: only production sender numbers.
    Non-production: testing numbers allowed; production numbers need force_send.
    """
    cfg = cfg or get_messaging_settings()
    if is_production_messaging_env():
        if getattr(cfg, 'sender_mode', 'production') == 'testing':
            return False
        return True
    # Non-production app env
    if getattr(cfg, 'sender_mode', 'production') == 'testing':
        return True
    return force_send_allowed(cfg)


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
    else:
        return f'unknown channel {channel!r}'

    block = cfg.sender_mode_block_reason()
    if block:
        return block

    if not env_allows_send(cfg):
        if is_production_messaging_env():
            return 'blocked on production with testing sender mode'
        return (
            f'non-production messaging blocked for production sender numbers '
            f'(ENVIRONMENT={getattr(settings, "ENVIRONMENT", "")!r}, DEBUG={settings.DEBUG}; '
            f'enable Force send non-production only for tests, or set Sender mode to Testing)'
        )
    if check_duplicate and check_duplicate(log_key):
        return 'duplicate within 30s'
    return 'skipped'


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

    # Do NOT auto-enable a channel from env — admin must choose SMS or WhatsApp explicitly.
    if changed:
        obj.save()
        logger.info('MessagingSettings credential fields seeded from environment')
    return obj
