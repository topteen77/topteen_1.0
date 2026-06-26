"""CSV export / import for Class 12 aptitude consolidated report admin rows."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.class12_aptitude_consolidated_io import normalize_combination_key
from app.class12_aptitude_signs_impact import bullets_to_text, text_to_bullets

CSV_COLUMNS = (
    'reasoning_combination',
    'aptitude_description',
    'real_life_signs',
    'daily_life_impact',
    'interpretation_narrative',
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
    from app.models import Class12AptitudeConsolidatedReport

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction='ignore')
    writer.writeheader()

    for row in Class12AptitudeConsolidatedReport.objects.order_by('reasoning_combination'):
        writer.writerow({
            'reasoning_combination': row.reasoning_combination,
            'aptitude_description': row.aptitude_description or '',
            'real_life_signs': bullets_to_text(row.real_life_signs or []),
            'daily_life_impact': bullets_to_text(row.daily_life_impact or []),
            'interpretation_narrative': row.interpretation_narrative or '',
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

            defaults = {
                'codes': codes,
                'aptitude_description': row.get('aptitude_description') or '',
                'real_life_signs': text_to_bullets(row.get('real_life_signs', '')),
                'daily_life_impact': text_to_bullets(row.get('daily_life_impact', '')),
                'interpretation_narrative': row.get('interpretation_narrative') or '',
                'career_clusters': _parse_json_cell(row.get('career_clusters', '')),
                'career_pathways': _parse_json_cell(row.get('career_pathways', '')),
                'degree_pathways': _parse_json_cell(row.get('degree_pathways', '')),
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
