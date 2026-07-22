"""
SmartPing SMS provider (India DLT transactional SMS).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from communication.providers.base import BaseMessagingProvider, register_provider

logger = logging.getLogger(__name__)


class SmartPingProvider(BaseMessagingProvider):
    key = 'smartping'
    label = 'SmartPing'
    supports_sms = True
    supports_whatsapp = False

    def send_sms(
        self,
        to_number: str,
        text: str,
        *,
        config: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        cfg = config or {}
        api_url = (cfg.get('api_url') or 'https://pgapi.smartping.ai/fe/api/v1/send').strip()
        params = {
            'username': cfg.get('username') or '',
            'password': cfg.get('password') or '',
            'unicode': cfg.get('unicode') or 'false',
            'from': cfg.get('from_id') or '',
            'to': to_number,
            'dltContentId': cfg.get('dlt_content_id') or '',
            'dltPrincipalEntityId': cfg.get('dlt_principal_entity_id') or '',
            'text': text,
        }
        if not params['username'] or not params['password']:
            return {
                'success': False,
                'error': 'SmartPing username/password not configured',
                'response': '',
                'status_code': None,
                'log_key': f'smartping:sms:{to_number}',
            }

        url = f'{api_url}?{urlencode(params)}'
        try:
            response = requests.get(url, timeout=timeout)
            if response.content:
                try:
                    response_text = response.content.decode('utf-8')
                except (UnicodeDecodeError, AttributeError):
                    response_text = str(response.content)
            else:
                response_text = f'Status: {response.status_code}'
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response': response_text,
                'error': None if response.status_code == 200 else response_text,
                'log_key': url,
            }
        except requests.RequestException as exc:
            logger.exception('SmartPing SMS failed')
            return {
                'success': False,
                'error': str(exc),
                'response': str(exc),
                'status_code': None,
                'log_key': url,
            }


register_provider(SmartPingProvider())
