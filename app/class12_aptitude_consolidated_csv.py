"""CSV export / import for Class 12 aptitude consolidated report admin rows."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.class12_aptitude_consolidated_io import normalize_combination_key
from app.class12_aptitude_signs_impact import (
    build_sign_impact_ids_for_codes,
    codes_to_sign_impact_ids,
    parse_code_list,
)

CSV_COLUMNS = (
    'reasoning_combination',
    'aptitude_description',
    'interpretation_narrative',
    'real_life_sign_codes',
    'daily_life_impact_codes',
    'career_clusters',
    'career_pathways',
    'degree_pathways',
    'is_active',
)


def _json_cell(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _parse_json_cell(raw: str, *, default=None):
    text = (raw or '').strip()
    if not text:
        return default if default is not None else []
    if text.startswith('[') or text.startswith('{'):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split('|') if part.strip()]


def export_consolidated_reports_csv() -> str:
    from app.models import (
        Class12AptitudeConsolidatedReport,
        Class12AptitudeDailyLifeImpact,
        Class12AptitudeRealLifeSign,
    )

    sign_code_by_id = {
        row.pk: row.reasoning_code
        for row in Class12AptitudeRealLifeSign.objects.all()
    }
    impact_code_by_id = {
        row.pk: row.reasoning_code
        for row in Class12AptitudeDailyLifeImpact.objects.all()
    }

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction='ignore')
    writer.writeheader()

    for row in Class12AptitudeConsolidatedReport.objects.order_by('reasoning_combination'):
        sign_codes = [
            sign_code_by_id[pk]
            for pk in (row.real_life_sign_ids or [])
            if pk in sign_code_by_id
        ]
        impact_codes = [
            impact_code_by_id[pk]
            for pk in (row.daily_life_impact_ids or [])
            if pk in impact_code_by_id
        ]
        if not sign_codes:
            sign_codes = list(row.codes or [])
        if not impact_codes:
            impact_codes = list(row.codes or [])

        writer.writerow({
            'reasoning_combination': row.reasoning_combination,
            'aptitude_description': row.aptitude_description or '',
            'interpretation_narrative': row.interpretation_narrative or '',
            'real_life_sign_codes': '|'.join(sign_codes),
            'daily_life_impact_codes': '|'.join(impact_codes),
            'career_clusters': _json_cell(row.career_clusters or []),
            'career_pathways': _json_cell(row.career_pathways or []),
            'degree_pathways': _json_cell(row.degree_pathways or []),
            'is_active': '1' if row.is_active else '0',
        })

    return buffer.getvalue()


def import_consolidated_reports_csv(
    uploaded_file,
    *,
    update_existing: bool = True,
) -> dict[str, Any]:
    from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
    from app.models import Class12AptitudeConsolidatedReport

    try:
        raw = uploaded_file.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(raw))
        if not reader.fieldnames:
            return {'ok': False, 'error': 'CSV file is empty or missing a header row.'}

        created = 0
        updated = 0
        skipped = 0
        errors: list[str] = []

        for line_no, row in enumerate(reader, start=2):
            key = normalize_combination_key(row.get('reasoning_combination', ''))
            if not key:
                errors.append(f'Line {line_no}: missing reasoning_combination.')
                continue

            codes = [part.strip() for part in key.split('+') if part.strip()]
            sign_codes = parse_code_list(row.get('real_life_sign_codes', '')) or codes
            impact_codes = parse_code_list(row.get('daily_life_impact_codes', '')) or codes
            sign_ids, impact_ids = codes_to_sign_impact_ids(sign_codes, impact_codes)

            defaults = {
                'codes': codes,
                'aptitude_description': row.get('aptitude_description') or '',
                'interpretation_narrative': row.get('interpretation_narrative') or '',
                'career_clusters': _parse_json_cell(row.get('career_clusters', '')),
                'career_pathways': _parse_json_cell(row.get('career_pathways', '')),
                'degree_pathways': _parse_json_cell(row.get('degree_pathways', '')),
                'real_life_sign_ids': sign_ids,
                'daily_life_impact_ids': impact_ids,
                'is_active': str(row.get('is_active', '1')).strip().lower() in ('1', 'true', 'yes'),
            }

            existing = Class12AptitudeConsolidatedReport.objects.filter(
                reasoning_combination=key,
            ).first()
            if existing:
                if not update_existing:
                    skipped += 1
                    continue
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                updated += 1
            else:
                Class12AptitudeConsolidatedReport.objects.create(
                    reasoning_combination=key,
                    **defaults,
                )
                created += 1

        clear_consolidated_lookup_cache()
        return {
            'ok': True,
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'errors': errors,
        }
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def rebuild_consolidated_sign_impact_ids_from_codes() -> int:
    from app.class12_aptitude_report_utils import clear_consolidated_lookup_cache
    from app.models import Class12AptitudeConsolidatedReport

    count = 0
    for row in Class12AptitudeConsolidatedReport.objects.all():
        sign_ids, impact_ids = build_sign_impact_ids_for_codes(list(row.codes or []))
        row.real_life_sign_ids = sign_ids
        row.daily_life_impact_ids = impact_ids
        row.save(update_fields=['real_life_sign_ids', 'daily_life_impact_ids', 'modified'])
        count += 1
    clear_consolidated_lookup_cache()
    return count
