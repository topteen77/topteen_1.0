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
from app.class12_aptitude_signs_impact import areas_to_codes, resolve_signs_and_impacts
from app.report_visibility import student_all_growth_areas
from app_post_matric.aptitude_area_labels import resolve_aptitude_json_area
from app_post_matric.aptitude_area_labels import APTITUDE_IMPROVEMENT_NOTE
from core.choices import (
    CLASS10_APTITUDE_STREAM_MODE_COMBINED,
    CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
    CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_KEY,
)

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
    """Sorted reasoning codes from supplied tier lists, e.g. 'AR + CR'."""
    codes = sorted({
        code
        for area in (above_areas or []) + (average_areas or [])
        if (code := map_aptitude_name_to_code(resolve_aptitude_json_area(area))) is not None
    })
    return ' + '.join(codes)


def get_class12_aptitude_display_mode() -> str:
    """Read Class 12 consolidated report display mode from Configuration."""
    try:
        from core.models import Configuration

        raw = Configuration.get(
            CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE_KEY,
            default=CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
            editable=True,
        )
        mode = str(raw or '').strip().lower()
        if mode in (CLASS10_APTITUDE_STREAM_MODE_COMBINED, CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY):
            return mode
    except Exception:
        pass
    return CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY


def resolve_class12_consolidated_tiers(
    high_categories: dict[str, Any] | Any,
    mode: str | None = None,
) -> dict[str, Any]:
    """
    Resolve which aptitude tiers feed the consolidated lookup and legacy box header.

    Mirrors Class 10 stream display rules:
    - Combined: Above Average + Average together
    - Single - Above Average: Above only, else Average only
    - All growth areas: note_only (improvement plan only)
    """
    hc = high_categories if isinstance(high_categories, dict) else {}
    above = list(hc.get('Above Average', []) or [])
    average = list(hc.get('Average', []) or [])
    below = list(hc.get('Below Average', []) or [])
    display_mode = mode or get_class12_aptitude_display_mode()

    if student_all_growth_areas(below, average, above):
        return {
            'note_only': True,
            'display_mode': display_mode,
            'tier_used': 'below_avg',
            'lookup_above': [],
            'lookup_average': [],
            'display_areas': [],
            'primary_area': below[0] if below else None,
            'combination_key': '',
            'consolidated_row': None,
        }

    if display_mode == CLASS10_APTITUDE_STREAM_MODE_COMBINED:
        lookup_above, lookup_average = above, average
        tier_used = 'combined'
        display_areas = above + average
    elif above:
        lookup_above, lookup_average = above, []
        tier_used = 'above_avg'
        display_areas = above
    elif average:
        lookup_above, lookup_average = [], average
        tier_used = 'average'
        display_areas = average
    else:
        lookup_above, lookup_average = [], []
        tier_used = 'below_avg'
        display_areas = below

    combination_key = normalize_combination_key(
        build_combination_key(lookup_above, lookup_average)
    )
    consolidated_row = None
    if combination_key and _consolidated_available():
        try:
            consolidated_row = lookup_combination(combination_key)
        except (FileNotFoundError, ValueError):
            consolidated_row = None

    primary_area = display_areas[0] if display_areas else None

    return {
        'note_only': False,
        'display_mode': display_mode,
        'tier_used': tier_used,
        'lookup_above': lookup_above,
        'lookup_average': lookup_average,
        'display_areas': display_areas,
        'primary_area': primary_area,
        'combination_key': combination_key,
        'consolidated_row': consolidated_row,
    }


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
    if not aptitude_interpretation_data or not area_name:
        return None
    mapped_area = resolve_aptitude_json_area(area_name)
    for interpretation in aptitude_interpretation_data.get('Aptitude_Interpretations', []):
        if interpretation.get('Area') == mapped_area:
            return interpretation
    return None


def lookup_student_consolidated_row(
    above_areas: list[str],
    average_areas: list[str],
    below_areas: list[str] | None = None,
    mode: str | None = None,
) -> dict[str, Any] | None:
    """Look up consolidated report row using admin display mode tier rules."""
    tier_ctx = resolve_class12_consolidated_tiers(
        {
            'Above Average': above_areas or [],
            'Average': average_areas or [],
            'Below Average': below_areas or [],
        },
        mode=mode,
    )
    if tier_ctx.get('note_only'):
        return None
    return tier_ctx.get('consolidated_row')


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
    primary_area: str | None = None,
    display_areas: list[str] | None = None,
    tier_used: str = 'combined',
    display_mode: str | None = None,
) -> dict[str, Any]:
    """Single-box consolidated profile for Interpretation & Recommendations."""
    primary_interp = (
        _find_area_interpretation(aptitude_interpretation_data, primary_area)
        if primary_area
        else None
    )

    real_life_signs, daily_life_impact = resolve_signs_and_impacts(
        consolidated_row,
        codes=areas_to_codes(display_areas),
        aptitude_interpretation_data=aptitude_interpretation_data,
    )

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
        'tier_used': tier_used,
        'display_mode': display_mode or get_class12_aptitude_display_mode(),
        'note_only': False,
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
    tier_ctx = resolve_class12_consolidated_tiers(high_categories)
    if tier_ctx.get('note_only') or tier_ctx.get('consolidated_row'):
        return []

    interpretations: list[dict[str, Any]] = []
    if not aptitude_interpretation_data or 'Aptitude_Interpretations' not in aptitude_interpretation_data:
        return interpretations

    for area in tier_ctx.get('display_areas', []):
        mapped_area = resolve_aptitude_json_area(area)
        for interpretation in aptitude_interpretation_data['Aptitude_Interpretations']:
            if interpretation['Area'] != mapped_area:
                continue
            interpretations.append(deepcopy(interpretation))
            break

    return interpretations


def _resolve_career_link_items(names: list[str]) -> list[dict[str, Any]]:
    """Map career role labels to career detail URLs when a catalog match exists."""
    items: list[dict[str, Any]] = []
    for raw in names or []:
        name = str(raw).strip()
        if not name:
            continue
        url = None
        try:
            from careers.models import Career
            from django.urls import reverse

            career = Career.objects.filter(name__iexact=name).first()
            if not career:
                career = Career.objects.filter(name__icontains=name[:50]).first()
            if career:
                url = reverse(
                    'careers:careerdetail',
                    kwargs={'slug': career.slug, 'career_id': career.id},
                )
        except Exception:
            url = None
        items.append({'name': name, 'url': url})
    return items


def build_class12_consolidated_aptitude_mapping(
    high_categories: dict[str, Any] | Any,
    *,
    mode: str | None = None,
    resolve_role_urls: bool = False,
) -> dict[str, Any] | None:
    """
    Build combined-report ``aptitude_mapping`` from consolidated admin data.

    Uses CLASS12_APTITUDE_CONSOLIDATED_DISPLAY_MODE (single vs combined tiers).
    """
    tier_ctx = resolve_class12_consolidated_tiers(high_categories, mode=mode)
    if tier_ctx.get('note_only'):
        return None

    row = tier_ctx.get('consolidated_row')
    if not row:
        return None

    cluster_names = [str(name).strip() for name in (row.get('career_clusters') or []) if str(name).strip()]
    role_names = [str(name).strip() for name in (row.get('career_pathways') or []) if str(name).strip()]
    pathway_names = [str(name).strip() for name in (row.get('degree_pathways') or []) if str(name).strip()]

    if not (cluster_names or role_names or pathway_names):
        return None

    clusters = [{'name': name, 'url': None} for name in cluster_names]
    pathways = [{'name': name, 'url': None} for name in pathway_names]
    if resolve_role_urls:
        roles = _resolve_career_link_items(role_names)
    else:
        roles = [{'name': name, 'url': None} for name in role_names]

    return {
        'aptitude_code': tier_ctx.get('combination_key', ''),
        'aptitude_areas': list(tier_ctx.get('display_areas') or []),
        'clusters': clusters,
        'roles': roles,
        'pathways': pathways,
        'tier_used': tier_ctx.get('tier_used'),
        'display_mode': tier_ctx.get('display_mode'),
        'source': 'class12_consolidated',
    }


def build_consolidated_profile_for_student(
    high_categories: dict[str, list[str]],
    aptitude_interpretation_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    tier_ctx = resolve_class12_consolidated_tiers(high_categories)
    if tier_ctx.get('note_only'):
        return {
            'note_only': True,
            'tier_used': tier_ctx.get('tier_used', 'below_avg'),
            'display_mode': tier_ctx.get('display_mode'),
        }

    row = tier_ctx.get('consolidated_row')
    if not row:
        return None

    return build_consolidated_profile(
        row,
        tier_ctx.get('combination_key', ''),
        aptitude_interpretation_data=aptitude_interpretation_data,
        primary_area=tier_ctx.get('primary_area'),
        display_areas=tier_ctx.get('display_areas', []),
        tier_used=tier_ctx.get('tier_used', 'combined'),
        display_mode=tier_ctx.get('display_mode'),
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
    tier_ctx = resolve_class12_consolidated_tiers(hc)
    consolidated_profile = build_consolidated_profile_for_student(
        hc,
        aptitude_interpretation_data,
    )
    ctx: dict[str, Any] = {
        'aptitude_improvement_plan': hexaco_recommendations.get('aptitude_improvement_plan', []),
        'aptitude_strength_narrative': hexaco_recommendations.get('aptitude_strength_narrative', []),
        'aptitude_Recommended_College_Courses': hexaco_recommendations.get(
            'aptitude_Recommended_College_Courses', []
        ),
        'aptitude_roles_guidance': hexaco_recommendations.get('aptitude_roles_guidance', []),
        'aptitude_interpretations': build_aptitude_interpretations(hc, aptitude_interpretation_data),
        'class12_aptitude_consolidated_profile': consolidated_profile,
        'class12_aptitude_combination_key': hexaco_recommendations.get('class12_aptitude_combination_key'),
        'class12_aptitude_display_mode': tier_ctx.get('display_mode'),
        'class12_consolidated_tier_used': tier_ctx.get('tier_used'),
        'class12_consolidated_note_only': tier_ctx.get('note_only', False),
        'aptitude_improvement_note': APTITUDE_IMPROVEMENT_NOTE,
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
    below_areas: list[str] | None = None,
) -> str | None:
    """
    Replace strength / college / role lists with consolidated JSON when a row exists.
    Returns the combination key used, or None.
    """
    tier_ctx = resolve_class12_consolidated_tiers(
        {
            'Above Average': above_areas or [],
            'Average': average_areas or [],
            'Below Average': below_areas or [],
        }
    )
    if tier_ctx.get('note_only'):
        return None

    consolidated_row = tier_ctx.get('consolidated_row')
    if not consolidated_row:
        return None

    strength, colleges, roles = build_consolidated_recommendation_lists(consolidated_row)
    result['aptitude_strength_narrative'] = strength
    result['aptitude_Recommended_College_Courses'] = colleges
    result['aptitude_roles_guidance'] = roles
    key = tier_ctx.get('combination_key', '')
    result['class12_aptitude_combination_key'] = key
    result['class12_aptitude_display_mode'] = tier_ctx.get('display_mode')
    result['class12_consolidated_tier_used'] = tier_ctx.get('tier_used')
    return key
