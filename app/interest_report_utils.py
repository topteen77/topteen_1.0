"""Helpers for test2 / combined report interest (RIASEC) display."""

import re

RIASEC_ORDER = ('R', 'I', 'A', 'S', 'E', 'C')

RIASEC_NAME_TO_CODE = {
    'Realistic': 'R',
    'Investigative': 'I',
    'Artistic': 'A',
    'Social': 'S',
    'Enterprising': 'E',
    'Conventional': 'C',
}

RIASEC_CODE_TO_NAME = {code: name for name, code in RIASEC_NAME_TO_CODE.items()}


def _category_to_code(name):
    if not name:
        return ''
    if name in RIASEC_NAME_TO_CODE:
        return RIASEC_NAME_TO_CODE[name]
    first = str(name).strip()[:1].upper()
    return first if first in RIASEC_CODE_TO_NAME else ''


def _codes_from_names(names):
    codes = []
    for name in names:
        code = _category_to_code(name)
        if code and code not in codes:
            codes.append(code)
    codes.sort(key=lambda c: RIASEC_ORDER.index(c))
    return codes


def codes_from_code_string(code_string):
    """Parse a concatenated RIASEC code string (e.g. 'ISC') into ordered codes."""
    if not code_string:
        return []
    codes = []
    for char in str(code_string).upper():
        if char in RIASEC_CODE_TO_NAME and char not in codes:
            codes.append(char)
    codes.sort(key=lambda c: RIASEC_ORDER.index(c))
    return codes


def resolve_interest_extrema(scores):
    """
    Return (max_length, min_length, dominant_names, lowest_names).
    max_length is a concatenation of RIASEC codes (e.g. 'RI') for all tied highest scores.
    """
    if not scores:
        return '', '', [], []

    max_score = max(scores.values())
    min_score = min(scores.values())
    dominant_names = [name for name, value in scores.items() if value == max_score]
    lowest_names = [name for name, value in scores.items() if value == min_score]
    max_codes = _codes_from_names(dominant_names)
    min_codes = _codes_from_names(lowest_names)
    return ''.join(max_codes), ''.join(min_codes), dominant_names, lowest_names


def riasec_code_display_label(code_string):
    """
    Human-readable RIASEC label, e.g. 'ISC' -> 'ISC — Investigative, Social, Conventional'.
    """
    codes = codes_from_code_string(code_string)
    if not codes:
        return str(code_string or '').strip()
    names = [RIASEC_CODE_TO_NAME[code] for code in codes]
    code_part = ''.join(codes)
    if len(names) == 1:
        return f'{code_part} — {names[0]}'
    return f'{code_part} — {", ".join(names)}'


def careers_for_riasec_codes(codes, career_map, limit=12):
    """Merge career suggestions for each RIASEC code (preserves order, dedupes)."""
    seen = []
    for code in codes:
        for career in career_map.get(code, []):
            if career not in seen:
                seen.append(career)
            if len(seen) >= limit:
                return seen
    return seen


def career_suggestion_groups(codes, career_map, fallback_careers=None, fallback_title='Recommended paths'):
    """
    Group careers under each RIASEC (or aptitude) heading for dashboard display.
    Returns list of {code, name, careers}.
    """
    groups = []
    for code in codes:
        careers = list(career_map.get(code, []) or [])
        if not careers:
            continue
        groups.append({
            'code': code,
            'name': RIASEC_CODE_TO_NAME.get(code, str(code).title()),
            'careers': careers,
        })
    if not groups and fallback_careers:
        groups.append({
            'code': '',
            'name': fallback_title,
            'careers': list(fallback_careers),
        })
    return groups


def _score_value(raw):
    if isinstance(raw, dict):
        for key in ('score', 'total', 'average'):
            if key in raw and raw[key] is not None:
                return float(raw[key])
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _dimension_code(key):
    code = re.sub(r'\d+$', '', str(key).strip())[:1].upper()
    return code if code in RIASEC_CODE_TO_NAME else ''


def top_riasec_codes_from_scores(scores, limit=3):
    """
    Return top RIASEC letter codes from a scores mapping.
    Ties are broken using canonical RIASEC order (R, I, A, S, E, C).
    """
    pairs = []
    for key, value in (scores or {}).items():
        if str(key).startswith('_'):
            continue
        code = _dimension_code(key)
        if not code:
            continue
        pairs.append((code, _score_value(value)))
    pairs.sort(key=lambda item: (-item[1], RIASEC_ORDER.index(item[0])))
    return [code for code, _ in pairs[:limit]]


def riasec_code_string_from_scores(scores, limit=3):
    return ''.join(top_riasec_codes_from_scores(scores, limit=limit))


def interest_report_context_fields(scores=None, max_length='', min_length=''):
    """Context keys for templates: tied dominant areas and explicit RIASEC code list."""
    if scores:
        max_length, min_length, dominant_names, _ = resolve_interest_extrema(scores)
        dominant_codes = _codes_from_names(dominant_names)
    elif max_length and not scores:
        dominant_codes = codes_from_code_string(max_length)
        dominant_names = [RIASEC_CODE_TO_NAME[code] for code in dominant_codes]
    else:
        dominant_names = []
        dominant_codes = []

    dominant_interest_labels = ', '.join(dominant_names)
    return {
        'max_length': max_length,
        'min_length': min_length,
        'dominant_interest_categories': dominant_names,
        'dominant_interest_codes': dominant_codes,
        'dominant_interest_labels': dominant_interest_labels,
        'dominant_interest_display': riasec_code_display_label(max_length),
        'dominant_interest_tied': len(dominant_names) > 1,
    }
