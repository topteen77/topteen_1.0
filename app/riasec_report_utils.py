"""Helpers for Class 10 RIASEC personality report career pathway sections."""

from __future__ import annotations

import re

from app.models import Category, Stream

CAREER_PATHWAYS_TITLE = 'Career Pathways'
CAREER_ALIGNMENT_HEADING = 'Career Alignment Explanation'

_BULLET_SPLIT_RE = re.compile(r'[\u2022\ufffd\u25cf\u00b7]+')
_TRAIT_PREFIX_RE = re.compile(r'^[\u2022\ufffd\u25cf\u00b7\u2013\u2014\-]\s*')


def normalize_career_pathways_mode(mode: str | None) -> str:
    if (mode or '').strip().lower() == Category.CAREER_PATHWAYS_COMBINED:
        return Category.CAREER_PATHWAYS_COMBINED
    return Category.CAREER_PATHWAYS_INDIVIDUAL


def stream_career_section_title(stream_code: str) -> str:
    return f'Suggested Careers — {stream_code}'


def parse_career_alignment_summary(summary: str | None) -> dict | None:
    """Parse RIASEC summary text into structured report fields."""
    if not summary or not str(summary).strip():
        return None

    text = str(summary).strip()
    result = {
        'types_heading': '',
        'intro': '',
        'characteristics': [],
        'trait_name': '',
        'trait_description': '',
        'structured': False,
    }

    char_idx = text.find('Characteristics:')
    trait_idx = text.find('Personality Trait')

    if char_idx == -1 and trait_idx == -1:
        colon = text.find(':')
        if colon > 0:
            result['types_heading'] = text[:colon].strip()
            result['intro'] = text[colon + 1:].strip()
        else:
            result['intro'] = text
        return result

    result['structured'] = True
    intro_end = char_idx if char_idx != -1 else trait_idx
    intro_part = text[:intro_end].strip()
    colon = intro_part.find(':')
    if colon > 0:
        result['types_heading'] = intro_part[:colon].strip()
        result['intro'] = intro_part[colon + 1:].strip()
    else:
        result['intro'] = intro_part

    if char_idx != -1:
        char_end = trait_idx if trait_idx != -1 and trait_idx > char_idx else len(text)
        char_text = text[char_idx + len('Characteristics:'):char_end].strip()
        result['characteristics'] = [
            item.strip(' -–\t\n')
            for item in _BULLET_SPLIT_RE.split(char_text)
            if item.strip(' -–\t\n')
        ]

    if trait_idx != -1:
        trait_text = _TRAIT_PREFIX_RE.sub('', text[trait_idx + len('Personality Trait'):].strip())
        trait_colon = trait_text.find(':')
        if trait_colon > 0:
            result['trait_name'] = trait_text[:trait_colon].strip()
            result['trait_description'] = trait_text[trait_colon + 1:].strip()
        else:
            result['trait_description'] = trait_text

    return result


def get_personality_career_groups(top_category) -> list[dict]:
    """Dashboard/report career pathway groups for a RIASEC combination."""
    groups: list[dict] = []
    for section in get_stream_career_sections(top_category):
        careers = [str(item).strip() for item in (section.get('careers') or []) if str(item).strip()]
        if not careers:
            continue
        groups.append({
            'code': section.get('code', ''),
            'name': section.get('title') or section.get('code', 'Suggested stream'),
            'label': section.get('label', ''),
            'careers': careers,
            'combined': bool(section.get('combined')),
        })
    return groups


def get_stream_career_sections(top_category) -> list[dict]:
    """Return career blocks for personality reports (combined or per-stream)."""
    if not top_category:
        return []

    mode = normalize_career_pathways_mode(
        getattr(top_category, 'career_pathways_mode', None)
    )
    streams = Stream.objects.filter(category=top_category).order_by('id')

    if mode == Category.CAREER_PATHWAYS_COMBINED:
        careers: list[str] = []
        for stream in streams:
            opts = stream.career_options if isinstance(stream.career_options, list) else []
            if opts:
                careers = [str(item).strip() for item in opts if str(item).strip()]
                break
        if not careers:
            return []
        return [{
            'code': '',
            'title': CAREER_PATHWAYS_TITLE,
            'label': '',
            'careers': careers,
            'combined': True,
        }]

    sections: list[dict] = []
    for stream in streams:
        careers = stream.career_options if isinstance(stream.career_options, list) else []
        careers = [str(item).strip() for item in careers if str(item).strip()]
        if not careers:
            continue
        code = stream.stream_name
        sections.append({
            'code': code,
            'title': stream_career_section_title(code),
            'label': stream.subjects,
            'careers': careers,
            'combined': False,
        })
    return sections
