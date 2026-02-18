import logging
from typing import Dict, Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_verification_sms(to_number: str, otp: str, message: str = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Send a verification SMS using SmartPing API. Configuration is read from Django settings
    which should be populated from the project's .env (see settings.SMARTPING_*).

    Returns a dict with keys:
      - success: bool
      - status_code: int (if request made)
      - response: text response from API (if any)
      - error: error message (on failure)
    """
    sms_text = message or settings.SMARTPING_SMS_MESSAGE_TEMPLATE.format(otp=otp)

    params = {
        "username": settings.SMARTPING_SMS_USERNAME,
        "password": settings.SMARTPING_SMS_PASSWORD,
        "unicode": settings.SMARTPING_SMS_UNICODE,
        "from": settings.SMARTPING_SMS_FROM,
        "to": to_number,
        "dltContentId": settings.SMARTPING_SMS_DLT_CONTENT_ID,
        "dltPrincipalEntityId": settings.SMARTPING_SMS_DLT_PRINCIPAL_ENTITY_ID,
        "text": sms_text,
    }

    try:
        resp = requests.get(settings.SMARTPING_SMS_API_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        logger.debug("SMS sent to %s: %s", to_number, resp.text)
        return {"success": True, "status_code": resp.status_code, "response": resp.text}
    except requests.RequestException as exc:
        logger.exception("Failed to send SMS to %s", to_number)
        return {"success": False, "error": str(exc)}

