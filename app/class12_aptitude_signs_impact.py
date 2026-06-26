"""Helpers for Class 12 aptitude real-life signs and daily-life impact bullets."""
from __future__ import annotations

from typing import Any

from app.class12_aptitude_consolidated_io import split_bullet_list

CLASS12_REASONING_CODES = ('AR', 'NR', 'LR', 'LVR', 'CR', 'MR', 'SR')


def bullets_to_text(items: list[str] | None) -> str:
    return '\n'.join(str(item).strip() for item in (items or []) if str(item).strip())


def text_to_bullets(text: str | None) -> list[str]:
    if not text or not str(text).strip():
        return []
    if '•' in text or '\u2022' in text:
        return split_bullet_list(text)
    return split_bullet_list('\n'.join(line.strip() for line in str(text).splitlines() if line.strip()))


def areas_to_codes(area_names: list[str] | None) -> list[str]:
    from app.class12_aptitude_report_utils import map_aptitude_name_to_code
    from app_post_matric.aptitude_area_labels import resolve_aptitude_json_area

    codes: list[str] = []
    seen: set[str] = set()
    for area in area_names or []:
        code = map_aptitude_name_to_code(resolve_aptitude_json_area(area))
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def resolve_signs_and_impacts(
    consolidated_row: dict[str, Any] | None,
    *,
    codes: list[str] | None = None,
    aptitude_interpretation_data: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    """Resolve bullets from consolidated row; legacy JSON only as fallback."""
    from app.class12_aptitude_consolidated_io import (
        load_aptitude_interpretation_data,
        merge_legacy_signs_impact_for_codes,
    )

    row = consolidated_row or {}
    signs = [str(item).strip() for item in (row.get('real_life_signs') or []) if str(item).strip()]
    impacts = [str(item).strip() for item in (row.get('daily_life_impact') or []) if str(item).strip()]

    if signs and impacts:
        return signs, impacts

    lookup_codes = list(codes or row.get('codes') or [])
    if aptitude_interpretation_data is None:
        aptitude_interpretation_data = load_aptitude_interpretation_data()

    legacy_signs, legacy_impacts = merge_legacy_signs_impact_for_codes(
        lookup_codes,
        aptitude_interpretation_data,
    )
    if not signs:
        signs = legacy_signs
    if not impacts:
        impacts = legacy_impacts
    return signs, impacts
