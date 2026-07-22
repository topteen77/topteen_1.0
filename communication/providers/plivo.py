"""
Plivo SMS + WhatsApp client (REST API via requests).

Docs: https://www.plivo.com/docs/
Console: https://manage.plivo.com/dashboard/

Credentials come from ``config`` (admin MessagingSettings) with Django settings fallback.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

from communication.providers.base import BaseMessagingProvider, register_provider

logger = logging.getLogger(__name__)

PLIVO_API_BASE = 'https://api.plivo.com/v1/Account'


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


def _auth_credentials(config: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    cfg = config or {}
    auth_id = (cfg.get('auth_id') or getattr(settings, 'PLIVO_AUTH_ID', '') or '').strip()
    auth_token = (cfg.get('auth_token') or getattr(settings, 'PLIVO_AUTH_TOKEN', '') or '').strip()
    return auth_id, auth_token


def is_configured(config: Optional[Dict[str, Any]] = None) -> bool:
    auth_id, auth_token = _auth_credentials(config)
    return bool(auth_id and auth_token)


def _message_url(auth_id: str) -> str:
    return f'{PLIVO_API_BASE}/{auth_id}/Message/'


def _post_message(payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Dict[str, Any]:
    auth_id, auth_token = _auth_credentials(config)
    if not auth_id or not auth_token:
        return {
            'success': False,
            'error': 'Plivo is not configured (set Auth ID and Auth Token in Messaging settings)',
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


def list_account_numbers(
    *,
    config: Optional[Dict[str, Any]] = None,
    services: str = 'sms',
    limit: int = 20,
    timeout: int = 15,
) -> Dict[str, Any]:
    """
    List Plivo account phone numbers (SMS-capable by default).

    GET /v1/Account/{auth_id}/Number/?services=sms
    WhatsApp WABA numbers are in Plivo Console → WhatsApp (not this endpoint).
    """
    auth_id, auth_token = _auth_credentials(config)
    if not auth_id or not auth_token:
        return {
            'success': False,
            'error': 'Plivo Auth ID and Auth Token are required',
            'numbers': [],
        }

    url = f'{PLIVO_API_BASE}/{auth_id}/Number/'
    params = {'limit': limit, 'offset': 0}
    if services:
        params['services'] = services

    try:
        response = requests.get(
            url,
            params=params,
            auth=(auth_id, auth_token),
            timeout=timeout,
        )
        try:
            body = response.json()
        except ValueError:
            body = {'raw': response.text}

        if response.status_code != 200:
            return {
                'success': False,
                'error': (body.get('error') if isinstance(body, dict) else None) or response.text,
                'numbers': [],
                'status_code': response.status_code,
            }

        objects = body.get('objects') if isinstance(body, dict) else None
        numbers = []
        for item in objects or []:
            num = str(item.get('number') or '').strip()
            if not num:
                continue
            numbers.append({
                'number': to_e164(num),
                'alias': item.get('alias') or '',
                'type': item.get('type') or '',
                'raw': item,
            })
        return {
            'success': True,
            'numbers': numbers,
            'status_code': response.status_code,
            'error': None,
        }
    except requests.RequestException as exc:
        logger.exception('Plivo list numbers failed')
        return {'success': False, 'error': str(exc), 'numbers': []}


def send_sms(
    to_number: str,
    text: str,
    *,
    src: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    cfg = config or {}
    src = (src or cfg.get('sms_from') or getattr(settings, 'PLIVO_SMS_FROM', '') or '').strip()
    if not src:
        return {
            'success': False,
            'error': 'Plivo SMS From is not set',
            'response': '',
            'status_code': None,
            'message_uuid': None,
        }

    payload = {
        'src': src if src.startswith('+') or not src.isdigit() else to_e164(src),
        'dst': to_e164(to_number),
        'text': text,
    }
    if not src.startswith('+') and not src.isdigit():
        payload['src'] = src

    result = _post_message(payload, config=cfg, timeout=timeout)
    result['log_key'] = f"plivo:sms:{payload['dst']}:{text}"
    return result


def send_whatsapp_text(
    to_number: str,
    text: str,
    *,
    src: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    cfg = config or {}
    src = (src or cfg.get('whatsapp_from') or getattr(settings, 'PLIVO_WHATSAPP_FROM', '') or '').strip()
    if not src:
        return {
            'success': False,
            'error': 'Plivo WhatsApp From is not set',
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
    result = _post_message(payload, config=cfg, timeout=timeout)
    result['log_key'] = f"plivo:whatsapp-text:{payload['dst']}"
    return result


def send_whatsapp_template(
    to_number: str,
    *,
    template_name: Optional[str] = None,
    language: Optional[str] = None,
    body_params: Optional[List[str]] = None,
    src: Optional[str] = None,
    auth_copy_code: bool = False,
    config: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    cfg = config or {}
    src = (src or cfg.get('whatsapp_from') or getattr(settings, 'PLIVO_WHATSAPP_FROM', '') or '').strip()
    template_name = (
        template_name
        or cfg.get('whatsapp_otp_template')
        or getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE', '')
        or ''
    ).strip()
    language = (
        language
        or cfg.get('whatsapp_otp_template_lang')
        or getattr(settings, 'PLIVO_WHATSAPP_OTP_TEMPLATE_LANG', 'en')
        or 'en'
    ).strip()

    if not src:
        return {
            'success': False,
            'error': 'Plivo WhatsApp From is not set',
            'response': '',
            'status_code': None,
            'message_uuid': None,
        }
    if not template_name:
        return {
            'success': False,
            'error': 'WhatsApp OTP template name is not set',
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
        if auth_copy_code:
            otp_code = str(body_params[0])
            components.append({
                'type': 'button',
                'sub_type': 'url',
                'index': '0',
                'parameters': [{'type': 'text', 'text': otp_code}],
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
    result = _post_message(payload, config=cfg, timeout=timeout)
    result['log_key'] = f"plivo:whatsapp-tpl:{payload['dst']}:{template_name}"
    return result


class PlivoProvider(BaseMessagingProvider):
    key = 'plivo'
    label = 'Plivo'
    supports_sms = True
    supports_whatsapp = True

    def send_sms(self, to_number, text, *, config=None, timeout=15):
        return send_sms(to_number, text, config=config, timeout=timeout)

    def send_whatsapp_template(
        self,
        to_number,
        *,
        template_name,
        language='en',
        body_params=None,
        auth_copy_code=False,
        config=None,
        timeout=15,
    ):
        return send_whatsapp_template(
            to_number,
            template_name=template_name,
            language=language,
            body_params=body_params,
            auth_copy_code=auth_copy_code,
            config=config,
            timeout=timeout,
        )

    def send_whatsapp_text(self, to_number, text, *, config=None, timeout=15):
        return send_whatsapp_text(to_number, text, config=config, timeout=timeout)


register_provider(PlivoProvider())
