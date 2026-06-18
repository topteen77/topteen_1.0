"""Load Class 10 stream sorter premium / future career guidance for reports."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from app.stream_sorter_unique_streams import (
    STREAM_CODES,
    _extract_stream_codes,
    build_unique_streams_payload,
)

DEFAULT_JSON_PATH = Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_stream_sorter_guidance.json'
UNIQUE_STREAMS_JSON_PATH = (
    Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_stream_sorter_unique_streams.json'
)


@lru_cache(maxsize=1)
def load_stream_sorter_guidance(path: str | None = None) -> dict:
    json_path = Path(path) if path else DEFAULT_JSON_PATH
    if not json_path.exists():
        return {}
    with json_path.open(encoding='utf-8') as handle:
        return json.load(handle)


def _letter_for_category_code(payload: dict, category_code: str) -> str | None:
    code = (category_code or '').strip().upper()
    if not code:
        return None
    mapping = payload.get('category_code_to_letter') or {}
    if code in mapping:
        return mapping[code]
    if len(code) >= 1 and code[0] in 'RIASEC':
        return code[0]
    return None


def get_stream_sorter_guidance_for_category(category_code: str, path: str | None = None) -> dict | None:
    """
    Return stream-wise and future-relevant career blocks for a personality category code (e.g. ASE).
    """
    payload = load_stream_sorter_guidance(path)
    if not payload:
        return None

    letter = _letter_for_category_code(payload, category_code)
    if not letter:
        return None

    for file_data in (payload.get('files') or {}).values():
        if file_data.get('riasec_letter') == letter:
            return {
                'category_code': category_code.strip().upper(),
                'riasec_letter': letter,
                'heading': file_data.get('heading') or '',
                'stream_wise_title': (payload.get('section_titles') or {}).get('stream_wise', ''),
                'future_relevant_title': (payload.get('section_titles') or {}).get('future_relevant', ''),
                'stream_wise_premium_careers': file_data.get('stream_wise_premium_careers') or [],
                'future_relevant_careers': file_data.get('future_relevant_careers') or [],
            }
    return None


def get_stream_sorter_guidance_for_top_category(top_category) -> dict | None:
    """Accept Category model instance or category code string."""
    if not top_category:
        return None
    if hasattr(top_category, 'category'):
        code = getattr(top_category, 'category', None)
    else:
        code = str(top_category)
    return get_stream_sorter_guidance_for_category(code)


def _normalize_career_entry(item) -> dict:
    if isinstance(item, dict):
        return {
            'name': (item.get('name') or '').strip(),
            'url': item.get('url') or None,
        }
    return {'name': str(item).strip(), 'url': None}


def _enrich_career_entry(item) -> dict:
    """Keep every career name; add url only when a published site page exists."""
    from app.career_resolve import career_report_entry

    entry = _normalize_career_entry(item)
    if not entry['name']:
        return entry
    if entry.get('url'):
        return entry
    return career_report_entry(name=entry['name'])


def _normalize_catalog_career_entries(catalog: dict) -> dict:
    for group in catalog.get('stream_wise_premium_careers') or []:
        group['careers'] = [
            _enrich_career_entry(c) for c in (group.get('careers') or [])
        ]
    catalog['future_relevant_careers'] = [
        _enrich_career_entry(c) for c in (catalog.get('future_relevant_careers') or [])
    ]
    return catalog


def clear_stream_sorter_guidance_cache():
    load_unique_streams_catalog.cache_clear()
    load_catalog_from_database.cache_clear()


@lru_cache(maxsize=1)
def load_catalog_from_database() -> dict | None:
    """Active career guidance from admin-managed models (combined report source of truth)."""
    from app.models import (
        Class10FutureRelevantCareer,
        Class10PremiumStream,
        Class10ReportGuidanceSettings,
    )

    from app.career_resolve import career_report_entry

    streams = (
        Class10PremiumStream.objects.filter(is_active=True)
        .prefetch_related('careers__career')
        .order_by('sort_order', 'stream_code')
    )
    if not streams.exists():
        return None

    settings = Class10ReportGuidanceSettings.get_solo()
    stream_groups = []
    for stream in streams:
        career_entries = []
        for row in stream.careers.filter(is_active=True).select_related('career').order_by('sort_order'):
            if row.career_id:
                career_entries.append(career_report_entry(row.career))
            elif (row.career_name or '').strip():
                career_entries.append(career_report_entry(name=row.career_name))
        if not career_entries:
            continue
        stream_groups.append({
            'stream': stream.display_label,
            'stream_code': stream.stream_code,
            'careers': career_entries,
        })

    future_careers = []
    for row in (
        Class10FutureRelevantCareer.objects.filter(is_active=True)
        .select_related('career')
        .order_by('sort_order')
    ):
        if row.career_id:
            future_careers.append(career_report_entry(row.career))
        elif (row.career_name or '').strip():
            future_careers.append(career_report_entry(name=row.career_name))

    return {
        'source': 'database',
        'section_titles': {
            'stream_wise': settings.stream_wise_title,
            'future_relevant': settings.future_relevant_title,
        },
        'stream_wise_premium_careers': stream_groups,
        'future_relevant_careers': future_careers,
        'stats': {
            'unique_streams': len(stream_groups),
            'unique_future_relevant_careers': len(future_careers),
        },
    }


def _catalog_from_json_file(path: str | None = None) -> dict:
    json_path = Path(path) if path else UNIQUE_STREAMS_JSON_PATH
    if json_path.exists():
        with json_path.open(encoding='utf-8') as handle:
            data = json.load(handle)
            data['source'] = 'json_file'
            return data
    return build_unique_streams_payload(DEFAULT_JSON_PATH)


@lru_cache(maxsize=1)
def load_unique_streams_catalog(path: str | None = None) -> dict:
    """DB catalog first, then class10_stream_sorter_unique_streams.json fallback."""
    db_catalog = load_catalog_from_database()
    if db_catalog and db_catalog.get('stream_wise_premium_careers'):
        return _normalize_catalog_career_entries(db_catalog)
    payload = _catalog_from_json_file(path)
    if payload.get('stream_wise_premium_careers'):
        payload['source'] = payload.get('source', 'json_file')
        return _normalize_catalog_career_entries(payload)
    return payload


def _stream_code_from_label(stream_label: str) -> str:
    codes = _extract_stream_codes(stream_label)
    if not codes:
        return ''
    for code in ('PCM', 'PCB', 'CWM', 'CWOM', 'HUM', 'FINEARTS'):
        if code in codes:
            return code
    return sorted(codes)[0]


def import_catalog_from_json_file(
    *,
    json_path: Path | None = None,
    replace: bool = False,
) -> dict:
    """
    Load admin models from unique streams JSON (used by admin import action / management command).
    """
    from app.models import (
        Class10FutureRelevantCareer,
        Class10PremiumStream,
        Class10PremiumStreamCareer,
        Class10ReportGuidanceSettings,
    )

    path = json_path or UNIQUE_STREAMS_JSON_PATH
    if not path.exists():
        return {'ok': False, 'error': f'File not found: {path}'}

    with path.open(encoding='utf-8') as handle:
        data = json.load(handle)

    clear_stream_sorter_guidance_cache()

    if replace:
        Class10PremiumStreamCareer.objects.all().delete()
        Class10PremiumStream.objects.all().delete()
        Class10FutureRelevantCareer.objects.all().delete()

    settings = Class10ReportGuidanceSettings.get_solo()
    titles = data.get('section_titles') or {}
    if titles.get('stream_wise'):
        settings.stream_wise_title = titles['stream_wise']
    if titles.get('future_relevant'):
        settings.future_relevant_title = titles['future_relevant']
    settings.save()

    stream_count = 0
    career_count = 0
    for order, group in enumerate(data.get('stream_wise_premium_careers') or []):
        label = (group.get('stream') or '').strip()
        if not label:
            continue
        code = _stream_code_from_label(label) or f'STREAM_{order}'
        stream, _ = Class10PremiumStream.objects.update_or_create(
            stream_code=code,
            defaults={
                'display_label': label,
                'sort_order': order,
                'is_active': True,
            },
        )
        stream_count += 1
        if replace:
            stream.careers.all().delete()
        from app.career_resolve import resolve_career_by_name

        for c_order, name in enumerate(group.get('careers') or []):
            name = (name or '').strip()
            if not name:
                continue
            linked = resolve_career_by_name(name)
            if linked:
                Class10PremiumStreamCareer.objects.update_or_create(
                    stream=stream,
                    career=linked,
                    defaults={
                        'career_name': linked.name,
                        'sort_order': c_order,
                        'is_active': True,
                    },
                )
            else:
                Class10PremiumStreamCareer.objects.update_or_create(
                    stream=stream,
                    career_name=name,
                    defaults={
                        'career': None,
                        'sort_order': c_order,
                        'is_active': True,
                    },
                )
            career_count += 1

    future_count = 0
    for order, name in enumerate(data.get('future_relevant_careers') or []):
        name = (name or '').strip()
        if not name:
            continue
        linked = resolve_career_by_name(name)
        if linked:
            Class10FutureRelevantCareer.objects.update_or_create(
                career=linked,
                defaults={
                    'career_name': linked.name,
                    'sort_order': order,
                    'is_active': True,
                },
            )
        else:
            Class10FutureRelevantCareer.objects.update_or_create(
                career_name=name,
                defaults={
                    'career': None,
                    'sort_order': order,
                    'is_active': True,
                },
            )
        future_count += 1

    clear_stream_sorter_guidance_cache()
    return {
        'ok': True,
        'streams': stream_count,
        'stream_careers': career_count,
        'future_careers': future_count,
    }


def _recommended_stream_names(streamsubject) -> list[str]:
    names = []
    if not streamsubject:
        return names
    for item in streamsubject:
        if isinstance(item, (tuple, list)) and item:
            names.append(str(item[0]).strip())
        elif isinstance(item, str):
            names.append(item.strip())
    return [n for n in names if n]


def _recommended_stream_codes(streamsubject) -> set[str]:
    codes: set[str] = set()
    for name in _recommended_stream_names(streamsubject):
        codes.update(_extract_stream_codes(name))
    return codes


def _stream_group_matches_codes(stream_label: str, codes: set[str]) -> bool:
    if not codes:
        return False
    group_codes = _extract_stream_codes(stream_label)
    return bool(group_codes.intersection(codes))


def _stream_group_key(group: dict) -> str:
    code = (group.get('stream_code') or '').strip().upper()
    if code:
        return code
    return (group.get('stream') or '').strip()


def _group_stream_code(group: dict) -> str:
    """Canonical stream code (PCM, HUM, …) for a catalogue group."""
    code = (group.get('stream_code') or '').strip().upper()
    if code:
        return code
    codes = _extract_stream_codes(group.get('stream', ''))
    if codes:
        return sorted(codes)[0]
    return ''


def _report_streams_catalog(catalog_path: str | None = None) -> dict:
    """
    Full stream catalogue for the combined report (always all standard streams).

    JSON provides every stream block; DB overrides careers (with URLs) per stream_code
    when admin data exists. Fixes partial DB seed (e.g. only PCM) hiding View more.
    """
    json_catalog = _normalize_catalog_career_entries(_catalog_from_json_file(catalog_path))
    db_catalog = load_catalog_from_database()
    if not db_catalog or not db_catalog.get('stream_wise_premium_careers'):
        return json_catalog

    db_by_code = {}
    for group in db_catalog.get('stream_wise_premium_careers') or []:
        code = _group_stream_code(group)
        if code:
            db_by_code[code] = group

    merged_groups = []
    for group in json_catalog.get('stream_wise_premium_careers') or []:
        code = _group_stream_code(group)
        if code and code in db_by_code:
            db_group = db_by_code[code]
            merged_groups.append({
                'stream': db_group.get('stream') or group.get('stream'),
                'stream_code': code,
                'careers': db_by_code[code].get('careers') or group.get('careers') or [],
            })
        else:
            merged_groups.append({
                'stream': group.get('stream'),
                'stream_code': code or group.get('stream_code'),
                'careers': group.get('careers') or [],
            })

    merged = dict(json_catalog)
    merged['stream_wise_premium_careers'] = merged_groups
    merged['section_titles'] = db_catalog.get('section_titles') or json_catalog.get('section_titles') or {}
    if db_catalog.get('future_relevant_careers'):
        merged['future_relevant_careers'] = db_catalog['future_relevant_careers']
    merged['source'] = 'merged'
    merged['stats'] = {
        'unique_streams': len(merged_groups),
        'unique_future_relevant_careers': len(merged.get('future_relevant_careers') or []),
    }
    return merged


def _other_stream_groups(all_groups: list[dict], recommended_groups: list[dict]) -> list[dict]:
    """Catalogue stream blocks not in the student's recommended set."""
    recommended_keys = {_stream_group_key(group) for group in recommended_groups}
    return [group for group in all_groups if _stream_group_key(group) not in recommended_keys]


def _normalize_streamsubject(streamsubject):
    if not streamsubject:
        return []
    items = list(streamsubject)
    return sorted(
        items,
        key=lambda item: (
            str(item[0]).strip().upper()
            if isinstance(item, (tuple, list)) and item
            else str(item).strip().upper()
        ),
    )


def _order_groups_by_streamsubject(groups: list[dict], streamsubject) -> list[dict]:
    """Keep filtered groups in the same order as the student's stream suggestions."""
    if not groups or not streamsubject:
        return groups
    ordered: list[dict] = []
    used: set[int] = set()
    for item in streamsubject:
        if isinstance(item, (tuple, list)) and item:
            name = str(item[0]).strip()
        else:
            name = str(item).strip()
        if not name:
            continue
        codes = _extract_stream_codes(name)
        for group in groups:
            group_id = id(group)
            if group_id in used:
                continue
            if codes and _stream_group_matches_codes(group.get('stream', ''), codes):
                ordered.append(group)
                used.add(group_id)
                break
            stream_label = str(group.get('stream') or '').lower()
            if name.lower() in stream_label or stream_label in name.lower():
                ordered.append(group)
                used.add(group_id)
                break
    for group in groups:
        if id(group) not in used:
            ordered.append(group)
    return ordered


def filter_stream_wise_for_student(
    streamsubject,
    catalog: dict | None = None,
    *,
    show_all_streams: bool = False,
) -> tuple[list[dict], str, list[str]]:
    """
    Filter canonical stream-wise careers to the student's suggested stream(s).

    Returns (groups, filter_mode, recommended_stream_names).
    filter_mode: 'recommended' | 'all'
    - One suggested stream (e.g. PCM) → one block
    - Two streams (e.g. HUM + CWM) → two blocks
    - Combined label (e.g. PCM / PCB) → both PCM and PCB blocks
    - show_all_streams or no suggestions → all streams in catalog
    """
    catalog = catalog or _report_streams_catalog()
    all_groups = list(catalog.get('stream_wise_premium_careers') or [])
    original_streamsubject = list(streamsubject or [])
    streamsubject = _normalize_streamsubject(streamsubject)
    recommended_names = _recommended_stream_names(streamsubject)
    codes = _recommended_stream_codes(streamsubject)

    if show_all_streams or not codes:
        return all_groups, 'all', recommended_names

    filtered = [
        group for group in all_groups
        if _stream_group_matches_codes(group.get('stream', ''), codes)
    ]
    if filtered:
        filtered = _order_groups_by_streamsubject(filtered, original_streamsubject)
        return filtered, 'recommended', recommended_names

    # Fallback: label match when codes failed (e.g. non-standard stream name)
    filtered = []
    for group in all_groups:
        stream_label = group.get('stream', '')
        if any(
            name.lower() in stream_label.lower() or stream_label.lower() in name.lower()
            for name in recommended_names
        ):
            filtered.append(group)
    if filtered:
        filtered = _order_groups_by_streamsubject(filtered, original_streamsubject)
        return filtered, 'recommended', recommended_names

    return all_groups, 'all', recommended_names


def verify_streams_catalog_coverage(
    catalog: dict | None = None,
    *,
    include_db_streams: bool = True,
) -> dict:
    """
    Check that every stream suggested in DB can be mapped to the unique streams JSON.
    """
    catalog = catalog or load_unique_streams_catalog()
    json_codes = set()
    for group in catalog.get('stream_wise_premium_careers') or []:
        json_codes.update(_extract_stream_codes(group.get('stream', '')))

    report = {
        'json_stream_labels': [g.get('stream') for g in catalog.get('stream_wise_premium_careers') or []],
        'json_stream_codes': sorted(json_codes),
        'expected_codes': list(STREAM_CODES),
        'missing_standard_codes': sorted(set(STREAM_CODES) - json_codes),
        'db_streams': [],
        'db_unmapped': [],
        'ok': True,
    }

    if report['missing_standard_codes']:
        report['ok'] = False

    if include_db_streams:
        from app.models import Stream

        for name in sorted({s.stream_name.strip() for s in Stream.objects.all() if s.stream_name}):
            codes = _extract_stream_codes(name)
            mapped = bool(codes and codes.intersection(json_codes))
            entry = {'stream_name': name, 'codes': sorted(codes), 'mapped': mapped}
            report['db_streams'].append(entry)
            if codes and not mapped:
                report['db_unmapped'].append(name)
                report['ok'] = False

    return report


def build_report_stream_guidance(
    streamsubject,
    *,
    show_all_streams: bool = False,
    top_category=None,
    catalog_path: str | None = None,
) -> dict | None:
    """
    Build combined-report appendix from unique streams JSON, filtered by suggested streams.
    """
    catalog = _report_streams_catalog(catalog_path)
    all_groups = list(catalog.get('stream_wise_premium_careers') or [])
    if not all_groups:
        return None

    original_streamsubject = list(streamsubject or [])
    streamsubject = _normalize_streamsubject(streamsubject)
    groups, filter_mode, recommended_names = filter_stream_wise_for_student(
        original_streamsubject,
        catalog,
        show_all_streams=show_all_streams,
    )
    if filter_mode == 'recommended':
        recommended_names = _recommended_stream_names(original_streamsubject)
    other_groups = (
        _other_stream_groups(all_groups, groups)
        if filter_mode == 'recommended' and not show_all_streams
        else []
    )
    has_other_streams = bool(other_groups)
    show_other_streams_toggle = (
        filter_mode == 'recommended'
        and not show_all_streams
        and len(all_groups) > len(groups)
    )
    titles = catalog.get('section_titles') or {}
    personality_code = ''
    if top_category is not None:
        personality_code = getattr(top_category, 'category', None) or str(top_category or '')

    if filter_mode == 'recommended' and recommended_names:
        intro = (
            f'Premium career options for your suggested '
            f'stream{"s" if len(recommended_names) != 1 else ""}: '
            f'{", ".join(recommended_names)}.'
        )
    else:
        intro = (
            'Premium career options across all subject streams. '
            'Compare pathways aligned with your Stream Sorter profile.'
        )

    hero_image = catalog.get('hero_image') or 'images_new/careers/preimum-img.svg'

    return {
        'hero_image': hero_image,
        'stream_wise_title': titles.get('stream_wise', 'Stream-Wise Premium Career Options'),
        'future_relevant_title': titles.get(
            'future_relevant',
            'Most Future-Relevant Careers Across All Streams',
        ),
        'stream_wise_premium_careers': groups,
        'stream_wise_other_careers': other_groups,
        'has_other_streams': has_other_streams,
        'show_other_streams_toggle': show_other_streams_toggle,
        'other_streams_count': len(other_groups),
        'future_relevant_careers': catalog.get('future_relevant_careers') or [],
        'filter_mode': filter_mode,
        'recommended_streams': recommended_names,
        'streams_shown_count': len(groups),
        'streams_total_count': len(all_groups),
        'personality_code': personality_code.strip().upper() if personality_code else '',
        'integration_intro': intro,
        'catalog_stats': catalog.get('stats') or {},
        'data_source': catalog.get('source', 'unknown'),
    }

