"""
Redis (or default Django cache) helpers for Class 12 combined report.

Caches the expensive report context per student for 20 minutes after first build.
Viewer-specific flags (staff embed, etc.) are re-applied on each request.
"""

from __future__ import annotations

import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

COMBINED_REPORT_CACHE_TTL = 1200  # 20 minutes
COMBINED_REPORT_LOCK_TTL = 60
DASHBOARD_STATUS_CACHE_TTL = 300
CACHE_VERSION = 'v2'

_VIEWER_KEYS = frozenset({
    'user',
    'profile_user',
    'embed_mode',
    'viewing_student_report',
    'viewing_as_admin',
    'breadcrumb',
})


def combined_report_cache_key(user_id: int) -> str:
    return f'c12:combined_report:ctx:{CACHE_VERSION}:{int(user_id)}'


def combined_report_lock_key(user_id: int) -> str:
    return f'c12:combined_report:lock:{CACHE_VERSION}:{int(user_id)}'


def dashboard_status_cache_key(user_id: int) -> str:
    return f'c12:tests_dashboard:status:{CACHE_VERSION}:{int(user_id)}'


def invalidate_combined_report_cache(user_id: int) -> None:
    """Drop combined-report + tests-dashboard caches after a test submit."""
    uid = int(user_id)
    try:
        cache.delete(combined_report_cache_key(uid))
        cache.delete(dashboard_status_cache_key(uid))
    except Exception:
        logger.exception('Failed to invalidate C12 report cache for user %s', uid)


def _apply_viewer_overlay(ctx: dict, request, target_user) -> dict:
    from django.urls import reverse
    from core.breadcrumbs import get_breadcrumb

    report_student_id = int(target_user.id)
    viewing = bool(int(getattr(request.user, 'id', 0) or 0) != report_student_id)
    ctx['user'] = target_user
    ctx['profile_user'] = target_user
    ctx['report_student_id'] = report_student_id
    ctx['viewing_student_report'] = viewing
    ctx['viewing_as_admin'] = viewing
    ctx['embed_mode'] = (request.GET.get('embed') or '').strip() == '1'
    ctx['breadcrumb'] = get_breadcrumb([
        {'text': 'Tests', 'url': reverse('post_matric:tests')},
        {'text': 'Results', 'url': reverse('post_matric:results_list')},
        {'text': 'Combined Report', 'url': ''},
    ])
    return ctx


def get_or_build_combined_report_context(request, target_user, build_fn):
    """
    Return combined-report context, using Redis when available.

    On cache miss, uses a short lock to avoid stampede under Locust load.
    """
    user_id = int(target_user.id)
    key = combined_report_cache_key(user_id)

    try:
        cached = cache.get(key)
    except Exception:
        cached = None
        logger.exception('C12 combined report cache get failed for user %s', user_id)

    if cached is not None and isinstance(cached, dict):
        return _apply_viewer_overlay(dict(cached), request, target_user)

    lock_key = combined_report_lock_key(user_id)
    got_lock = False
    try:
        got_lock = cache.add(lock_key, '1', COMBINED_REPORT_LOCK_TTL)
    except Exception:
        got_lock = True

    if not got_lock:
        for _ in range(40):
            time.sleep(0.25)
            try:
                cached = cache.get(key)
            except Exception:
                cached = None
            if cached is not None and isinstance(cached, dict):
                return _apply_viewer_overlay(dict(cached), request, target_user)

    context = build_fn(request, target_user)

    if context and not context.get('no_results') and not context.get('error'):
        to_store = {k: v for k, v in context.items() if k not in _VIEWER_KEYS}
        try:
            cache.set(key, to_store, COMBINED_REPORT_CACHE_TTL)
        except Exception:
            logger.exception('Failed to cache C12 combined report for user %s', user_id)

    if got_lock:
        try:
            cache.delete(lock_key)
        except Exception:
            pass

    return _apply_viewer_overlay(context, request, target_user)


def warm_combined_report_cache(request, target_user, build_fn) -> None:
    """Precompute and store combined-report context after the last test submit."""
    invalidate_combined_report_cache(target_user.id)
    try:
        get_or_build_combined_report_context(request, target_user, build_fn)
    except Exception:
        logger.exception(
            'Failed to warm C12 combined report cache for user %s',
            target_user.id,
        )
