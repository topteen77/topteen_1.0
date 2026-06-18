"""
Stream recommendations for class 10 psychometric (test3) intelligence reports.

Uses the corrected master combination tables (sections 1–7) with weighted
scoring (section 8) as fallback when no exact combination match exists.

Display mode is configurable in Admin → Psychometric Test Settings
(CLASS10_APTITUDE_STREAM_DISPLAY_MODE).
"""
from __future__ import annotations

from typing import Any

from core.choices import (
    CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY,
    CLASS10_APTITUDE_STREAM_MODE_COMBINED,
    CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
)

# DB / report area keys → short reasoning codes
AREA_TO_CODE = {
    'CRITICAL': 'CR',
    'EMOTIONAL': 'CR',  # emotional subtest scores as critical reasoning
    'NUMERICAL': 'NR',
    'VERBAL': 'VR',
    'LOGICAL': 'LR',
    'LANGUAGE': 'LA',
    'SPATIAL': 'SR',
    'MECHANICAL': 'MR',
}

ALL_REASONING_CODES = frozenset({'CR', 'NR', 'VR', 'LR', 'LA', 'SR', 'MR'})

ALL_SEVEN_NOTE = (
    'This profile demonstrates well-rounded aptitude across all reasoning domains. '
    'Stream selection should be guided primarily by interests, personality, '
    'career aspirations and academic performance rather than aptitude limitations.'
)

# UI metadata (display code may differ from internal stream key)
STREAM_UI = {
    'PCM': {
        'display': 'PCM',
        'description': 'Physics, Chemistry, Mathematics',
        'icon': 'pcm-icon.png',
    },
    'PCB': {
        'display': 'PCB',
        'description': 'Physics, Chemistry, Biology',
        'icon': 'pcb-icon.png',
    },
    'CWM': {
        'display': 'CWM',
        'description': 'Commerce with Mathematics',
        'icon': 'cwm-icon.png',
    },
    'CWOM': {
        'display': 'CWOM',
        'description': 'Commerce without Mathematics',
        'icon': 'cwm-icon.png',
    },
    'HUM-L': {
        'display': 'HUM-L',
        'description': 'Humanities with Language',
        'icon': 'hwl-icon.png',
    },
    'HUM-NL': {
        'display': 'HUM-NL',
        'description': 'Humanities without Language',
        'icon': 'hum-icon.png',
    },
    'Fine Arts': {
        'display': 'Fine Arts',
        'description': 'Fine Arts',
        'icon': 'fine-art-icon.png',
    },
}


def _combo(*codes: str) -> frozenset[str]:
    return frozenset(codes)


# Sections 1–5: exact combination → (primary, secondary)
COMBO_LOOKUP: dict[frozenset[str], tuple[str, str]] = {
    # Section 1 — single reasoning areas
    _combo('CR'): ('HUM-NL', 'CWOM'),
    _combo('NR'): ('PCM', 'CWM'),
    _combo('VR'): ('HUM-L', 'CWOM'),
    _combo('LR'): ('PCM', 'HUM-NL'),
    _combo('LA'): ('HUM-L', 'CWOM'),
    _combo('SR'): ('Fine Arts', 'PCM'),
    _combo('MR'): ('PCM', 'PCB'),
    # Section 2 — pairs
    _combo('CR', 'NR'): ('CWM', 'PCM'),
    _combo('CR', 'VR'): ('HUM-NL', 'HUM-L'),
    _combo('CR', 'LR'): ('HUM-NL', 'HUM-L'),
    _combo('CR', 'LA'): ('HUM-L', 'CWOM'),
    _combo('CR', 'SR'): ('Fine Arts', 'HUM-NL'),
    _combo('CR', 'MR'): ('PCB', 'PCM'),
    _combo('NR', 'VR'): ('CWM', 'CWOM'),
    _combo('NR', 'LR'): ('PCM', 'CWM'),
    _combo('NR', 'LA'): ('HUM-L', 'CWM'),
    _combo('NR', 'SR'): ('PCM', 'Fine Arts'),
    _combo('NR', 'MR'): ('PCM', 'PCB'),
    _combo('VR', 'LR'): ('HUM-L', 'HUM-NL'),
    _combo('VR', 'LA'): ('HUM-L', 'CWOM'),
    _combo('VR', 'SR'): ('Fine Arts', 'HUM-L'),
    _combo('VR', 'MR'): ('PCB', 'PCM'),
    _combo('LR', 'LA'): ('HUM-L', 'HUM-NL'),
    _combo('LR', 'SR'): ('PCM', 'Fine Arts'),
    _combo('LR', 'MR'): ('PCM', 'PCB'),
    _combo('LA', 'SR'): ('Fine Arts', 'HUM-L'),
    _combo('LA', 'MR'): ('CWOM', 'HUM-L'),
    _combo('SR', 'MR'): ('PCM', 'Fine Arts'),
    # Section 3 — triples
    _combo('CR', 'NR', 'LR'): ('CWM', 'PCM'),
    _combo('CR', 'NR', 'VR'): ('CWM', 'CWOM'),
    _combo('CR', 'NR', 'SR'): ('PCM', 'Fine Arts'),
    _combo('CR', 'NR', 'MR'): ('PCM', 'PCB'),
    _combo('CR', 'VR', 'LA'): ('HUM-L', 'CWOM'),
    _combo('CR', 'VR', 'LR'): ('HUM-L', 'HUM-NL'),
    _combo('CR', 'VR', 'SR'): ('Fine Arts', 'HUM-L'),
    _combo('CR', 'VR', 'MR'): ('PCB', 'PCM'),
    _combo('CR', 'LA', 'SR'): ('Fine Arts', 'HUM-L'),
    _combo('CR', 'LR', 'SR'): ('Fine Arts', 'PCM'),
    _combo('CR', 'LR', 'MR'): ('PCM', 'PCB'),
    _combo('NR', 'LR', 'SR'): ('PCM', 'Fine Arts'),
    _combo('NR', 'LR', 'MR'): ('PCM', 'PCB'),
    _combo('NR', 'SR', 'MR'): ('PCM', 'Fine Arts'),
    _combo('NR', 'VR', 'LA'): ('CWM', 'HUM-L'),
    _combo('VR', 'LA', 'SR'): ('Fine Arts', 'HUM-L'),
    _combo('VR', 'LA', 'LR'): ('HUM-L', 'HUM-NL'),
    _combo('VR', 'LR', 'SR'): ('Fine Arts', 'HUM-NL'),
    _combo('LR', 'SR', 'MR'): ('PCM', 'Fine Arts'),
    _combo('CR', 'NR', 'LA'): ('CWM', 'HUM-L'),
    _combo('CR', 'LA', 'LR'): ('HUM-L', 'HUM-NL'),
    _combo('NR', 'VR', 'MR'): ('CWM', 'PCB'),
    _combo('NR', 'LR', 'VR'): ('CWM', 'PCM'),
    _combo('VR', 'SR', 'MR'): ('Fine Arts', 'PCB'),
    _combo('LR', 'LA', 'MR'): ('PCM', 'HUM-L'),
    # Section 4 — quads
    _combo('NR', 'LR', 'SR', 'MR'): ('PCM', 'PCB'),
    _combo('NR', 'CR', 'LR', 'VR'): ('CWM', 'PCM'),
    _combo('CR', 'VR', 'LA', 'LR'): ('HUM-L', 'HUM-NL'),
    _combo('CR', 'VR', 'LA', 'SR'): ('Fine Arts', 'HUM-L'),
    _combo('CR', 'VR', 'LA', 'MR'): ('PCB', 'HUM-L'),
    _combo('CR', 'LR', 'VR', 'SR'): ('Fine Arts', 'HUM-NL'),
    _combo('CR', 'NR', 'LR', 'SR'): ('PCM', 'CWM'),
    _combo('CR', 'NR', 'LR', 'MR'): ('PCM', 'PCB'),
    _combo('CR', 'NR', 'VR', 'LA'): ('CWM', 'HUM-L'),
    _combo('NR', 'VR', 'LA', 'SR'): ('Fine Arts', 'CWM'),
    _combo('NR', 'LR', 'VR', 'LA'): ('CWM', 'HUM-L'),
    _combo('NR', 'SR', 'MR', 'LR'): ('PCM', 'Fine Arts'),
    _combo('VR', 'LA', 'SR', 'MR'): ('Fine Arts', 'HUM-L'),
    _combo('LR', 'SR', 'MR', 'NR'): ('PCM', 'Fine Arts'),
    _combo('CR', 'LR', 'MR', 'SR'): ('PCM', 'PCB'),
    _combo('CR', 'VR', 'LR', 'MR'): ('HUM-NL', 'PCB'),
    # Section 5 — five areas
    _combo('CR', 'NR', 'VR', 'LR', 'LA'): ('CWM', 'HUM-L'),
    _combo('CR', 'NR', 'VR', 'LR', 'SR'): ('PCM', 'CWM'),
    _combo('CR', 'NR', 'VR', 'LR', 'MR'): ('PCM', 'PCB'),
    _combo('CR', 'NR', 'VR', 'LA', 'SR'): ('Fine Arts', 'CWM'),
    _combo('CR', 'NR', 'VR', 'LA', 'MR'): ('PCB', 'CWM'),
    _combo('CR', 'NR', 'LR', 'SR', 'MR'): ('PCM', 'PCB'),
    _combo('CR', 'VR', 'LR', 'LA', 'SR'): ('HUM-L', 'Fine Arts'),
    _combo('CR', 'VR', 'LR', 'LA', 'MR'): ('HUM-NL', 'PCB'),
    _combo('CR', 'VR', 'LA', 'SR', 'MR'): ('Fine Arts', 'HUM-L'),
    _combo('NR', 'VR', 'LR', 'LA', 'SR'): ('CWM', 'Fine Arts'),
    _combo('NR', 'VR', 'LR', 'LA', 'MR'): ('CWM', 'PCB'),
    _combo('NR', 'VR', 'LR', 'SR', 'MR'): ('PCM', 'CWM'),
    _combo('NR', 'LA', 'LR', 'SR', 'MR'): ('PCM', 'Fine Arts'),
    _combo('CR', 'LA', 'LR', 'SR', 'MR'): ('PCM', 'Fine Arts'),
    _combo('CR', 'NR', 'LA', 'SR', 'MR'): ('PCM', 'Fine Arts'),
    _combo('VR', 'LA', 'LR', 'SR', 'MR'): ('Fine Arts', 'HUM-L'),
    _combo('CR', 'NR', 'LR', 'VR', 'SR'): ('PCM', 'CWM'),
    _combo('NR', 'VR', 'LA', 'SR', 'MR'): ('Fine Arts', 'CWM'),
    _combo('CR', 'NR', 'VR', 'SR', 'MR'): ('PCM', 'Fine Arts'),
    _combo('CR', 'LR', 'LA', 'VR', 'SR'): ('HUM-L', 'Fine Arts'),
}

# Section 6 — six areas present (key = missing reasoning code)
SIX_AREA_LOOKUP: dict[str, tuple[str, str]] = {
    'CR': ('PCM', 'Fine Arts'),       # missing CR
    'NR': ('HUM-L', 'Fine Arts'),     # missing NR
    'VR': ('PCM', 'CWM'),             # missing VR
    'LR': ('PCB', 'Fine Arts'),        # missing LR
    'LA': ('PCM', 'CWM'),             # missing LA
    'SR': ('CWM', 'PCB'),             # missing SR
    'MR': ('CWM', 'HUM-L'),           # missing MR
}

# Section 7 — all seven areas
ALL_SEVEN_STREAMS = ('PCM', 'CWM')

# Section 8 — weighted scoring keys per stream
STREAM_WEIGHT_KEYS: dict[str, list[str]] = {
    'PCM': ['NR', 'LR', 'SR', 'MR'],
    'PCB': ['CR', 'LR', 'NR', 'MR'],
    'CWM': ['NR', 'CR', 'LR', 'VR'],
    'CWOM': ['CR', 'VR', 'LA'],
    'HUM-L': ['CR', 'VR', 'LA', 'LR'],
    'HUM-NL': ['CR', 'LR', 'VR'],
    'Fine Arts': ['SR', 'VR', 'LA', 'CR'],
}

STREAM_RANK_ALL_SEVEN = ['PCM', 'CWM', 'HUM-L', 'PCB', 'Fine Arts', 'HUM-NL', 'CWOM']


def areas_to_codes(areas: list[str]) -> frozenset[str]:
    """Convert report area labels to short reasoning codes."""
    codes: set[str] = set()
    for area in areas or []:
        key = str(area or '').upper().strip()
        code = AREA_TO_CODE.get(key)
        if code:
            codes.add(code)
    return frozenset(codes)


def get_aptitude_stream_display_mode() -> str:
    """Read class 10 aptitude stream display mode from Configuration."""
    try:
        from core.models import Configuration

        raw = Configuration.get(
            CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY,
            default=CLASS10_APTITUDE_STREAM_MODE_COMBINED,
            editable=True,
        )
        mode = str(raw or '').strip().lower()
        if mode in (CLASS10_APTITUDE_STREAM_MODE_COMBINED, CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY):
            return mode
    except Exception:
        pass
    return CLASS10_APTITUDE_STREAM_MODE_COMBINED


def _dedupe_areas(areas: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for area in areas or []:
        key = str(area or '').upper().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def strong_areas_from_tiers(above_avg: list[str], average: list[str]) -> list[str]:
    """Areas that are Average or Above Average (exclude development areas)."""
    return _dedupe_areas((above_avg or []) + (average or []))


def resolve_stream_input_areas(
    above_avg: list[str] | None,
    average: list[str] | None,
    mode: str | None = None,
) -> tuple[list[str], str]:
    """
    Pick reasoning areas used for stream lookup based on admin display mode.

    Returns (areas, tier_used) where tier_used is one of:
    combined | above_avg | average | below_avg
    """
    mode = mode or get_aptitude_stream_display_mode()
    above = _dedupe_areas(above_avg or [])
    avg = _dedupe_areas(average or [])

    if mode == CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY:
        if above:
            return above, 'above_avg'
        if avg:
            return avg, 'average'
        return [], 'below_avg'

    return strong_areas_from_tiers(above, avg), 'combined'


def profile_label_for_tier(tier_used: str) -> str:
    if tier_used == 'above_avg':
        return 'above average reasoning profile'
    if tier_used == 'average':
        return 'average reasoning profile'
    return 'combined reasoning profile'


def _stream_entry(stream_key: str) -> dict[str, Any]:
    meta = STREAM_UI.get(stream_key, {})
    return {
        'key': stream_key,
        'display': meta.get('display', stream_key),
        'description': meta.get('description', stream_key),
        'icon': meta.get('icon', 'pcm-icon.png'),
    }


def _weighted_recommendation(codes: frozenset[str]) -> tuple[str, str, str]:
    """Return primary, secondary, tertiary via weighted key-area overlap."""
    scores: dict[str, float] = {}
    for stream, keys in STREAM_WEIGHT_KEYS.items():
        if not keys:
            scores[stream] = 0.0
            continue
        scores[stream] = sum(1 for k in keys if k in codes) / len(keys)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    primary = ranked[0][0]
    secondary = ranked[1][0] if len(ranked) > 1 else ranked[0][0]
    tertiary = ranked[2][0] if len(ranked) > 2 else None
    return primary, secondary, tertiary or secondary


def _lookup_exact(codes: frozenset[str]) -> tuple[str, str] | None:
    if not codes:
        return None
    if codes == ALL_REASONING_CODES:
        return ALL_SEVEN_STREAMS
    if len(codes) == 6:
        missing = (ALL_REASONING_CODES - codes).pop()
        return SIX_AREA_LOOKUP.get(missing)
    return COMBO_LOOKUP.get(codes)


def recommend_streams_from_tiers(
    above_avg: list[str] | None,
    average: list[str] | None,
    below_avg: list[str] | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    """
    Recommend best-fit and alternative streams from aptitude tier lists.

    Returns dict with primary, secondary, optional tertiary, and metadata.
    When tier-priority mode is active and all areas are below average,
    returns note_only=True with no stream cards.
    """
    display_mode = mode or get_aptitude_stream_display_mode()
    strong_areas, tier_used = resolve_stream_input_areas(above_avg, average, display_mode)

    if tier_used == 'below_avg':
        return {
            'note_only': True,
            'display_mode': display_mode,
            'tier_used': tier_used,
            'profile_label': profile_label_for_tier(tier_used),
            'strong_areas': [],
            'reasoning_codes': [],
            'has_development_areas': bool(_dedupe_areas(below_avg or [])),
            'method': 'note_only',
            'all_seven_note': None,
        }

    codes = areas_to_codes(strong_areas)

    result: dict[str, Any] = {
        'note_only': False,
        'display_mode': display_mode,
        'tier_used': tier_used,
        'profile_label': profile_label_for_tier(tier_used),
        'strong_areas': strong_areas,
        'reasoning_codes': sorted(codes),
        'has_development_areas': bool(_dedupe_areas(below_avg or [])),
        'method': 'weighted',
        'all_seven_note': None,
    }

    if not codes:
        primary, secondary, tertiary = _weighted_recommendation(frozenset())
        result['method'] = 'fallback_empty'
    else:
        exact = _lookup_exact(codes)
        if exact:
            primary, secondary = exact
            result['method'] = 'exact'
            if codes == ALL_REASONING_CODES:
                result['all_seven_note'] = ALL_SEVEN_NOTE
                result['ranked_streams'] = [
                    _stream_entry(s) for s in STREAM_RANK_ALL_SEVEN
                ]
            tertiary = None
        else:
            primary, secondary, tertiary = _weighted_recommendation(codes)
            result['method'] = 'weighted'

    result['primary'] = _stream_entry(primary)
    result['secondary'] = _stream_entry(secondary)
    if tertiary and tertiary != secondary:
        result['tertiary'] = _stream_entry(tertiary)

    return result


def streamsubject_from_recommendation(stream_recommendation: dict[str, Any] | None) -> list[tuple[str, str]]:
    """(stream name, description) pairs for premium career catalogue filtering."""
    if not stream_recommendation or stream_recommendation.get('note_only'):
        return []
    pairs: list[tuple[str, str]] = []
    for slot in ('primary', 'secondary'):
        entry = stream_recommendation.get(slot)
        if not entry:
            continue
        display = str(entry.get('display') or entry.get('key') or '').strip()
        description = str(entry.get('description') or '').strip()
        if display:
            pairs.append((display, description))
    return pairs


def suitable_combinations_from_recommendation(
    stream_recommendation: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Dashboard-style stream cards from best fit + alternative recommendation."""
    if not stream_recommendation or stream_recommendation.get('note_only'):
        return []
    combos: list[dict[str, Any]] = []
    for tier, slot in (('best_fit', 'primary'), ('alternative', 'secondary')):
        entry = stream_recommendation.get(slot)
        if not entry:
            continue
        display = str(entry.get('display') or entry.get('key') or '').strip()
        if not display:
            continue
        combos.append({
            'label': display,
            'stream': display,
            'subjects': str(entry.get('description') or '').strip(),
            'stream_tier': tier,
            'icon': entry.get('icon'),
            'key': entry.get('key', display),
        })
    return combos


def premium_career_groups_from_recommendation(
    stream_recommendation: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Premium catalogue career groups for recommended streams (dashboard / report)."""
    from app.stream_sorter_guidance import filter_stream_wise_for_student
    from app.stream_sorter_unique_streams import _extract_stream_codes

    streamsubject = streamsubject_from_recommendation(stream_recommendation)
    if not streamsubject:
        return []

    groups, _, _ = filter_stream_wise_for_student(streamsubject)
    if not groups:
        return []

    def _codes_for_entry(entry: dict[str, Any]) -> set[str]:
        text = f"{entry.get('key', '')} {entry.get('display', '')}"
        return set(_extract_stream_codes(text))

    def _careers_from_group(group: dict[str, Any]) -> list[str]:
        careers: list[str] = []
        for item in group.get('careers') or []:
            if isinstance(item, dict):
                name = str(item.get('name') or '').strip()
            else:
                name = str(item).strip()
            if name:
                careers.append(name)
        return careers

    tier_labels = {
        'best_fit': 'Best fit stream',
        'alternative': 'Alternative stream',
    }
    result: list[dict[str, Any]] = []
    used_group_ids: set[int] = set()

    for tier, slot in (('best_fit', 'primary'), ('alternative', 'secondary')):
        entry = stream_recommendation.get(slot) if stream_recommendation else None
        if not entry:
            continue
        entry_codes = _codes_for_entry(entry)
        display = str(entry.get('display') or entry.get('key') or '').strip()
        matched_group = None
        for group in groups:
            if id(group) in used_group_ids:
                continue
            group_codes = set(_extract_stream_codes(str(group.get('stream') or '')))
            if entry_codes and group_codes.intersection(entry_codes):
                matched_group = group
                break
        if not matched_group and display:
            display_lower = display.lower()
            for group in groups:
                if id(group) in used_group_ids:
                    continue
                stream_label = str(group.get('stream') or '').lower()
                if display_lower in stream_label or stream_label in display_lower:
                    matched_group = group
                    break
        if not matched_group:
            continue
        used_group_ids.add(id(matched_group))
        careers = _careers_from_group(matched_group)
        if not careers:
            continue
        stream_label = str(matched_group.get('stream') or matched_group.get('stream_code') or '').strip()
        result.append({
            'code': str(matched_group.get('stream_code') or stream_label).strip(),
            'name': tier_labels.get(tier, stream_label),
            'stream': stream_label,
            'careers': careers,
        })
    return result


  