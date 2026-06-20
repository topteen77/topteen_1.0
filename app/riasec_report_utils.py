"""Helpers for Class 10 RIASEC personality report career pathway sections."""

from __future__ import annotations

from app.models import Category, Stream

CAREER_PATHWAYS_TITLE = 'Career Pathways'


def normalize_career_pathways_mode(mode: str | None) -> str:
    if (mode or '').strip().lower() == Category.CAREER_PATHWAYS_COMBINED:
        return Category.CAREER_PATHWAYS_COMBINED
    return Category.CAREER_PATHWAYS_INDIVIDUAL


def stream_career_section_title(stream_code: str) -> str:
    return f'Suggested Careers — {stream_code}'


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
