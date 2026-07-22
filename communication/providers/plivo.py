"""
Plivo SMS + WhatsApp client (REST API via requests).

Docs: https://www.plivo.com/docs/
Console: https://manage.plivo.com/dashboard/
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PLIVO_API_BASE = 'https://api.plivo.com/v1/Account'


def _auth_credentials() -> tuple[str, str]:
    auth_id = (getattr(settings, 'PLIVO_AUTH_ID', None) or '').strip()
    auth_token = (getattr(settings, 'PLIVO_AUTH_TOKEN', None) or '').strip()
    return auth_id, auth_token


def is_configured() -> bool:
    auth_id, auth_token = _auth_credentials()
    return bool(auth_id and auth_token)


def to_e164(phone_number: str) -> str:
    """
    Normalize to E.164 (+country…digits).
    10-digit Indian mobiles (6–9…) become +91…; already-prefixed numbers keep their country code.
    """
    phone_str = str(phone_number).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone_str.startswith('+'):
        digits = phone_str[1:]
    else:
        digits = phone_str
    digits = ''.join(ch for ch in digits if ch.isdigit())
    if not digits:
        return phone_str
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in '6789':
        digits = f'91{digits}'
    return f'+{digits}'


def _message_url(auth_id: str) -> str:
    return f'{PLIVO_API_BASE}/{auth_id}/Message/'


def _post_message(payload: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
    auth_id, auth_token = _auth_credentials()
    if not auth_id or not auth_token:
        return {
            'success': False,
            'error': 'Plivo is not configured (set PLIVO_AUTH_ID and PLIVO_AUTH_TOKEN)',
            'response': '',
            'status_code': None,
            'message_uuid': None,
        }

    try:
        response = requests.post(
            _message_url(auth_id),
            json=payload,
            auth=(auth_id, auth_token),
            headers={'Content-Type': 'application/json'},
            timeout=timeout,
        )
        try:
            body = response.json()
        except ValueError:
            body = {'raw': response.text}

        message_uuid = None
        if isinstance(body, dict):
            uuids = body.get('message_uuid') or body.get('message_uuids')
            if isinstance(uuids, list) and uuids:
                message_uuid = uuids[0]
            elif isinstance(uuids, str):
                message_uuid = uuids

        # Plivo returns 202 Accepted on successful queue
        success = response.status_code in (200, 202) and not (
            isinstance(body, dict) and body.get('error')
        )
        if not success:
            logger.warning(
                'Plivo message failed status=%s body=%s payload_keys=%s',
                response.status_code,
                body,
                list(payload.keys()),
            )
        return {
            'success': success,
            'status_code': response.status_code,
            'response': json.dumps(body) if not isinstance(body, str) else body,
            'message_uuid': message_uuid,
            'error': None if success else (body.get('error') if isinstance(body, dict) else response.text),
        }
    except requests.RequestException as exc:
        logger.exception('Plivo API request failed')
        return {
            'success': False,
            'error': str(exc),
            'response': str(exc),
            'status_code': None,
            'message_uuid': None,
        }


def send_sms(
    to_number: str,
    text: str,
    *,
    src: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Send a transactional SMS via Plivo."""
    src = (src or getattr(settings, 'PLIVO_SMS_FROM', '') or '').strip()
    if not src:
        return {
            'success': False,
            'error': 'PLIVO_SMS_FROM is not set',
            'response': '',
            'status_code': None,
            'message_uuid': None,
        }

    payload = {
        'src': src if src.startswith('+') or not src.isdigit() else to_e164(src),
        'dst': to_e164(to_number),
        'text': text,
    }
    # Alphanumeric sender IDs (India etc.) must stay as-is, not E.164
    if not src.startswith('+') and not src.isdigit():
        payload['src'] = src

    return _post_message(payload, timeout=timeout)


def send_whatsapp_text(
    to_number: str,
    text: str,
    *,
    src: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """
    Send a free-form WhatsApp message (only valid inside an open customer-care window).
    Prefer send_whatsapp_template for outbound OTPs / first contact.
    """
    src = (src or getattr(settings, 'PLIVO_WHATSAPP_FROM', '') or '').strip()
    if not src:
        return {
            'success': False,
            'error': 'PLIVO_WHATSAPP_FROM is not set',
            'response': '',
            'status_code': None,
            'message_uuid': None,
        }

    payload = {
        'src': to_e164(src),
        'dst': to_e164(to_number),
        'type': 'whatsapp',
        'text': text,
    }
    return _post_message(payload, timeout=timeout)


def send_whatsapp_template(
    to_number: str,
    *,
    template_name: Optional[str] = None,
    language: Optional[str] = None,
    body_params: Optional[List[str]] = None,
    src: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """
    Send an approved WhatsApp template message (required to start a conversation).

    body_params are mapped to sequential body text placeholders in the template.
    """
    src = (src or getattr(settings, 'PLIVO_WHATSAPP_FROM', '') or '').strip()
    template_name = (
        template_name
        or getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE', '')
        or ''
    ).strip()
    language = (
        language
        or getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE_LANG', 'en_US')
        or 'en_US'
    ).strip()

    if not src:
        return {
            'success': False,
            'error': 'PLIVO_WHATSAPP_FROM is not set',
            'response': '',
            'status_code': None,
            'message_uuid': None,
        }
    if not template_name:
        return {
            'success': False,
            'error': 'PLIVO_WHATSAPP_OTP_TEMPLATE is not set (approved template name required)',
            'response': '',
            'status_code': None,
            'message_uuid': None,
        }

    components: List[Dict[str, Any]] = []
    if body_params:
        components.append({
            'type': 'body',
            'parameters': [{'type': 'text', 'text': str(p)} for p in body_params],
        })

    template: Dict[str, Any] = {
        'name': template_name,
        'language': language,
    }
    if components:
        template['components'] = components

    payload = {
        'src': to_e164(src),
        'dst': to_e164(to_number),
        'type': 'whatsapp',
        'template': template,
    }
    return _post_message(payload, timeout=timeout)
