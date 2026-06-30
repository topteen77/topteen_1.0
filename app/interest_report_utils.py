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

RIASEC_DISPLAY_LABELS = {
    'R': 'Realistic & Adventurous',
    'I': 'Investigative & Knowledgeable',
    'A': 'Artistic & Creative',
    'S': 'Social & Collaborative',
    'E': 'Enterprising & Bold Leader',
    'C': 'Conventional & Organized',
}

RIASEC_THEME = {
    'R': {'color': '#057190', 'bg': '#C9EDF8'},
    'I': {'color': '#A92CAF', 'bg': '#FEECFF'},
    'A': {'color': '#2A740E', 'bg': '#EDFFE7'},
    'S': {'color': '#6D5C04', 'bg': '#FFFAE2'},
    'E': {'color': '#A22717', 'bg': '#FFFAE2'},
    'C': {'color': '#0B5BA1', 'bg': '#EBF6FF'},
}

RIASEC_STORY_DESCRIPTIONS = {
    'R': (
        'Hey! Your dominant interest area turned out to be Realistic. From a young age, you may have '
        'shown strong practical skills and a natural ability to build, repair, or work with tools, '
        'machines, or physical systems. You prefer action over excessive discussion and enjoy solving '
        'real-world problems through hands-on work. You are resilient, practical, and often the person '
        'others rely on when something needs fixing or improving. You are likely to thrive in careers '
        'involving technical systems, engineering, operations, and physical problem-solving.'
    ),
    'I': (
        'Hey! Your dominant interest area turned out to be Investigative. You are naturally curious '
        'and enjoy asking deep questions about how things work. You love exploring ideas, analyzing '
        'data, and solving complex problems. Your strong observation skills and analytical mindset help '
        'you notice patterns that others may miss. You are drawn toward learning, research, and '
        'discovery, and likely enjoy intellectual challenges that require critical thinking and '
        'evidence-based reasoning.'
    ),
    'A': (
        'Hey! Your dominant interest area turned out to be Artistic. You are imaginative, expressive, '
        'and full of original ideas. You enjoy creating, designing, writing, performing, or bringing '
        'concepts to life in unique ways. You likely have strong aesthetic sense and creative '
        'intuition, and people often admire your originality. You thrive in environments where '
        'innovation, storytelling, design, and self-expression are valued.'
    ),
    'S': (
        'Hey! Your dominant interest area turned out to be Social. You connect easily with people and '
        'naturally understand emotions, relationships, and group dynamics. You are empathetic, '
        'supportive, and often the person others trust for advice or help. You enjoy teamwork, '
        'mentoring, teaching, and contributing to the well-being of others. You are likely to thrive '
        'in careers centered around helping, guiding, healing, or empowering people.'
    ),
    'E': (
        'Hey! Your dominant interest area turned out to be Enterprising. You are ambitious, confident, '
        'and naturally inclined toward leadership. You enjoy influencing people, taking initiative, and '
        'turning ideas into action. You are comfortable making decisions, taking calculated risks, and '
        'motivating others toward goals. You thrive in dynamic environments where persuasion, strategy, '
        'leadership, and business thinking drive success and impact.'
    ),
    'C': (
        'Hey! Your dominant interest area turned out to be Conventional. You are highly organized, '
        'dependable, and excellent at managing systems, processes, and details. You like structure, '
        'clarity, and well-defined workflows. You are often the one who keeps things running smoothly '
        'by planning carefully and ensuring nothing is overlooked. You thrive in careers that value '
        'accuracy, efficiency, organization, and systematic execution.'
    ),
}

# Canonical "Careers to Choose" lists — keep aligned with test2_report.html / combined report.
RIASEC_CAREERS_TO_CHOOSE = {
    'R': [
        'Mechanical Engineering',
        'Construction Management',
        'Aviation (Pilot / Aviation Operations)',
        'Surveying & Mapping',
        'Skilled Technical Trades',
        'Industrial Engineering',
        'Automotive Engineering',
        'Robotics & Automation',
    ],
    'I': [
        'Research & Development',
        'Data Science & Analytics',
        'Biotechnology & Life Sciences',
        'Software Engineering',
        'Forensic Science',
        'Medical Research',
        'Environmental Science',
        'AI / Machine Learning',
    ],
    'A': [
        'Graphic Design',
        'Writing & Publishing',
        'Music & Performing Arts',
        'Film & Media Production',
        'Fashion Design',
        'Animation',
        'Interior Design',
        'UI/UX Design',
    ],
    'S': [
        'Counseling & Therapy',
        'Education & Teaching',
        'Healthcare & Allied Health Sciences',
        'Social Services',
        'Human Resource Management',
        'Occupational Therapy',
        'Public Relations',
        'NGO / Nonprofit Management',
    ],
    'E': [
        'Entrepreneurship',
        'Marketing & Sales',
        'Real Estate & Infrastructure',
        'Business Management',
        'Brand Management',
        'Digital Marketing',
        'Business Development',
        'Product Management',
    ],
    'C': [
        'Accounting & Finance',
        'Administrative Management',
        'Data Analysis',
        'Project Management',
        'Banking & Financial Services',
        'Compliance & Risk Management',
        'Supply Chain Management',
        'Audit & Compliance',
    ],
}


def _split_story_description(description):
    """Split 'Hey! ... turned out to be X.' intro from the rest of the paragraph."""
    text = str(description or '').strip()
    marker = 'turned out to be '
    marker_idx = text.find(marker)
    if marker_idx == -1:
        return text, ''
    after_type = text[marker_idx + len(marker):]
    dot_idx = after_type.find('. ')
    if dot_idx == -1:
        return text, ''
    intro_end = marker_idx + len(marker) + dot_idx + 1
    intro = text[:intro_end].strip()
    body = text[intro_end:].strip()
    return intro, body


def riasec_report_sections():
    """Full section payload for test2 HTML/PDF templates and careers wheel."""
    sections = {}
    for code in RIASEC_ORDER:
        theme = RIASEC_THEME[code]
        description = RIASEC_STORY_DESCRIPTIONS[code]
        description_intro, description_body = _split_story_description(description)
        sections[code] = {
            'code': code,
            'label': RIASEC_DISPLAY_LABELS[code],
            'description': description,
            'description_intro': description_intro,
            'description_body': description_body,
            'careers': list(RIASEC_CAREERS_TO_CHOOSE[code]),
            'color': theme['color'],
            'bg': theme['bg'],
        }
    return sections


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
        'riasec_sections': riasec_report_sections(),
    }
