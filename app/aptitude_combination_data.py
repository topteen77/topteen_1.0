"""Load Class 10 aptitude combination profiles from Excel-derived JSON."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings

ALL_REASONING_CODES = frozenset({'CR', 'NR', 'VR', 'LR', 'LA', 'SR', 'MR'})

DEFAULT_JSON_PATH = Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_aptitude_combinations.json'


def codes_to_key(codes: frozenset[str] | set[str]) -> str:
    """Sorted reasoning codes joined with '+', e.g. CR+NR+VR."""
    return '+'.join(sorted(codes))


@lru_cache(maxsize=1)
def _load_payload() -> dict[str, Any]:
    path = DEFAULT_JSON_PATH
    if not path.is_file():
        return {'combinations': {}, 'six_area_present_keys': {}}
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def lookup_combination_profile(codes: frozenset[str]) -> dict[str, Any] | None:
    """
    Return full combination row for a set of reasoning codes.

    Matches Sections 1–7 from the aptitude combinations Excel:
    - 1–5 codes: direct key lookup
    - 6 codes: present-code key
    - 7 codes: all-seven key
    """
    if not codes:
        return None

    payload = _load_payload()
    combinations: dict[str, dict[str, Any]] = payload.get('combinations') or {}

    key = codes_to_key(codes)
    if key in combinations:
        return dict(combinations[key])

    if len(codes) == 6:
        six_map: dict[str, str] = payload.get('six_area_present_keys') or {}
        missing = (ALL_REASONING_CODES - codes).pop()
        present_key = six_map.get(missing)
        if present_key and present_key in combinations:
            return dict(combinations[present_key])

    return None


def combination_profile_for_display(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize a combination profile dict for templates."""
    if not profile:
        return None
    return {
        'code': profile.get('code', ''),
        'section': profile.get('section'),
        'profile': profile.get('profile') or '',
        'strong_fit_stream': profile.get('strong_fit_stream') or '',
        'good_fit_stream': profile.get('good_fit_stream') or '',
        'strong_fit_careers': list(profile.get('strong_fit_careers') or []),
        'good_fit_careers': list(profile.get('good_fit_careers') or []),
        'strong_fit_subjects': list(profile.get('strong_fit_subjects') or []),
        'good_fit_subjects': list(profile.get('good_fit_subjects') or []),
    }
