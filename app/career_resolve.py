"""Resolve published Career records by display name for report guidance linking."""

from __future__ import annotations

import re

from core import choices


def _published_careers_qs():
    from careers.models import Career

    return Career.objects.filter(
        publish_status=choices.PublishStatus.PUBLISHED,
        object_status=choices.ObjectStatus.ACTIVE,
    )


def _normalize_name_key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', (name or '').lower()).strip()


def resolve_career_by_name(name: str):
    """Match a label to a published Career (exact name, then normalized, then single contains)."""
    raw = (name or '').strip()
    if not raw:
        return None

    qs = _published_careers_qs()
    career = qs.filter(name__iexact=raw).first()
    if career:
        return career

    norm = _normalize_name_key(raw)
    if norm:
        for candidate in qs.only('id', 'name', 'slug'):
            if _normalize_name_key(candidate.name) == norm:
                return candidate

    contains = list(qs.filter(name__icontains=raw)[:2])
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
