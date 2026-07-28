"""
Load separate SMS / WhatsApp admin settings and decide when live sends are allowed.

Production/staging safety:
- Seed empty admin fields from .env (SmartPing / Plivo).
- If SmsSettings / WhatsAppSettings tables are missing (migrations not deployed),
  fall back to env-only config so OTP does not 500.
- Production (ENVIRONMENT=production, DEBUG=False): allow live SMS when credentials
  are present (auto-enable), matching historical SmartPing behaviour.
- Non-production: require admin is_enabled and/or *_FORCE_SEND.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from django.conf import settings
from django.db import DatabaseError, OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

_DB_ERRORS = (ProgrammingError, OperationalError, DatabaseError)


def is_production_messaging_env() -> bool:
    env = str(getattr(settings, 'ENVIRONMENT', '') or '').strip().lower()
    return env == 'production' and not settings.DEBUG


def _sms_force_send_env() -> bool:
    return bool(
        getattr(settings, 'SMS_FORCE_SEND', False)
        or getattr(settings, 'SMARTPING_SMS_FORCE_SEND', False)
        or getattr(settings, 'PLIVO_FORCE_SEND', False)
    )


def _whatsapp_force_send_env() -> bool:
    return bool(
        getattr(settings, 'WHATSAPP_FORCE_SEND', False)
        or getattr(settings, 'PLIVO_FORCE_SEND', False)
    )


def _env_allows_live_send(*, channel: str, admin_enabled: bool) -> bool:
    """Production always; staging/dev need FORCE_SEND or admin enable."""
    if is_production_messaging_env():
        return True
    if channel == 'sms':
        return admin_enabled or _sms_force_send_env()
    if channel == 'whatsapp':
        return admin_enabled or _whatsapp_force_send_env()
    return False


def _env_sms_namespace():
    """In-memory SMS config from Django settings when DB table is unavailable."""
    provider = (getattr(settings, 'SMS_PROVIDER', None) or 'smartping').strip().lower()
    ns = SimpleNamespace(
        is_enabled=bool(getattr(settings, 'SMS_ENABLED', False)) or is_production_messaging_env(),
        provider=provider,
        message_template=(
            getattr(settings, 'SMARTPING_SMS_MESSAGE_TEMPLATE', None)
            or getattr(settings, 'PLIVO_SMS_MESSAGE_TEMPLATE', None)
            or '{otp} is your verification code for TopTeen'
        ),
        test_destination='',
        smartping_api_url=getattr(settings, 'SMARTPING_SMS_API_URL', '') or '',
        smartping_username=getattr(settings, 'SMARTPING_SMS_USERNAME', '') or '',
        smartping_password=getattr(settings, 'SMARTPING_SMS_PASSWORD', '') or '',
        smartping_from=getattr(settings, 'SMARTPING_SMS_FROM', '') or '',
        smartping_dlt_content_id=getattr(settings, 'SMARTPING_SMS_DLT_CONTENT_ID', '') or '',
        smartping_dlt_principal_entity_id=getattr(
            settings, 'SMARTPING_SMS_DLT_PRINCIPAL_ENTITY_ID', ''
        ) or '',
        smartping_unicode=getattr(settings, 'SMARTPING_SMS_UNICODE', 'false') or 'false',
        plivo_auth_id=getattr(settings, 'PLIVO_AUTH_ID', '') or '',
        plivo_auth_token=getattr(settings, 'PLIVO_AUTH_TOKEN', '') or '',
        plivo_sms_from=getattr(settings, 'PLIVO_SMS_FROM', '') or '',
        _from_env_fallback=True,
    )

    def credentials_ok():
        if provider == 'smartping':
            return bool(ns.smartping_username.strip() and ns.smartping_password.strip())
        if provider == 'plivo':
            return bool(ns.plivo_auth_id.strip() and ns.plivo_auth_token.strip())
        return False

    def has_from_number():
        if provider == 'smartping':
            return bool(ns.smartping_from.strip())
        if provider == 'plivo':
            return bool(ns.plivo_sms_from.strip())
        return False

    def config_ready_for_test():
        return credentials_ok() and has_from_number()

    def is_ready():
        if not config_ready_for_test():
            return False
        if not (ns.is_enabled or getattr(settings, 'SMS_ENABLED', False)):
            if not (is_production_messaging_env() and credentials_ok()):
                return False
        return _env_allows_live_send(channel='sms', admin_enabled=bool(ns.is_enabled))

    def missing_config_message():
        if not credentials_ok():
            return 'Missing SMS credentials in .env (and SmsSettings table unavailable)'
        if not has_from_number():
            return 'Missing SMS From in .env'
        return 'SMS not ready'

    def provider_config():
        if provider == 'smartping':
            return {
                'api_url': ns.smartping_api_url,
                'username': ns.smartping_username,
                'password': ns.smartping_password,
                'from_id': ns.smartping_from,
                'dlt_content_id': ns.smartping_dlt_content_id,
                'dlt_principal_entity_id': ns.smartping_dlt_principal_entity_id,
                'unicode': ns.smartping_unicode or 'false',
            }
        if provider == 'plivo':
            return {
                'auth_id': ns.plivo_auth_id,
                'auth_token': ns.plivo_auth_token,
                'sms_from': ns.plivo_sms_from,
            }
        return {}

    ns.credentials_ok = credentials_ok
    ns.has_from_number = has_from_number
    ns.config_ready_for_test = config_ready_for_test
    ns.is_ready = is_ready
    ns.missing_config_message = missing_config_message
    ns.provider_config = provider_config
    return ns


def _env_whatsapp_namespace():
    ns = SimpleNamespace(
        is_enabled=bool(getattr(settings, 'WHATSAPP_ENABLED', False)),
        provider='plivo',
        test_destination='',
        plivo_auth_id=getattr(settings, 'PLIVO_AUTH_ID', '') or '',
        plivo_auth_token=getattr(settings, 'PLIVO_AUTH_TOKEN', '') or '',
        waba_id=getattr(settings, 'PLIVO_WABA_ID', '') or '',
        whatsapp_from=getattr(settings, 'PLIVO_WHATSAPP_FROM', '') or '',
        otp_template=getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE', '') or '',
        otp_template_lang=getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE_LANG', 'en') or 'en',
        otp_template_status='',
        otp_template_preview='',
        _from_env_fallback=True,
    )

    def credentials_ok():
        return bool(ns.plivo_auth_id.strip() and ns.plivo_auth_token.strip())

    def template_is_approved():
        # Env-only fallback cannot verify Meta status — require WHATSAPP_ENABLED + template name
        return bool(ns.otp_template.strip()) and bool(getattr(settings, 'WHATSAPP_ENABLED', False))

    def has_from_number():
        return bool(ns.whatsapp_from.strip())

    def config_ready_for_test():
        return credentials_ok() and has_from_number() and bool(ns.otp_template.strip())

    def is_ready():
        if not (ns.is_enabled and config_ready_for_test() and template_is_approved()):
            return False
        return _env_allows_live_send(channel='whatsapp', admin_enabled=bool(ns.is_enabled))

    def missing_config_message():
        return 'WhatsAppSettings table unavailable — configure admin after migrate, or set WHATSAPP_ENABLED + Plivo env'

    def provider_config():
        return {
            'auth_id': ns.plivo_auth_id,
            'auth_token': ns.plivo_auth_token,
            'whatsapp_from': ns.whatsapp_from,
            'whatsapp_otp_template': ns.otp_template,
            'whatsapp_otp_template_lang': ns.otp_template_lang,
            'waba_id': ns.waba_id,
        }

    ns.credentials_ok = credentials_ok
    ns.template_is_approved = template_is_approved
    ns.has_from_number = has_from_number
    ns.config_ready_for_test = config_ready_for_test
    ns.is_ready = is_ready
    ns.missing_config_message = missing_config_message
    ns.provider_config = provider_config
    return ns


def seed_sms_settings_from_env(obj=None):
    from communication.models import SmsSettings

    try:
        obj = obj or SmsSettings.load()
    except _DB_ERRORS:
        return _env_sms_namespace()

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

    _set_if_empty('provider', getattr(settings, 'SMS_PROVIDER', 'smartping'))
    _set_if_empty('message_template', getattr(settings, 'SMARTPING_SMS_MESSAGE_TEMPLATE', None))
    _set_if_empty('message_template', getattr(settings, 'PLIVO_SMS_MESSAGE_TEMPLATE', None))
    # Correct known DLT mismatches (brand text that is not on the SmartPing template)
    approved_sms = (
        getattr(settings, 'SMARTPING_SMS_MESSAGE_TEMPLATE', None)
        or '{otp} is your verification code for TestprepGPT AI'
    ).strip()
    current_tmpl = (obj.message_template or '').strip()
    if approved_sms and current_tmpl and (
        'TopTeen' in current_tmpl
        or current_tmpl == '{otp} is your verification code for TestprepGPT'
    ):
        obj.message_template = approved_sms
        changed = True
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

    # Bootstrap enable so staging/production OTP keeps working after deploy
    # (admin can turn off later). Requires credentials + From.
    if not obj.is_enabled and obj.credentials_ok() and obj.has_from_number():
        obj.is_enabled = True
        changed = True

    if changed:
        try:
            obj.save()
            logger.info('SmsSettings seeded/bootstrapped from environment')
        except _DB_ERRORS:
            logger.warning('SmsSettings seed save failed — using in-memory values', exc_info=True)
    return obj


def seed_whatsapp_settings_from_env(obj=None):
    from communication.models import WhatsAppSettings

    try:
        obj = obj or WhatsAppSettings.load()
    except _DB_ERRORS:
        return _env_whatsapp_namespace()

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

    _set_if_empty('otp_template', getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE', None))
    _set_if_empty('otp_template_lang', getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE_LANG', None))
    _set_if_empty('plivo_auth_id', getattr(settings, 'PLIVO_AUTH_ID', None))
    _set_if_empty('plivo_auth_token', getattr(settings, 'PLIVO_AUTH_TOKEN', None))
    _set_if_empty('whatsapp_from', getattr(settings, 'PLIVO_WHATSAPP_FROM', None))
    _set_if_empty('waba_id', getattr(settings, 'PLIVO_WABA_ID', None))

    if (
        not obj.is_enabled
        and getattr(settings, 'WHATSAPP_ENABLED', False)
        and obj.config_ready_for_test()
        and obj.template_is_approved()
    ):
        obj.is_enabled = True
        changed = True

    if changed:
        try:
            obj.save()
            logger.info('WhatsAppSettings seeded/bootstrapped from environment')
        except _DB_ERRORS:
            logger.warning('WhatsAppSettings seed save failed', exc_info=True)
    return obj


def get_sms_settings():
    from communication.models import SmsSettings

    try:
        obj = SmsSettings.load()
        return seed_sms_settings_from_env(obj)
    except _DB_ERRORS as exc:
        logger.warning('SmsSettings unavailable (%s) — using .env fallback', exc)
        return _env_sms_namespace()


def get_whatsapp_settings():
    from communication.models import WhatsAppSettings

    try:
        obj = WhatsAppSettings.load()
        return seed_whatsapp_settings_from_env(obj)
    except _DB_ERRORS as exc:
        logger.warning('WhatsAppSettings unavailable (%s) — using .env fallback', exc)
        return _env_whatsapp_namespace()


def _sms_live_ready(cfg) -> bool:
    if not cfg.credentials_ok() or not cfg.has_from_number():
        return False
    tmpl = (getattr(cfg, 'message_template', None) or '').strip()
    if tmpl and '{otp}' not in tmpl:
        return False
    admin_on = bool(getattr(cfg, 'is_enabled', False) or getattr(settings, 'SMS_ENABLED', False))
    # Production: SmartPing/.env credentials alone are enough (historical behaviour)
    if not admin_on and is_production_messaging_env() and cfg.credentials_ok():
        admin_on = True
    if not admin_on:
        return False
    return _env_allows_live_send(channel='sms', admin_enabled=True)


def _whatsapp_live_ready(cfg) -> bool:
    if hasattr(cfg, 'is_ready') and getattr(cfg, '_from_env_fallback', False):
        return bool(cfg.is_ready())
    if not cfg.is_enabled and not getattr(settings, 'WHATSAPP_ENABLED', False):
        return False
    if not cfg.credentials_ok() or not cfg.has_from_number():
        return False
    if not (cfg.otp_template or '').strip() or not cfg.template_is_approved():
        return False
    return _env_allows_live_send(
        channel='whatsapp',
        admin_enabled=bool(cfg.is_enabled or getattr(settings, 'WHATSAPP_ENABLED', False)),
    )


def channel_enabled(channel: str) -> bool:
    channel = (channel or '').strip().lower()
    if channel == 'sms':
        return _sms_live_ready(get_sms_settings())
    if channel == 'whatsapp':
        return _whatsapp_live_ready(get_whatsapp_settings())
    return False


def should_send_mobile_message(log_key: str, channel: str = 'sms', check_duplicate=None) -> bool:
    if not channel_enabled(channel):
        return False
    if check_duplicate and check_duplicate(log_key):
        return False
    return True


def skip_send_reason(log_key: str, channel: str = 'sms', check_duplicate=None) -> str:
    channel = (channel or '').strip().lower()
    if channel == 'sms':
        cfg = get_sms_settings()
        if not _sms_live_ready(cfg):
            if not cfg.credentials_ok() or not cfg.has_from_number():
                return getattr(cfg, 'missing_config_message', lambda: 'SMS config incomplete')()
            if not _env_allows_live_send(channel='sms', admin_enabled=bool(cfg.is_enabled)):
                return (
                    'SMS blocked on non-production '
                    '(set SmsSettings.is_enabled or SMS_FORCE_SEND=True)'
                )
            return 'SMS not ready'
    elif channel == 'whatsapp':
        cfg = get_whatsapp_settings()
        if not _whatsapp_live_ready(cfg):
            return getattr(cfg, 'missing_config_message', lambda: 'WhatsApp not ready')()
    else:
        return f'unknown channel {channel!r}'

    if check_duplicate and check_duplicate(log_key):
        return 'duplicate within 30s'
    return 'skipped'


def get_messaging_settings():
    """Back-compat alias — returns SMS settings."""
    return get_sms_settings()
