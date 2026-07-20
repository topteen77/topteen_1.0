"""
Redis helpers for Class 10 (Stream Sorter) combined report.

Caches expensive report context per student; viewer-specific flags are reapplied
per request. Also tracks short-lived HTML page cache keys for invalidation.
"""

from __future__ import annotations

import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

CLASS10_REPORT_CACHE_TTL = 1200  # 20 minutes
CLASS10_REPORT_LOCK_TTL = 60
CLASS10_HTML_CACHE_TTL = 60
CACHE_VERSION = "v1"

_VIEWER_KEYS = frozenset({
    "viewing_as_admin",
    "embed_mode",
    "user_id",  # route id may differ for staff viewing
    "breadcrumb",
})


def class10_combined_report_cache_key(user_id: int) -> str:
    return f"c10:combined_report:ctx:{CACHE_VERSION}:{int(user_id)}"


def class10_combined_report_lock_key(user_id: int) -> str:
    return f"c10:combined_report:lock:{CACHE_VERSION}:{int(user_id)}"


def class10_combined_report_html_cache_key(user_id: int, embed: bool) -> str:
    return f"c10:combined_report:html:{CACHE_VERSION}:{int(user_id)}:{1 if embed else 0}"


def invalidate_class10_report_cache(user_id: int) -> None:
    """Drop Class 10 combined-report context + HTML caches after a test submit."""
    uid = int(user_id)
    try:
        cache.delete(class10_combined_report_cache_key(uid))
        cache.delete(class10_combined_report_html_cache_key(uid, False))
        cache.delete(class10_combined_report_html_cache_key(uid, True))
    except Exception:
        logger.exception("Failed to invalidate C10 report cache for user %s", uid)

    # Stale PDFs would otherwise be served forever — best-effort delete.
    try:
        from django.contrib.auth import get_user_model
        from core.utils import (
            class10_web_report_pdf_filename,
            delete_user_pdf,
        )

        user = get_user_model().objects.only("id", "name", "email").filter(pk=uid).first()
        if not user:
            return
        for kind in ("combined", "test1", "test2", "test3"):
            delete_user_pdf(uid, class10_web_report_pdf_filename(user, kind))
    except Exception:
        logger.exception("Failed to clear C10 report PDFs for user %s", uid)


def _apply_viewer_overlay(ctx: dict, request, target_user, *, route_user_id=None, embed_mode: bool = False) -> dict:
    from django.urls import reverse
    from core.breadcrumbs import get_breadcrumb

    viewer_id = int(getattr(request.user, "id", 0) or 0)
    effective_route_id = (
        int(route_user_id) if route_user_id is not None else int(target_user.id)
    )
    ctx["user"] = target_user
    ctx["user_ID"] = target_user.id
    ctx["user_id"] = effective_route_id
    ctx["embed_mode"] = embed_mode
    ctx["viewing_as_admin"] = effective_route_id != viewer_id
    ctx["breadcrumb"] = get_breadcrumb([
        {"text": "Dashboard", "url": reverse("app:dashboard")},
        {"text": "Combined Report", "url": ""},
    ])
    return ctx


def get_or_build_class10_combined_report_context(
    request,
    target_user,
    build_fn,
    *,
    route_user_id=None,
    embed_mode: bool = False,
):
    """
    Return Class 10 combined-report context, using Redis when available.

    On cache miss, uses a short lock to avoid stampede under load.
    """
    user_id = int(target_user.id)
    key = class10_combined_report_cache_key(user_id)

    try:
        cached = cache.get(key)
    except Exception:
        cached = None
        logger.exception("C10 combined report cache get failed for user %s", user_id)

    if cached is not None and isinstance(cached, dict):
        return _apply_viewer_overlay(
            dict(cached),
            request,
            target_user,
            route_user_id=route_user_id,
            embed_mode=embed_mode,
        )

    lock_key = class10_combined_report_lock_key(user_id)
    got_lock = False
    try:
        got_lock = cache.add(lock_key, "1", CLASS10_REPORT_LOCK_TTL)
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
                return _apply_viewer_overlay(
                    dict(cached),
                    request,
                    target_user,
                    route_user_id=route_user_id,
                    embed_mode=embed_mode,
                )

    context = build_fn(
        request,
        target_user,
        route_user_id=route_user_id,
        embed_mode=embed_mode,
    )

    if context and not context.get("no_results") and not context.get("error"):
        to_store = {k: v for k, v in context.items() if k not in _VIEWER_KEYS}
        try:
            cache.set(key, to_store, CLASS10_REPORT_CACHE_TTL)
        except Exception:
            logger.exception("Failed to cache C10 combined report for user %s", user_id)

    if got_lock:
        try:
            cache.delete(lock_key)
        except Exception:
            pass

    return _apply_viewer_overlay(
        context,
        request,
        target_user,
        route_user_id=route_user_id,
        embed_mode=embed_mode,
    )
