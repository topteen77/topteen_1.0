"""Class 10 aptitude report helpers (performance profile cards)."""

from __future__ import annotations

from typing import Any

CLASS10_APTITUDE_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ('LOGICAL', 'Logical Reasoning'),
    ('SPATIAL', 'Spatial Reasoning'),
    ('CRITICAL', 'Critical Reasoning'),
    ('NUMERICAL', 'Numerical Reasoning'),
    ('MECHANICAL', 'Mechanical Reasoning'),
    ('LANGUAGE', 'Language Usage and Spelling'),
    ('VERBAL', 'Verbal Reasoning'),
)

_SCORE_KEY_ALIASES = {
    'LOGICAL': ('logical_score', 'logical'),
    'SPATIAL': ('spatial_score', 'spatial'),
    'CRITICAL': ('critical_score', 'critical', 'emotional_score', 'emotional'),
    'NUMERICAL': ('numerical_score', 'numerical'),
    'MECHANICAL': ('mechanical_score', 'mechanical'),
    'LANGUAGE': ('language_score', 'language'),
    'VERBAL': ('verbal_score', 'verbal'),
}


def _normalize_scores(scores: dict[str, Any] | None) -> dict[str, float]:
    if not scores:
        return {}
    normalized: dict[str, float] = {}
    for key, value in scores.items():
        code = str(key).split('_')[0].upper().strip()
        if code == 'EMOTIONAL':
            code = 'CRITICAL'
        try:
            normalized[code] = float(value)
        except (TypeError, ValueError):
            normalized[code] = 0.0
        normalized[str(key).lower()] = normalized[code]
    return normalized


def _score_for_code(normalized: dict[str, float], code: str) -> float:
    for alias in _SCORE_KEY_ALIASES.get(code, (code.lower(),)):
        if alias in normalized:
            return normalized[alias]
        alias_code = alias.split('_')[0].upper()
        if alias_code in normalized:
            return normalized[alias_code]
    return normalized.get(code, 0.0)


def _performance_style(accuracy: float) -> dict[str, str]:
    if accuracy >= 70:
        return {'level': 'above-average', 'color': '#3F37C9'}
    if accuracy < 40:
        return {'level': 'below-average', 'color': '#C24E4E'}
    return {'level': 'average', 'color': '#2E8AA6'}


def class10_aptitude_profile_sections(
    scores: dict[str, Any] | None,
    *,
    total_questions: int = 15,
) -> list[dict[str, Any]]:
    """Build per-section performance cards for Class 10 aptitude reports."""
    normalized = _normalize_scores(scores)
    if not normalized:
        return []

    sections: list[dict[str, Any]] = []
    for code, name in CLASS10_APTITUDE_SECTIONS:
        try:
            correct = int(round(_score_for_code(normalized, code)))
        except (TypeError, ValueError):
            correct = 0
        correct = max(0, min(total_questions, correct))
        accuracy = (correct / total_questions * 100.0) if total_questions else 0.0
        style = _performance_style(accuracy)
        sections.append({
            'name': name,
            'code': code,
            'total_questions': total_questions,
            'correct_answers': correct,
            'accuracy': round(accuracy, 1),
            'performance_level': style['level'],
            'accent_color': style['color'],
        })
    return sections


def aptitude_report_context_fields(
    scores: dict[str, Any] | None,
    *,
    total_questions: int = 15,
) -> dict[str, Any]:
    return {
        'aptitude_profile_sections': class10_aptitude_profile_sections(
            scores,
            total_questions=total_questions,
        ),
    }
