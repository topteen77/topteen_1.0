"""
Parent dashboard / catalog Redis cache.

Uses dedicated ``parents`` cache alias (Redis when ENABLE_REDIS) so payloads still
cache in DEBUG when default is DummyCache — same pattern as careers/roster.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Iterable, Optional

from django.core.cache import caches

logger = logging.getLogger(__name__)

PARENTS_CACHE_ALIAS = "parents"
PARENT_DASH_TTL = 120  # 2 minutes
PARENT_CATALOG_TTL = 120
PARENT_DASH_LOCK_TTL = 30
CACHE_VERSION = "v1"


def _parents_cache():
    try:
        return caches[PARENTS_CACHE_ALIAS]
    except Exception:
        from django.core.cache import cache

        return cache


def parent_dashboard_cache_key(parent_id: int) -> str:
    return f"parent:dash:payload:{CACHE_VERSION}:{int(parent_id)}"


def parent_dashboard_lock_key(parent_id: int) -> str:
    return f"parent:dash:lock:{CACHE_VERSION}:{int(parent_id)}"


def parent_catalog_cache_key(parent_id: int) -> str:
    return f"parent:catalog:payload:{CACHE_VERSION}:{int(parent_id)}"


def parent_mieq_cache_key(parent_id: int) -> str:
    return f"parent:mieq:{CACHE_VERSION}:{int(parent_id)}"


def parent_skilllab_suggest_cache_key(parent_id: int) -> str:
    return f"parent:skilllab_suggest:{CACHE_VERSION}:{int(parent_id)}"


def parent_report_html_cache_key(student_id: int, version: str = "v6") -> str:
    return f"parent_report_html:{version}:{int(student_id)}"


def get_cached_json(key: str) -> Optional[Any]:
    try:
        return _parents_cache().get(key)
    except Exception:
        logger.exception("parents cache get failed key=%s", key)
        return None


def set_cached_json(key: str, value: Any, ttl: int) -> None:
    try:
        _parents_cache().set(key, value, int(ttl))
    except Exception:
        logger.exception("parents cache set failed key=%s", key)


def delete_cached_keys(keys: Iterable[str]) -> None:
    c = _parents_cache()
    key_list = [k for k in keys if k]
    if not key_list:
        return
    try:
        c.delete_many(key_list)
    except Exception:
        for key in key_list:
            try:
                c.delete(key)
            except Exception:
                pass


def invalidate_parent_dashboard_cache(parent_id: int) -> None:
    """Drop all parent-dashboard related Redis keys for one parent."""
    pid = int(parent_id or 0)
    if not pid:
        return
    delete_cached_keys(
        [
            parent_dashboard_cache_key(pid),
            parent_catalog_cache_key(pid),
            parent_mieq_cache_key(pid),
            parent_skilllab_suggest_cache_key(pid),
            parent_dashboard_lock_key(pid),
            f"{parent_catalog_cache_key(pid)}:lock",
            f"{parent_mieq_cache_key(pid)}:lock",
            f"{parent_skilllab_suggest_cache_key(pid)}:lock",
        ]
    )
    # Clear any legacy fingerprint-suffixed MI/EQ keys if present.
    c = _parents_cache()
    if getattr(c, "delete_pattern", None):
        try:
            c.delete_pattern(f"*{parent_mieq_cache_key(pid)}*")
        except Exception:
            pass


def invalidate_parent_report_cache(student_id: int) -> None:
    """Drop cached assessment-report HTML for a student (parents Redis alias)."""
    sid = int(student_id or 0)
    if not sid:
        return
    delete_cached_keys(
        [
            parent_report_html_cache_key(sid, "v6"),
            parent_report_html_cache_key(sid, "v5"),
        ]
    )


def invalidate_parent_caches_for_student(student) -> None:
    """Invalidate every linked parent's dashboard caches for this student."""
    try:
        from users.models import ParentStudentLink

        student_id = int(getattr(student, "id", student) or 0)
        if student_id:
            invalidate_parent_report_cache(student_id)

        qs = ParentStudentLink.objects.filter(student_id=student_id) if student_id else (
            ParentStudentLink.objects.filter(student=student)
        )
        for pid in qs.values_list("parent_id", flat=True):
            if pid:
                invalidate_parent_dashboard_cache(pid)
    except Exception:
        logger.exception("Failed to invalidate parent caches for student")


def get_or_build_cached(
    key: str,
    build_fn: Callable[[], Any],
    *,
    ttl: int,
    lock_key: str = "",
    lock_ttl: int = PARENT_DASH_LOCK_TTL,
    validate: Optional[Callable[[Any], bool]] = None,
) -> Any:
    """
    Redis-first: return cached value if present; otherwise build, store, return.

    Optional lock reduces stampede when many parents hit a cold key together.
    """
    cached = get_cached_json(key)
    if cached is not None and (validate is None or validate(cached)):
        return cached

    acquired = False
    c = _parents_cache()
    if lock_key:
        try:
            acquired = bool(c.add(lock_key, 1, int(lock_ttl)))
        except Exception:
            acquired = False

    if lock_key and not acquired:
        # Another worker is building — brief wait then re-check Redis.
        for _ in range(8):
            time.sleep(0.05)
            cached = get_cached_json(key)
            if cached is not None and (validate is None or validate(cached)):
                return cached
        # Fall through and build ourselves.

    try:
        value = build_fn()
        if validate is None or validate(value):
            set_cached_json(key, value, ttl)
        return value
    finally:
        if acquired and lock_key:
            try:
                c.delete(lock_key)
            except Exception:
                pass


def get_or_build_parent_dashboard_payload(
    parent_id: int,
    build_fn: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    """Full parent dashboard JSON bundle (students + MI/EQ + skilllab suggestions)."""

    def _ok(val: Any) -> bool:
        return isinstance(val, dict) and "students_dashboard_payload" in val

    return get_or_build_cached(
        parent_dashboard_cache_key(parent_id),
        build_fn,
        ttl=PARENT_DASH_TTL,
        lock_key=parent_dashboard_lock_key(parent_id),
        validate=_ok,
    )


def get_or_build_parent_catalog_payload(
    parent_id: int,
    build_fn: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    def _ok(val: Any) -> bool:
        return isinstance(val, dict) and "sections" in val

    return get_or_build_cached(
        parent_catalog_cache_key(parent_id),
        build_fn,
        ttl=PARENT_CATALOG_TTL,
        lock_key=f"{parent_catalog_cache_key(parent_id)}:lock",
        validate=_ok,
    )
