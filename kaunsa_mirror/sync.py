"""
Sync Kaunsa API responses into KaunsaSnapshot with SHA-256 change detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from kaunsa_mirror.client import KaunsaApiError, count_university_rows, fetch_universities_list
from kaunsa_mirror.models import KaunsaSnapshot, KaunsaSyncLog

logger = logging.getLogger(__name__)

ENDPOINT_UNIVERSITIES = 'universities'


def canonical_json_bytes(data: Any) -> bytes:
    """Stable JSON for hashing (UTF-8)."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def content_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def _ensure_mirror_enabled() -> None:
    if not getattr(settings, 'KAUNSA_PG_ENABLED', False):
        raise RuntimeError('KAUNSA_PG_ENABLED is False — enable PostgreSQL mirror in .env')
    if 'kaunsa_mirror' not in settings.DATABASES:
        raise RuntimeError("DATABASES['kaunsa_mirror'] is not configured")


def sync_universities(scope: str) -> Dict[str, Any]:
    """
    Fetch POST /universities for scope, update snapshot if hash changed.
    Returns dict: success, skipped_no_change, hash, error (optional), http_status (optional).
    """
    _ensure_mirror_enabled()
    if scope not in (KaunsaSnapshot.Scope.INDIA, KaunsaSnapshot.Scope.INTERNATIONAL):
        raise ValueError('scope must be india or international')

    log = KaunsaSyncLog.objects.using('kaunsa_mirror').create(scope=scope)

    prev = (
        KaunsaSnapshot.objects.using('kaunsa_mirror')
        .filter(scope=scope, endpoint_key=ENDPOINT_UNIVERSITIES)
        .first()
    )
    log.hash_before = prev.content_hash if prev else ''

    try:
        payload = fetch_universities_list(scope)
    except KaunsaApiError as e:
        log.finished_at = timezone.now()
        log.success = False
        log.http_status = e.status_code
        log.error_message = str(e)[:4000]
        log.save(using='kaunsa_mirror')
        logger.warning('Kaunsa sync failed scope=%s: %s', scope, e)
        return {
            'success': False,
            'skipped_no_change': False,
            'error': str(e),
            'http_status': e.status_code,
        }
    except Exception as e:
        log.finished_at = timezone.now()
        log.success = False
        log.error_message = str(e)[:4000]
        log.save(using='kaunsa_mirror')
        logger.exception('Kaunsa sync unexpected error scope=%s', scope)
        return {'success': False, 'skipped_no_change': False, 'error': str(e)}

    new_hash = content_hash(payload)
    log.http_status = 200

    if prev and prev.content_hash == new_hash:
        log.finished_at = timezone.now()
        log.success = True
        log.skipped_no_change = True
        log.hash_after = new_hash
        with transaction.atomic(using='kaunsa_mirror'):
            log.save(using='kaunsa_mirror')
        return {
            'success': True,
            'skipped_no_change': True,
            'hash': new_hash,
        }

    row_count = count_university_rows(payload)
    with transaction.atomic(using='kaunsa_mirror'):
        KaunsaSnapshot.objects.using('kaunsa_mirror').update_or_create(
            scope=scope,
            endpoint_key=ENDPOINT_UNIVERSITIES,
            defaults={
                'content_hash': new_hash,
                'row_count': row_count,
                'payload': payload,
            },
        )
        log.finished_at = timezone.now()
        log.success = True
        log.skipped_no_change = False
        log.hash_after = new_hash
        log.save(using='kaunsa_mirror')

    return {
        'success': True,
        'skipped_no_change': False,
        'hash': new_hash,
        'row_count': row_count,
    }


def sync_both() -> Dict[str, Dict[str, Any]]:
    return {
        'india': sync_universities(KaunsaSnapshot.Scope.INDIA),
        'international': sync_universities(KaunsaSnapshot.Scope.INTERNATIONAL),
    }


def check_postgres_connection() -> bool:
    """Return True if kaunsa_mirror DB accepts a simple query."""
    _ensure_mirror_enabled()
    from django.db import connections

    conn = connections['kaunsa_mirror']
    conn.ensure_connection()
    with conn.cursor() as c:
        c.execute('SELECT 1')
        one = c.fetchone()
    return one == (1,)
