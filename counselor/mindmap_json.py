"""
Resolve counselor mindmap JSON files under static/counselor/mindmaps/.

Templates use {% static %} for URLs; this module checks filesystem existence via
staticfiles finders (and STATICFILES_DIRS in dev).
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.staticfiles import finders
from django.templatetags.static import static


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
