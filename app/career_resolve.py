"""Resolve published Career records by display name for report guidance linking."""

from __future__ import annotations

import re
import time

from core import choices


def _published_careers_qs():
    from careers.models import Career

    return Career.objects.filter(
        publish_status=choices.PublishStatus.PUBLISHED,
        object_status=choices.ObjectStatus.ACTIVE,
    )


def _normalize_name_key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', (name or '').lower()).strip()


# Report guidance resolves hundreds of career labels per build. Previously each
# unresolved label iterated the entire published-careers table (an N+1 that cost
# several seconds per report). Build an in-memory lookup index once and reuse it
# with a short TTL so admin changes still surface within a few minutes.
_NAME_INDEX_TTL_SECONDS = 300
_name_index_cache = {"exact": None, "norm": None, "ts": 0.0}


def clear_career_name_index_cache():
    _name_index_cache["exact"] = None
    _name_index_cache["norm"] = None
    _name_index_cache["ts"] = 0.0


def _career_name_index():
    now = time.monotonic()
    if _name_index_cache["exact"] is not None and (now - _name_index_cache["ts"]) < _NAME_INDEX_TTL_SECONDS:
        return _name_index_cache["exact"], _name_index_cache["norm"]

    exact = {}
    norm = {}
    for candidate in _published_careers_qs().only(
        'id', 'name', 'slug', 'publish_status', 'object_status'
    ):
        display = (candidate.name or '').strip()
        if not display:
            continue
        exact.setdefault(display.lower(), candidate)
        key = _normalize_name_key(display)
        if key:
            norm.setdefault(key, candidate)

    _name_index_cache["exact"] = exact
    _name_index_cache["norm"] = norm
    _name_index_cache["ts"] = now
    return exact, norm


def resolve_career_by_name(name: str):
    """Match a label to a published Career (exact name, then normalized, then single contains)."""
    raw = (name or '').strip()
    if not raw:
        return None

    exact_index, norm_index = _career_name_index()

    career = exact_index.get(raw.lower())
    if career:
        return career

    norm = _normalize_name_key(raw)
    if norm:
        career = norm_index.get(norm)
        if career:
            return career

    contains = list(_published_careers_qs().filter(name__icontains=raw)[:2])
    if len(contains) == 1:
        return contains[0]

    return None


def career_report_url(career) -> str | None:
    """Public career detail URL, or None if the career has no live page on the site."""
    if not career:
        return None
    if career.publish_status != choices.PublishStatus.PUBLISHED:
        return None
    if career.object_status != choices.ObjectStatus.ACTIVE:
        return None
    if not (career.slug or '').strip():
        return None
    try:
        return career.url()
    except Exception:
        return None


def career_report_entry(career=None, *, name: str | None = None) -> dict:
    """
    Report list item: always includes display name; url only when a published page exists.
    Pass career FK, or a label to resolve against the catalog when possible.
    """
    if career:
        return {
            'name': (career.name or '').strip(),
            'url': career_report_url(career),
        }
    label = (name or '').strip()
    if not label:
        return {'name': '', 'url': None}
    linked = resolve_career_by_name(label)
    if linked:
        return {
            'name': (linked.name or label).strip(),
            'url': career_report_url(linked),
        }
    return {'name': label, 'url': None}
