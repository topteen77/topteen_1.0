"""
HTTP client for Kaunsa Laravel API (POST JSON, GET reference data).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class KaunsaApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: str = ''):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


def _timeout() -> int:
    return int(getattr(settings, 'KAUNSA_REQUEST_TIMEOUT', 30) or 30)


def _join(base: str, path: str) -> str:
    base = (base or '').rstrip('/')
    path = path.lstrip('/')
    return f'{base}/{path}' if path else base


def get_json(base_url: str, path: str) -> Dict[str, Any]:
    url = _join(base_url, path)
    r = requests.get(
        url,
        headers={'Accept': 'application/json'},
        timeout=_timeout(),
    )
    if not r.ok:
        raise KaunsaApiError(
            f'GET {url} failed: HTTP {r.status_code}',
            status_code=r.status_code,
            response_text=r.text[:2000],
        )
    return r.json()


def post_json(base_url: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = body or {}
    url = _join(base_url, path)
    r = requests.post(
        url,
        json=body,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
        timeout=_timeout(),
    )
    if not r.ok:
        raise KaunsaApiError(
            f'POST {url} failed: HTTP {r.status_code}',
            status_code=r.status_code,
            response_text=r.text[:2000],
        )
    try:
        return r.json()
    except ValueError as e:
        raise KaunsaApiError(f'Invalid JSON from {url}: {e}', status_code=r.status_code, response_text=r.text[:500])


def fetch_universities_list(scope: str) -> Dict[str, Any]:
    """
    POST /universities with optional cid for India or international.
    scope: 'india' | 'international'
    """
    if scope == 'india':
        base = getattr(settings, 'KAUNSA_INDIA_API_BASE_URL', '') or ''
        cid = getattr(settings, 'KAUNSA_INDIA_COUNTRY_ID', '') or ''
    elif scope == 'international':
        base = getattr(settings, 'KAUNSA_INTL_API_BASE_URL', '') or ''
        cid = getattr(settings, 'KAUNSA_INTL_COUNTRY_ID', '') or ''
    else:
        raise ValueError(f'Unknown scope: {scope}')

    if not base:
        raise KaunsaApiError(f'KAUNSA API base URL not configured for scope={scope}')

    body: Dict[str, Any] = {}
    if cid:
        body['cid'] = cid
    return post_json(base, 'universities', body)


def count_university_rows(payload: Dict[str, Any]) -> Optional[int]:
    """Best-effort row count from Laravel paginated or list response."""
    success = payload.get('success')
    if success is None:
        return None
    if isinstance(success, dict):
        if 'data' in success and isinstance(success['data'], list):
            return len(success['data'])
        if 'total' in success:
            try:
                return int(success['total'])
            except (TypeError, ValueError):
                return None
    if isinstance(success, list):
        return len(success)
    return None
