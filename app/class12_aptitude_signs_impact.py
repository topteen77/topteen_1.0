"""Master real-life signs and daily-life impact items for Class 12 aptitude reports."""
from __future__ import annotations

from typing import Any

from app.class12_aptitude_consolidated_io import (
    CODE_TO_INTERPRETATION_AREA,
    load_aptitude_interpretation_data,
    merge_legacy_signs_impact_for_codes,
)

CLASS12_REASONING_CODES = ('AR', 'NR', 'LR', 'LVR', 'CR', 'MR', 'SR')


def parse_code_list(raw: str | list[str] | None) -> list[str]:
    if isinstance(raw, list):
        items = raw
    else:
        text = (raw or '').strip()
        if not text:
            return []
        if '|' in text:
            items = text.split('|')
        elif ',' in text:
            items = text.split(',')
        else:
            items = text.split()
    order = {code: index for index, code in enumerate(CLASS12_REASONING_CODES)}
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        code = str(item).strip().upper()
        if code in order and code not in seen:
            seen.add(code)
            ordered.append(code)
    return sorted(ordered, key=order.get)


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


def _ordered_codes(codes: list[str] | None) -> list[str]:
    order = {code: index for index, code in enumerate(CLASS12_REASONING_CODES)}
    return sorted({code for code in (codes or []) if code in order}, key=order.get)


def _bullets_by_record_ids(
    model,
    ids: list[int] | None,
    allowed_codes: list[str] | None = None,
) -> list[str]:
    if not ids:
        return []
    queryset = model.objects.filter(pk__in=ids, is_active=True)
    if allowed_codes:
        queryset = queryset.filter(reasoning_code__in=allowed_codes)
    rows = {row.pk: row for row in queryset}
    bullets: list[str] = []
    for pk in ids:
        row = rows.get(pk)
        if not row:
            continue
        bullets.extend(row.bullet_list())
    return bullets


def _bullets_for_codes(model, codes: list[str] | None) -> list[str]:
    ordered = _ordered_codes(codes)
    if not ordered:
        return []
    rows = list(model.objects.filter(reasoning_code__in=ordered, is_active=True))
    code_rank = {code: index for index, code in enumerate(ordered)}
    rows.sort(key=lambda row: code_rank.get(row.reasoning_code, 99))
    bullets: list[str] = []
    for row in rows:
        bullets.extend(row.bullet_list())
    return bullets


def _db_lookup_signs_impacts(
    sign_ids: list[int],
    impact_ids: list[int],
    lookup_codes: list[str],
) -> tuple[list[str], list[str]]:
    try:
        from app.models import Class12AptitudeDailyLifeImpact, Class12AptitudeRealLifeSign

        signs = _bullets_by_record_ids(Class12AptitudeRealLifeSign, sign_ids, lookup_codes)
        impacts = _bullets_by_record_ids(Class12AptitudeDailyLifeImpact, impact_ids, lookup_codes)
        if not signs:
            signs = _bullets_for_codes(Class12AptitudeRealLifeSign, lookup_codes)
        if not impacts:
            impacts = _bullets_for_codes(Class12AptitudeDailyLifeImpact, lookup_codes)
        return signs, impacts
    except Exception:
        return [], []


def resolve_signs_and_impacts(
    consolidated_row: dict[str, Any] | None,
    *,
    codes: list[str] | None = None,
    aptitude_interpretation_data: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    """Resolve report bullets from master records, then legacy JSON."""
    row = consolidated_row or {}
    sign_ids = list(row.get('real_life_sign_ids') or [])
    impact_ids = list(row.get('daily_life_impact_ids') or [])
    row_codes = list(row.get('codes') or [])
    lookup_codes = _ordered_codes(codes or row_codes)

    signs, impacts = _db_lookup_signs_impacts(sign_ids, impact_ids, lookup_codes)

    if (not signs or not impacts) and aptitude_interpretation_data is None:
        aptitude_interpretation_data = load_aptitude_interpretation_data()

    if not signs or not impacts:
        legacy_signs, legacy_impacts = merge_legacy_signs_impact_for_codes(
            lookup_codes,
            aptitude_interpretation_data,
        )
        if not signs:
            signs = legacy_signs
        if not impacts:
            impacts = legacy_impacts

    return signs, impacts


def _items_text_from_legacy_list(items: list[Any] | None) -> str:
    return '\n'.join(str(item).strip() for item in (items or []) if str(item).strip())


def seed_master_signs_impact_from_legacy(*, overwrite: bool = False) -> dict[str, Any]:
    """Create one admin row per reasoning code with one textarea (one bullet per line)."""
    from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
    from app.models import Class12AptitudeDailyLifeImpact, Class12AptitudeRealLifeSign

    interpretation_data = load_aptitude_interpretation_data()
    if not interpretation_data:
        return {'ok': False, 'error': 'Legacy aptitude interpretation JSON not found.'}

    by_area = {
        item.get('Area'): item
        for item in interpretation_data.get('Aptitude_Interpretations', [])
        if item.get('Area')
    }

    sign_count = 0
    impact_count = 0
    for code in CLASS12_REASONING_CODES:
        area = CODE_TO_INTERPRETATION_AREA.get(code)
        interp = by_area.get(area) if area else None
        if not interp:
            continue

        sign_text = _items_text_from_legacy_list(interp.get('Real life signs'))
        impact_text = _items_text_from_legacy_list(interp.get('Daily life impact'))

        if sign_text:
            if overwrite:
                Class12AptitudeRealLifeSign.objects.update_or_create(
                    reasoning_code=code,
                    defaults={'items_text': sign_text, 'is_active': True},
                )
            elif not Class12AptitudeRealLifeSign.objects.filter(reasoning_code=code).exists():
                Class12AptitudeRealLifeSign.objects.create(
                    reasoning_code=code,
                    items_text=sign_text,
                    is_active=True,
                )
            sign_count += 1

        if impact_text:
            if overwrite:
                Class12AptitudeDailyLifeImpact.objects.update_or_create(
                    reasoning_code=code,
                    defaults={'items_text': impact_text, 'is_active': True},
                )
            elif not Class12AptitudeDailyLifeImpact.objects.filter(reasoning_code=code).exists():
                Class12AptitudeDailyLifeImpact.objects.create(
                    reasoning_code=code,
                    items_text=impact_text,
                    is_active=True,
                )
            impact_count += 1

    clear_consolidated_lookup_cache()
    return {'ok': True, 'sign_count': sign_count, 'impact_count': impact_count}


def codes_to_sign_impact_ids(
    sign_codes: list[str] | None,
    impact_codes: list[str] | None,
) -> tuple[list[int], list[int]]:
    from app.models import Class12AptitudeDailyLifeImpact, Class12AptitudeRealLifeSign

    sign_map = {
        row.reasoning_code: row.pk
        for row in Class12AptitudeRealLifeSign.objects.filter(is_active=True)
    }
    impact_map = {
        row.reasoning_code: row.pk
        for row in Class12AptitudeDailyLifeImpact.objects.filter(is_active=True)
    }
    sign_ids = [sign_map[code] for code in _ordered_codes(sign_codes) if code in sign_map]
    impact_ids = [impact_map[code] for code in _ordered_codes(impact_codes) if code in impact_map]
    return sign_ids, impact_ids


def build_sign_impact_ids_for_codes(codes: list[str] | None) -> tuple[list[int], list[int]]:
    return codes_to_sign_impact_ids(codes, codes)


def seed_consolidated_sign_impact_ids(
    queryset=None,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
    from app.models import Class12AptitudeConsolidatedReport

    rows = queryset if queryset is not None else Class12AptitudeConsolidatedReport.objects.all()
    count = 0
    for row in rows:
        if not overwrite and row.real_life_sign_ids and row.daily_life_impact_ids:
            continue
        sign_ids, impact_ids = build_sign_impact_ids_for_codes(list(row.codes or []))
        row.real_life_sign_ids = sign_ids
        row.daily_life_impact_ids = impact_ids
        row.save(update_fields=['real_life_sign_ids', 'daily_life_impact_ids', 'modified'])
        count += 1

    clear_consolidated_lookup_cache()
    return {'ok': True, 'count': count}
