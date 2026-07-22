import logging
from typing import Dict, Any

from django.conf import settings

from communication.messaging_config import get_messaging_settings, should_send_mobile_message
from communication.providers import get_provider

logger = logging.getLogger(__name__)


def send_verification_sms(to_number: str, otp: str, message: str = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Send verification SMS via the admin-selected provider.
    Missing keys → skipped (service disabled).
    """
    cfg = get_messaging_settings()
    provider_key = (cfg.sms_provider or 'smartping').strip().lower()
    provider = get_provider(provider_key)
    sms_text = message or (cfg.sms_message_template or '{otp} is your verification code for TopTeen').format(otp=otp)
    log_key = f'{provider_key}:sms:{to_number}:{sms_text}'

    if not should_send_mobile_message(log_key, channel='sms'):
        logger.info(
            'SMS skipped (channel/keys/env). SMS ready=%s provider=%s',
            cfg.is_sms_ready(),
            provider_key,
        )
        return {
            'success': True,
            'skipped': True,
            'response': 'SKIPPED: SMS not ready (keys/channel/environment)',
        }

    if not provider or not provider.supports_sms:
        return {'success': False, 'error': f'Provider {provider_key!r} unavailable'}

    result = provider.send_sms(
        to_number,
        sms_text,
        config=cfg.provider_config_for(provider_key),
        timeout=timeout,
    )
    return {
        'success': bool(result.get('success')),
        'status_code': result.get('status_code'),
        'response': result.get('response'),
        'error': result.get('error'),
    }
