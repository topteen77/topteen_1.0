"""Lookup and import helpers for admin-managed aptitude improvement plans."""

from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

from app_post_matric.aptitude_area_labels import resolve_aptitude_json_area

CLASS_10 = 'class_10'
CLASS_12 = 'class_12'

CLASS_12_AREA_ALIASES = {
    'language skills': 'language_skills',
    'language and verbal reasoning': 'language_verbal_reasoning',
    'language & verbal reasoning': 'language_verbal_reasoning',
    'language & verbal reasoning (lvr)': 'language_verbal_reasoning',
    'abstract reasoning': 'abstract_reasoning',
    'abstract reasoning (ar)': 'abstract_reasoning',
    'critical reasoning': 'critical_logical_reasoning',
    'logical reasoning': 'critical_logical_reasoning',
    'critical / logical reasoning': 'critical_logical_reasoning',
    'critical / logical reasoning (lr)': 'critical_logical_reasoning',
    'numerical reasoning': 'numerical_reasoning',
    'numerical reasoning (nr)': 'numerical_reasoning',
    'clerical speed & accuracy': 'clerical_reasoning',
    'clerical speed and accuracy': 'clerical_reasoning',
    'clerical reasoning': 'clerical_reasoning',
    'clerical reasoning (cr)': 'clerical_reasoning',
    'mechanical reasoning': 'mechanical_reasoning',
    'mechanical reasoning (mr)': 'mechanical_reasoning',
    'spatial reasoning': 'spatial_reasoning',
    'spatial reasoning (sr)': 'spatial_reasoning',
}

CLASS_10_AREA_ALIASES = {
    'VERBAL': 'verbal',
    'LOGICAL': 'logical',
    'SPATIAL': 'spatial',
    'CRITICAL': 'critical',
    'LANGUAGE': 'language',
    'NUMERICAL': 'numerical',
    'MECHANICAL': 'mechanical',
}

CLASS_10_SEED_FROM_CLASS_12 = {
    'verbal': 'language_verbal_reasoning',
    'logical': 'critical_logical_reasoning',
    'spatial': 'spatial_reasoning',
    'critical': 'critical_logical_reasoning',
    'language': 'language_skills',
    'numerical': 'numerical_reasoning',
    'mechanical': 'mechanical_reasoning',
}

CLASS_10_DISPLAY_TITLES = {
    'verbal': 'Verbal',
    'logical': 'Logical',
    'spatial': 'Spatial',
    'critical': 'Critical',
    'language': 'Language',
    'numerical': 'Numerical',
    'mechanical': 'Mechanical',
}


def _normalize_lookup(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def resolve_improvement_plan_area_key(area, education_level=CLASS_12) -> str | None:
    """Map a student below-average label to a stable plan area_key."""
    if not area:
        return None
    if education_level == CLASS_10:
        token = str(area).strip().upper()
        if token in CLASS_10_AREA_ALIASES:
            return CLASS_10_AREA_ALIASES[token]
        first = re.split(r'[\s_]+', token)[0] if token else ''
        return CLASS_10_AREA_ALIASES.get(first)

    resolved = resolve_aptitude_json_area(str(area))
    lookup = _normalize_lookup(resolved)
    if lookup in CLASS_12_AREA_ALIASES:
        return CLASS_12_AREA_ALIASES[lookup]
    compact = re.sub(r'[^a-z0-9]+', '_', lookup).strip('_')
    return compact or None


def plan_to_report_dict(plan) -> dict:
    """Serialize a model row for aptitude report templates."""
    return {
        'Area': plan.growth_area_title,
        'GrowthArea': plan.growth_area_title,
        'Remarks': list(plan.improvement_plan_items or []),
        'SuggestedImprovementPlan': list(plan.improvement_plan_items or []),
        'Duration': plan.expected_timeline or '',
        'ExpectedTimeline': plan.expected_timeline or '',
        'Category': 'Below Average',
        'DevelopmentGoal': plan.development_goal or '',
        'PracticeFrequency': plan.practice_frequency or '',
        'area_key': plan.area_key,
    }


def normalize_report_plan(plan: dict) -> dict:
    """Ensure all five doc fields are present for templates."""
    area = plan.get('GrowthArea') or plan.get('Area') or ''
    remarks = plan.get('SuggestedImprovementPlan') or plan.get('Remarks') or []
    timeline = plan.get('ExpectedTimeline') or plan.get('Duration') or ''
    return {
        'Area': area,
        'GrowthArea': area,
        'DevelopmentGoal': plan.get('DevelopmentGoal') or '',
        'SuggestedImprovementPlan': list(remarks),
        'Remarks': list(remarks),
        'PracticeFrequency': plan.get('PracticeFrequency') or '',
        'Duration': timeline,
        'ExpectedTimeline': timeline,
        'Category': plan.get('Category') or 'Below Average',
        'area_key': plan.get('area_key') or '',
    }


def enrich_plan_dict_from_db(plan: dict, education_level=CLASS_12) -> dict:
    """Fill missing doc fields from admin DB when a matching area exists."""
    from app.models import AptitudeImprovementPlan

    area_key = plan.get('area_key') or resolve_improvement_plan_area_key(
        plan.get('Area') or plan.get('GrowthArea'),
        education_level=education_level,
    )
    if area_key:
        row = (
            AptitudeImprovementPlan.objects.filter(
                education_level=education_level,
                area_key=area_key,
                is_active=True,
            )
            .order_by('sort_order', 'id')
            .first()
        )
        if row:
            return plan_to_report_dict(row)
    return normalize_report_plan({**plan, 'area_key': area_key or ''})


def build_improvement_plans_for_below_areas(below_areas, education_level=CLASS_12) -> list[dict]:
    """Return active admin plans for the student's below-average reasoning areas."""
    from app.models import AptitudeImprovementPlan

    if not below_areas or not isinstance(below_areas, list):
        return []

    plans = []
    seen_keys = set()
    for area in below_areas:
        area_key = resolve_improvement_plan_area_key(area, education_level=education_level)
        if not area_key or area_key in seen_keys:
            continue
        seen_keys.add(area_key)
        row = (
            AptitudeImprovementPlan.objects.filter(
                education_level=education_level,
                area_key=area_key,
                is_active=True,
            )
            .order_by('sort_order', 'id')
            .first()
        )
        if row:
            plans.append(normalize_report_plan(plan_to_report_dict(row)))
    return plans


def merge_improvement_plans(below_areas, json_plans, education_level=CLASS_12) -> list[dict]:
    """
    Prefer admin-managed plans; fall back to legacy JSON rows enriched from admin when possible.
    """
    db_plans = build_improvement_plans_for_below_areas(below_areas, education_level=education_level)
    if db_plans:
        return db_plans

    if not json_plans or not below_areas:
        return [normalize_report_plan(p) for p in (json_plans or [])]

    below_resolved = {resolve_aptitude_json_area(a) for a in below_areas if a}
    merged = []
    for plan in json_plans:
        area = plan.get('Area')
        if area and resolve_aptitude_json_area(area) in below_resolved:
            merged.append(enrich_plan_dict_from_db(plan, education_level=education_level))
    if merged:
        return merged
    return [enrich_plan_dict_from_db(p, education_level=education_level) for p in json_plans]


def extract_docx_paragraphs(path: str) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read('word/document.xml')
    root = ET.fromstring(xml)
    paragraphs = []
    for paragraph in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
        texts = [
            node.text or ''
            for node in paragraph.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        ]
        line = ''.join(texts).strip()
        if line:
            paragraphs.append(line)
    return paragraphs


def _area_key_from_doc_title(title: str) -> str:
    lookup = _normalize_lookup(re.sub(r'\s*\([^)]+\)\s*$', '', title).strip())
    if lookup in CLASS_12_AREA_ALIASES:
        return CLASS_12_AREA_ALIASES[lookup]
    return re.sub(r'[^a-z0-9]+', '_', lookup).strip('_')


def parse_improvement_plan_docx(path: str) -> list[dict]:
    """
    Parse the Class 12 improvement-plan docx into structured rows.
    Each block: title, development goal, plan bullets, practice frequency, timeline.
    """
    paragraphs = extract_docx_paragraphs(path)
    header_tokens = {
        'growth area',
        'development goal',
        'suggested improvement plan',
        'practice frequency',
        'expected improvement timeline',
    }
    content = [line for line in paragraphs if _normalize_lookup(line) not in header_tokens]

    rows = []
    index = 0
    while index < len(content):
        title = content[index]
        index += 1
        if index >= len(content):
            break
        development_goal = content[index]
        index += 1
        plan_items = []
        while index < len(content):
            line = content[index]
            if _looks_like_frequency(line):
                break
            plan_items.append(line)
            index += 1
        if index >= len(content):
            break
        practice_frequency = content[index]
        index += 1
        if index >= len(content):
            break
        expected_timeline = content[index]
        index += 1
        rows.append({
            'area_key': _area_key_from_doc_title(title),
            'growth_area_title': title,
            'development_goal': development_goal,
            'improvement_plan_items': plan_items,
            'practice_frequency': practice_frequency,
            'expected_timeline': expected_timeline,
        })
    return rows


def _looks_like_frequency(line: str) -> bool:
    normalized = _normalize_lookup(line)
    if len(line) > 90:
        return False
    if 'sessions/week' in normalized or 'session/week' in normalized:
        return True
    if normalized.startswith('daily'):
        return True
    if re.match(r'^\d+\s*[–-]\s*\d+\s*sessions?', normalized):
        return True
    return False


def upsert_class_12_plans_from_docx(path: str) -> dict:
    from app.models import AptitudeImprovementPlan

    parsed = parse_improvement_plan_docx(path)
    created = updated = 0
    for sort_order, row in enumerate(parsed, start=1):
        obj, was_created = AptitudeImprovementPlan.objects.update_or_create(
            education_level=CLASS_12,
            area_key=row['area_key'],
            defaults={
                'growth_area_title': row['growth_area_title'],
                'development_goal': row['development_goal'],
                'improvement_plan_items': row['improvement_plan_items'],
                'practice_frequency': row['practice_frequency'],
                'expected_timeline': row['expected_timeline'],
                'sort_order': sort_order,
                'is_active': True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {'created': created, 'updated': updated, 'total': len(parsed)}


def seed_class_10_plans_from_class_12() -> dict:
    """Seed Class 10 plans using Class 12 content mapped to seven reasoning areas."""
    from app.models import AptitudeImprovementPlan

    class_12 = {
        row.area_key: row
        for row in AptitudeImprovementPlan.objects.filter(
            education_level=CLASS_12,
            is_active=True,
        )
    }
    created = updated = 0
    for sort_order, (area_key, source_key) in enumerate(CLASS_10_SEED_FROM_CLASS_12.items(), start=1):
        source = class_12.get(source_key)
        if not source:
            continue
        title = CLASS_10_DISPLAY_TITLES.get(area_key, area_key.replace('_', ' ').title())
        obj, was_created = AptitudeImprovementPlan.objects.update_or_create(
            education_level=CLASS_10,
            area_key=area_key,
            defaults={
                'growth_area_title': title,
                'development_goal': source.development_goal,
                'improvement_plan_items': list(source.improvement_plan_items or []),
                'practice_frequency': source.practice_frequency,
                'expected_timeline': source.expected_timeline,
                'sort_order': sort_order,
                'is_active': True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {'created': created, 'updated': updated, 'total': len(CLASS_10_SEED_FROM_CLASS_12)}
