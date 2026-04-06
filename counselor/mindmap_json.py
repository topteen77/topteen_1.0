"""
Resolve counselor mindmap JSON files under static/counselor/mindmaps/.

Templates use {% static %} for URLs; this module checks filesystem existence via
staticfiles finders (and STATICFILES_DIRS in dev).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from django.contrib.staticfiles import finders
from django.templatetags.static import static

# Process-local TTL cache for mindmap flags (DEBUG dev uses DummyCache — Django cache is a no-op).
_MINDMAP_FLAG_CACHE: dict[int, tuple[float, bool, dict[int, bool], dict[int, bool]]] = {}
_MINDMAP_FLAG_LOCK = threading.Lock()


def counselor_mindmaps_globally_enabled() -> bool:
    """Core Configuration ENABLE_COUNSELOR_COURSE_MINDMAP (default on)."""
    from core.models import Configuration

    try:
        v = Configuration.get("ENABLE_COUNSELOR_COURSE_MINDMAP", "true", editable=True)
    except Exception:
        return True
    return str(v).lower() in ("true", "1", "yes", "on")


def _relative_path(*parts: str) -> str:
    return "/".join(("counselor", "mindmaps", *parts))


def course_mindmap_relpath() -> str:
    return _relative_path("course.json")


def chapter_mindmap_relpath(chapter_id: int) -> str:
    return _relative_path(f"chapter_{int(chapter_id)}.json")


def part_mindmap_relpath(part_id: int) -> str:
    return _relative_path(f"part_{int(part_id)}.json")


def mindmap_json_file_exists(relative_static_path: str) -> bool:
    """True if staticfiles can find a real file at relative_static_path."""
    found = finders.find(relative_static_path)
    if found and Path(found).is_file():
        return True
    return False


def mindmap_json_valid(relative_static_path: str) -> bool:
    """True if file exists and parses as JSON (object or array)."""
    found = finders.find(relative_static_path)
    if not found or not Path(found).is_file():
        return False
    try:
        raw = Path(found).read_text(encoding="utf-8")
        json.loads(raw)
    except (OSError, ValueError, TypeError):
        return False
    return True


def mindmap_static_url(relative_static_path: str) -> str:
    return static(relative_static_path)


def course_mindmap_available(course) -> bool:
    from counselor.models import CounselorCourse

    if not counselor_mindmaps_globally_enabled():
        return False
    if not course or not isinstance(course, CounselorCourse):
        return False
    rel = course_mindmap_relpath()
    return mindmap_json_valid(rel)


def chapter_mindmap_available(chapter) -> bool:
    if not counselor_mindmaps_globally_enabled():
        return False
    if not chapter:
        return False
    pk = getattr(chapter, "pk", None)
    if not pk:
        return False
    rel = chapter_mindmap_relpath(pk)
    return mindmap_json_valid(rel)


def part_mindmap_available(part) -> bool:
    if not counselor_mindmaps_globally_enabled():
        return False
    if not part:
        return False
    pid = getattr(part, "pk", None)
    if not pid:
        return False
    return mindmap_json_valid(part_mindmap_relpath(pid))


def cached_course_chapter_part_mindmap_flags(course, chapters_list, *, ttl: int = 3600):
    """
    Return (course_has_mindmap, chapter_id -> bool, part_id -> bool).

    Without caching, each course learning request re-reads and json.loads every static
    mindmap file (chapter_*.json / part_*.json) — multi-second cost at scale.

    Uses a **process-local** TTL dict so it works when Django settings use DummyCache
    (typical DEBUG + DISABLE_CACHE_FOR_DEV). Also writes to Django cache when that backend
    is real (Redis/LocMem) so multiple workers can share entries.
    """
    if not counselor_mindmaps_globally_enabled():
        return False, {}, {}

    from counselor.models import CounselorCourse

    if not course or not isinstance(course, CounselorCourse):
        return False, {}, {}

    cid = int(course.id)
    now = time.time()

    with _MINDMAP_FLAG_LOCK:
        ent = _MINDMAP_FLAG_CACHE.get(cid)
        if ent is not None and (now - ent[0]) < ttl:
            return ent[1], ent[2], ent[3]

    try:
        from django.core.cache import cache

        key = f"counselor_mm_av:v2:{cid}"
        hit = cache.get(key)
        if isinstance(hit, dict) and "course" in hit and "chapters" in hit and "parts" in hit:
            course_ok = hit["course"]
            ch_f = hit["chapters"]
            part_f = hit["parts"]
            with _MINDMAP_FLAG_LOCK:
                _MINDMAP_FLAG_CACHE[cid] = (now, course_ok, ch_f, part_f)
            return course_ok, ch_f, part_f
    except Exception:
        pass

    course_ok = course_mindmap_available(course)
    ch_f = {}
    part_f = {}
    for ch in chapters_list:
        ch_f[ch.id] = chapter_mindmap_available(ch)
        for p in ch.parts.all():
            part_f[p.id] = part_mindmap_available(p)

    payload = {"course": course_ok, "chapters": ch_f, "parts": part_f}
    try:
        from django.core.cache import cache

        cache.set(f"counselor_mm_av:v2:{cid}", payload, ttl)
    except Exception:
        pass

    with _MINDMAP_FLAG_LOCK:
        _MINDMAP_FLAG_CACHE[cid] = (now, course_ok, ch_f, part_f)

    return course_ok, ch_f, part_f
