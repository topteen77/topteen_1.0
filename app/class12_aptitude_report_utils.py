"""Apply Class 11–12 consolidated aptitude JSON to student report context."""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from typing import Any

from app.class12_aptitude_consolidated_io import (
    DEFAULT_JSON_PATH,
    lookup_combination,
    normalize_combination_key,
)
from app_post_matric.aptitude_area_labels import resolve_aptitude_json_area

CONSOLIDATED_AREA = '__consolidated__'
DEFAULT_CONSOLIDATED_IMAGE = 'images/aptitude-ig.png'
DEFAULT_HEADING = 'Recommendation'

_APTITUDE_NAME_TO_CODE = {
    'abstract reasoning': 'AR',
    'numerical reasoning': 'NR',
    'logical reasoning': 'LR',
    'language & verbal reasoning': 'LVR',
    'language and verbal reasoning': 'LVR',
    'verbal & language reasoning': 'LVR',
    'mechanical reasoning': 'MR',
    'spatial reasoning': 'SR',
    'clerical speed & accuracy': 'CR',
    'clerical speed and accuracy': 'CR',
    'clerical': 'CR',
}


def map_aptitude_name_to_code(name: str) -> str | None:
    if not name:
        return None
    return _APTITUDE_NAME_TO_CODE.get(str(name).strip().lower())


def build_combination_key(above_areas: list[str], average_areas: list[str]) -> str:
    """Sorted reasoning codes from Above Average + Average tiers, e.g. 'AR + CR'."""
    codes = sorted({
        code
        for area in (above_areas or []) + (average_areas or [])
        if (code := map_aptitude_name_to_code(resolve_aptitude_json_area(area))) is not None
    })
    return ' + '.join(codes)


@lru_cache(maxsize=1)
def _consolidated_available() -> bool:
    if DEFAULT_JSON_PATH.is_file():
        return True
    try:
        from app.models import Class12AptitudeConsolidatedReport

        return Class12AptitudeConsolidatedReport.objects.filter(is_active=True).exists()
    except Exception:
        return False


def clear_consolidated_lookup_cache() -> None:
    _consolidated_available.cache_clear()


def _find_area_interpretation(
    aptitude_interpretation_data: dict[str, Any] | None,
    area_name: str,
) -> dict[str, Any] | None:
    if not aptitude_interpretation_data:
        return None
    mapped_area = resolve_aptitude_json_area(area_name)
    for interpretation in aptitude_interpretation_data.get('Aptitude_Interpretations', []):
        if interpretation.get('Area') == mapped_area:
            return interpretation
    return None


def _primary_area_name(above_areas: list[str], average_areas: list[str]) -> str | None:
    if above_areas:
        return above_areas[0]
    if average_areas:
        return average_areas[0]
    return None


def lookup_student_consolidated_row(
    above_areas: list[str],
    average_areas: list[str],
) -> dict[str, Any] | None:
    """Look up consolidated report row for the student's reasoning combination."""
    if not _consolidated_available():
        return None
    key = build_combination_key(above_areas, average_areas)
    if not key:
        return None
    try:
        return lookup_combination(key)
    except (FileNotFoundError, ValueError):
        return None


def _as_description_html(text: str) -> str:
    cleaned = (text or '').strip()
    if not cleaned:
        return ''
    if '<' in cleaned:
        return cleaned
    return f'<p>{cleaned}</p>'


def build_consolidated_profile(
    consolidated_row: dict[str, Any],
    combination_key: str,
    *,
    aptitude_interpretation_data: dict[str, Any] | None = None,
    above_areas: list[str] | None = None,
    average_areas: list[str] | None = None,
) -> dict[str, Any]:
    """Single-box consolidated profile for Interpretation & Recommendations."""
    above = list(above_areas or [])
    average = list(average_areas or [])
    primary_area = _primary_area_name(above, average)
    primary_interp = (
        _find_area_interpretation(aptitude_interpretation_data, primary_area)
        if primary_area
        else None
    )

    # Real-life signs and daily life impact stay on the primary Above/Average area only
    # (legacy JSON per-area content — do not merge across the full combination).
    real_life_signs = list((primary_interp or {}).get('Real life signs') or [])
    daily_life_impact = list((primary_interp or {}).get('Daily life impact') or [])

    title = (primary_interp or {}).get('Title') or DEFAULT_HEADING
    image = (primary_interp or {}).get('Image') or DEFAULT_CONSOLIDATED_IMAGE

    return {
        'combination_key': combination_key,
        'code_count': len(consolidated_row.get('codes') or []),
        'title': title,
        'image': image,
        'description_html': _as_description_html(
            consolidated_row.get('aptitude_description', '')
        ),
        'narrative_html': consolidated_row.get('interpretation_narrative') or '',
        'career_clusters': list(consolidated_row.get('career_clusters') or []),
        'career_pathways': list(consolidated_row.get('career_pathways') or []),
        'degree_pathways': list(consolidated_row.get('degree_pathways') or []),
        'real_life_signs': real_life_signs,
        'daily_life_impact': daily_life_impact,
    }


def build_consolidated_recommendation_lists(
    consolidated_row: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Single strength / college / role blocks for consolidated report mode."""
    narrative = consolidated_row.get('interpretation_narrative') or ''
    degree_pathways = list(consolidated_row.get('degree_pathways') or [])
    career_pathways = list(consolidated_row.get('career_pathways') or [])

    strength_narrative = [{
        'Area': CONSOLIDATED_AREA,
        'Narrative_html': narrative,
        'Major_points': [],
    }]
    college_courses = [{
        'Area': CONSOLIDATED_AREA,
        'Recommended_College': degree_pathways,
        'Universities': [],
    }]
    roles_guidance = [{
        'Area': CONSOLIDATED_AREA,
        'Guidance': 'Career Recommendations',
        'Recommendations': [{'Role': role} for role in career_pathways],
    }]
    return strength_narrative, college_courses, roles_guidance


def enrich_interpretation(
    interpretation: dict[str, Any],
    consolidated_row: dict[str, Any],
) -> dict[str, Any]:
    """Overlay consolidated fields; keep Real-life signs and Daily life impact."""
    enriched = deepcopy(interpretation)
    enriched['Description'] = _as_description_html(
        consolidated_row.get('aptitude_description', '')
    )
    enriched['Career impact'] = list(consolidated_row.get('career_clusters') or [])
    return enriched


def build_aptitude_interpretations(
    high_categories: dict[str, list[str]],
    aptitude_interpretation_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Legacy per-area interpretation cards.

    When consolidated JSON is available, returns an empty list — the template
    should render ``class12_aptitude_consolidated_profile`` as a single box.
    """
    if lookup_student_consolidated_row(
        high_categories.get('Above Average', []) or [],
        high_categories.get('Average', []) or [],
    ):
        return []

    interpretations: list[dict[str, Any]] = []
    if not aptitude_interpretation_data or 'Aptitude_Interpretations' not in aptitude_interpretation_data:
        return interpretations

    above_areas = high_categories.get('Above Average', []) or []
    average_areas = high_categories.get('Average', []) or []
    all_areas = above_areas + average_areas

    for area in all_areas:
        mapped_area = resolve_aptitude_json_area(area)
        for interpretation in aptitude_interpretation_data['Aptitude_Interpretations']:
            if interpretation['Area'] != mapped_area:
                continue
            interpretations.append(deepcopy(interpretation))
            break

    return interpretations


def build_consolidated_profile_for_student(
    high_categories: dict[str, list[str]],
    aptitude_interpretation_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    above_areas = high_categories.get('Above Average', []) or []
    average_areas = high_categories.get('Average', []) or []
    row = lookup_student_consolidated_row(above_areas, average_areas)
    if not row:
        return None
    key = normalize_combination_key(build_combination_key(above_areas, average_areas))
    return build_consolidated_profile(
        row,
        key,
        aptitude_interpretation_data=aptitude_interpretation_data,
        above_areas=above_areas,
        average_areas=average_areas,
    )


def aptitude_tier_data_json(
    above_areas: list[str],
    average_areas: list[str],
    below_areas: list[str],
) -> str:
    """JSON for pdf-results.js tier cards (must match combination lookup tiers)."""
    return json.dumps({
        'above_average': list(above_areas or []),
        'average': list(average_areas or []),
        'below_average': list(below_areas or []),
    })


def aptitude_assessment_report_context(
    high_categories: dict[str, Any] | Any,
    aptitude_interpretation_data: dict[str, Any] | None,
    hexaco_recommendations: dict[str, Any],
) -> dict[str, Any]:
    """Shared aptitude report context for Results view, PDF, and duplicates."""
    hc = high_categories if isinstance(high_categories, dict) else {}
    above = list(hc.get('Above Average', []) or [])
    average = list(hc.get('Average', []) or [])
    below = list(hc.get('Below Average', []) or [])
    ctx: dict[str, Any] = {
        'aptitude_improvement_plan': hexaco_recommendations.get('aptitude_improvement_plan', []),
        'aptitude_strength_narrative': hexaco_recommendations.get('aptitude_strength_narrative', []),
        'aptitude_Recommended_College_Courses': hexaco_recommendations.get(
            'aptitude_Recommended_College_Courses', []
        ),
        'aptitude_roles_guidance': hexaco_recommendations.get('aptitude_roles_guidance', []),
        'aptitude_interpretations': build_aptitude_interpretations(hc, aptitude_interpretation_data),
        'class12_aptitude_consolidated_profile': build_consolidated_profile_for_student(
            hc,
            aptitude_interpretation_data,
        ),
        'class12_aptitude_combination_key': hexaco_recommendations.get('class12_aptitude_combination_key'),
        'aptitude_tier_data_json': aptitude_tier_data_json(above, average, below),
        'above_list': above,
        'average_list': average,
        'below_list': below,
    }
    if 'career_guidance_selected' in hexaco_recommendations:
        ctx['career_guidance_selected'] = hexaco_recommendations['career_guidance_selected']
    return ctx


def apply_consolidated_to_aptitude_result(
    result: dict[str, Any],
    above_areas: list[str],
    average_areas: list[str],
) -> str | None:
    """
    Replace strength / college / role lists with consolidated JSON when a row exists.
    Returns the combination key used, or None.
    """
    consolidated_row = lookup_student_consolidated_row(above_areas, average_areas)
    if not consolidated_row:
        return None

    strength, colleges, roles = build_consolidated_recommendation_lists(consolidated_row)
    result['aptitude_strength_narrative'] = strength
    result['aptitude_Recommended_College_Courses'] = colleges
    result['aptitude_roles_guidance'] = roles
    key = normalize_combination_key(build_combination_key(above_areas, average_areas))
    result['class12_aptitude_combination_key'] = key
    return key
