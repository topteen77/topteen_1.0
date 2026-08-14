import logging
from typing import Dict, Any

from communication.messaging_config import get_sms_settings, should_send_mobile_message
from communication.providers import get_provider

logger = logging.getLogger(__name__)


def send_verification_sms(to_number: str, otp: str, message: str = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Send verification SMS via SMS settings.
    Missing keys / disabled → skipped.
    """
    cfg = get_sms_settings()
    provider_key = (cfg.provider or 'smartping').strip().lower()
    provider = get_provider(provider_key)
    sms_text = message or (cfg.message_template or '{otp} is your verification code for TopTeen').format(otp=otp)
    log_key = f'{provider_key}:sms:{to_number}:{sms_text}'

    if not should_send_mobile_message(log_key, channel='sms'):
        logger.info(
            'SMS skipped (enabled/keys). SMS ready=%s provider=%s',
            cfg.is_ready(),
            provider_key,
        )
        return {
            'success': True,
            'skipped': True,
            'response': 'SKIPPED: SMS not ready (keys/enabled)',
        }

    if not provider or not provider.supports_sms:
        return {'success': False, 'error': f'Provider {provider_key!r} unavailable'}

    result = provider.send_sms(
        to_number,
        sms_text,
        config=cfg.provider_config(),
        timeout=timeout,
    )
    return {
        'success': bool(result.get('success')),
        'status_code': result.get('status_code'),
        'response': result.get('response'),
        'error': result.get('error'),
    }
