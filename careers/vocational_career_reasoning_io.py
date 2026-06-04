from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field

from django.db import transaction

from careers.models import Career, VocationalCareerReasoningMapping
from careers.vocational_cluster import vocational_career_cluster_id
from core import choices
from core.choices import ReasoningArea

EXPORT_VERSION = 1

PUBLISH_STATUS_LABEL = {
    choices.PublishStatus.PUBLISHED: 'published',
    choices.PublishStatus.DRAFT: 'draft',
}


def _published_vocational_careers_qs():
    cluster_id = vocational_career_cluster_id()
    return Career.objects.filter(
        career_cluster__id=cluster_id,
        publish_status=choices.PublishStatus.PUBLISHED,
        object_status=choices.ObjectStatus.ACTIVE,
    ).distinct().order_by('name')


def _career_row(career):
    return {
        'id': career.pk,
        'name': career.name,
        'slug': career.slug,
        'cluster_id': vocational_career_cluster_id(),
        'publish_status': PUBLISH_STATUS_LABEL.get(career.publish_status, str(career.publish_status)),
    }


def build_export_payload():
    careers = list(_published_vocational_careers_qs())
    mappings_qs = (
        VocationalCareerReasoningMapping.objects.filter(object_status=choices.ObjectStatus.ACTIVE)
        .select_related('career')
        .filter(career__in=[c.pk for c in careers])
        .order_by('reasoning_area', 'priority', 'career__name')
    )
    mapped_career_ids = set(mappings_qs.values_list('career_id', flat=True))
    mappings = [
        {
            'career_id': mapping.career_id,
            'career_name': mapping.career.name,
            'reasoning_area': mapping.reasoning_area,
            'priority': mapping.priority,
        }
        for mapping in mappings_qs
    ]
    return {
        'version': EXPORT_VERSION,
        'vocational_cluster_id': vocational_career_cluster_id(),
        'reasoning_area_choices': ReasoningArea.ALL,
        'careers': [_career_row(career) for career in careers],
        'mappings': mappings,
        'unmapped_career_ids': [career.pk for career in careers if career.pk not in mapped_career_ids],
    }


def export_json_bytes():
    return json.dumps(build_export_payload(), indent=2).encode('utf-8')


def _csv_mappings_rows(mappings):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['career_id', 'career_name', 'reasoning_area', 'priority'])
    for row in mappings:
        writer.writerow([
            row['career_id'],
            row['career_name'],
            row['reasoning_area'],
            row['priority'],
        ])
    return buffer.getvalue()


def _csv_catalog_rows(careers):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['# reasoning_area_choices: ' + '|'.join(ReasoningArea.ALL)])
    writer.writerow(['id', 'name', 'slug', 'publish_status'])
    for row in careers:
        writer.writerow([row['id'], row['name'], row['slug'], row['publish_status']])
    return buffer.getvalue()


def export_csv_zip_bytes():
    payload = build_export_payload()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('vocational_careers_catalog.csv', _csv_catalog_rows(payload['careers']))
        zf.writestr('vocational_career_reasoning_mappings.csv', _csv_mappings_rows(payload['mappings']))
    zip_buffer.seek(0)
    return zip_buffer.read()


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors


def _parse_mappings_from_json(raw_bytes):
    data = json.loads(raw_bytes.decode('utf-8'))
    if isinstance(data, dict) and 'mappings' in data:
        rows = data['mappings']
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError('JSON must be an object with a "mappings" array or a list of mapping rows.')
    if rows and isinstance(rows[0], dict) and 'course_id' in rows[0] and 'career_id' not in rows[0]:
        raise ValueError(
            'This JSON is from vocational COURSE reasoning export (course_id). '
            'Export JSON from Careers → Vocational career reasoning mappings instead.'
        )
    return rows


def _normalize_name_key(name):
    return re.sub(r'[^a-z0-9]+', ' ', (name or '').lower()).strip()


def _reasoning_area_from_label(label):
    text = (label or '').strip()
    if not text:
        return None
    upper = text.upper()
    if ReasoningArea.is_valid(upper):
        return upper
    for code, area_label in ReasoningArea.CHOICES:
        if area_label.lower() == text.lower():
            return code
    token = text.split()[0].upper() if text else ''
    return token if ReasoningArea.is_valid(token) else None


def _career_lookup_tables(careers):
    by_exact = {}
    by_norm = {}
    for career in careers:
        exact = (career.name or '').strip().lower()
        if exact and exact not in by_exact:
            by_exact[exact] = career
        norm = _normalize_name_key(career.name)
        if norm and norm not in by_norm:
            by_norm[norm] = career
    return by_exact, by_norm


def _resolve_career_by_name(name, careers, by_exact, by_norm):
    """Match CSV career name to DB career by exact or normalized name only (no fuzzy guess)."""
    raw = (name or '').strip()
    if not raw:
        return None
    career = by_exact.get(raw.lower())
    if career:
        return career
    return by_norm.get(_normalize_name_key(raw))


def _parse_mappings_from_csv(raw_bytes):
    text = raw_bytes.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError('CSV has no header row.')
    field_map = {name.strip().lower(): name for name in reader.fieldnames if name}
    headers = set(field_map.keys())
    if 'course_id' in headers and 'career_id' not in headers:
        raise ValueError(
            'This CSV is from vocational COURSE export (course_id column). '
            'Use vocational_career_reasoning_mappings.csv from the career reasoning Export CSV (zip).'
        )

    career_col = field_map.get('career') or field_map.get('career name') or field_map.get('career_name')
    area_col = (
        field_map.get('dominant reasoning area')
        or field_map.get('reasoning_area')
        or field_map.get('reasoning area')
    )
    if not area_col:
        for key, orig in field_map.items():
            if 'reasoning' in key:
                area_col = orig
                break

    parse_errors = []
    rows = []

    if career_col and area_col and 'career_id' not in headers:
        careers = list(_published_vocational_careers_qs())
        by_exact, by_norm = _career_lookup_tables(careers)
        for line_no, row in enumerate(reader, start=2):
            if not any((value or '').strip() for value in row.values()):
                continue
            name = (row.get(career_col) or '').strip()
            area_label = (row.get(area_col) or '').strip()
            if not name:
                parse_errors.append(f'Line {line_no}: missing career name.')
                continue
            area = _reasoning_area_from_label(area_label)
            if not area:
                parse_errors.append(
                    f'Line {line_no}: invalid reasoning area "{area_label}" for career "{name}".'
                )
                continue
            career = _resolve_career_by_name(name, careers, by_exact, by_norm)
            if not career:
                parse_errors.append(f'Line {line_no}: no published vocational career matched "{name}".')
                continue
            rows.append({
                'career_id': str(career.pk),
                'career_name': career.name,
                'reasoning_area': area,
                'priority': '1',
                '_line': line_no,
            })
        return rows, parse_errors, True

    required = {'career_id', 'reasoning_area'}
    missing = required - headers
    if missing:
        raise ValueError(f'CSV missing required columns: {", ".join(sorted(missing))}')
    for line_no, row in enumerate(reader, start=2):
        if not any((value or '').strip() for value in row.values()):
            continue
        rows.append({
            'career_id': row.get(field_map.get('career_id', 'career_id'), '').strip(),
            'career_name': row.get(field_map.get('career_name', 'career_name'), '').strip(),
            'reasoning_area': row.get(field_map.get('reasoning_area', 'reasoning_area'), '').strip().upper(),
            'priority': row.get(field_map.get('priority', 'priority'), '1').strip() or '1',
            '_line': line_no,
        })
    return rows, parse_errors, False


def _normalize_mapping_rows(rows):
    normalized = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        line = row.get('_line', index)
        try:
            career_id = int(row.get('career_id'))
        except (TypeError, ValueError):
            normalized.append({'error': f'Line {line}: invalid career_id "{row.get("career_id")}".'})
            continue
        area = str(row.get('reasoning_area', '')).strip().upper()
        if not ReasoningArea.is_valid(area):
            normalized.append({'error': f'Line {line}: invalid reasoning_area "{area}".'})
            continue
        try:
            priority = int(row.get('priority', 1))
        except (TypeError, ValueError):
            normalized.append({'error': f'Line {line}: invalid priority "{row.get("priority")}".'})
            continue
        if priority < 1:
            normalized.append({'error': f'Line {line}: priority must be >= 1.'})
            continue
        key = (career_id, area)
        if key in seen:
            normalized.append({'error': f'Line {line}: duplicate mapping for career_id={career_id}, area={area}.'})
            continue
        seen.add(key)
        normalized.append({
            'career_id': career_id,
            'reasoning_area': area,
            'priority': priority,
            'line': line,
        })
    return normalized


def _extract_import_payload(raw_bytes, filename=''):
    """Accept .json, .csv, or .zip (CSV/JSON inside export zip)."""
    filename_lower = (filename or '').lower()
    if not filename_lower.endswith('.zip'):
        return raw_bytes, filename_lower

    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        names = [n for n in zf.namelist() if not n.startswith('__MACOSX')]
        preferred_csv = 'vocational_career_reasoning_mappings.csv'
        preferred_json = 'vocational_career_reasoning_mappings.json'
        if preferred_json in names:
            return zf.read(preferred_json), '.json'
        if preferred_csv in names:
            return zf.read(preferred_csv), '.csv'
        json_files = [n for n in names if n.lower().endswith('.json')]
        csv_files = [n for n in names if n.lower().endswith('.csv') and 'catalog' not in n.lower()]
        if len(json_files) == 1:
            return zf.read(json_files[0]), '.json'
        if len(csv_files) == 1:
            return zf.read(csv_files[0]), '.csv'
        raise ValueError(
            'Zip must contain vocational_career_reasoning_mappings.csv or .json. '
            f'Found: {", ".join(names[:8])}{"..." if len(names) > 8 else ""}'
        )


def import_mappings(raw_bytes, filename='', *, dry_run=False, replace_all=False):
    try:
        payload_bytes, kind = _extract_import_payload(raw_bytes, filename)
    except (zipfile.BadZipFile, ValueError) as exc:
        result = ImportResult()
        result.errors.append(str(exc))
        return result
    except Exception as exc:
        result = ImportResult()
        result.errors.append(f'Could not read upload: {exc}')
        return result

    try:
        dominant_area_import = False
        if kind.endswith('.json') or (filename or '').lower().endswith('.json'):
            rows = _parse_mappings_from_json(payload_bytes)
            parse_errors = []
        else:
            rows, parse_errors, dominant_area_import = _parse_mappings_from_csv(payload_bytes)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        result = ImportResult()
        result.errors.append(str(exc))
        return result

    normalized = _normalize_mapping_rows(rows)
    result = ImportResult()
    result.errors.extend(parse_errors)
    valid_rows = []
    for item in normalized:
        if 'error' in item:
            result.errors.append(item['error'])
        else:
            valid_rows.append(item)

    if not valid_rows:
        return result

    career_ids = {row['career_id'] for row in valid_rows}
    allowed_career_ids = set(_published_vocational_careers_qs().filter(pk__in=career_ids).values_list('pk', flat=True))
    for row in valid_rows:
        if row['career_id'] not in allowed_career_ids:
            result.errors.append(
                f'Line {row["line"]}: career_id {row["career_id"]} is not a published career '
                f'in vocational cluster {vocational_career_cluster_id()}.'
            )
    valid_rows = [row for row in valid_rows if row['career_id'] in allowed_career_ids]
    if not valid_rows:
        return result

    incoming_keys = {(row['career_id'], row['reasoning_area']) for row in valid_rows}

    def apply():
        existing = {
            (mapping.career_id, mapping.reasoning_area): mapping
            for mapping in VocationalCareerReasoningMapping.objects.complete().filter(
                career_id__in=career_ids,
            )
        }
        for row in valid_rows:
            key = (row['career_id'], row['reasoning_area'])
            mapping = existing.get(key)
            if mapping:
                changed = False
                if mapping.priority != row['priority']:
                    mapping.priority = row['priority']
                    changed = True
                if mapping.object_status != choices.ObjectStatus.ACTIVE:
                    mapping.object_status = choices.ObjectStatus.ACTIVE
                    changed = True
                if changed:
                    mapping.save()
                    result.updated += 1
            else:
                VocationalCareerReasoningMapping.objects.create(
                    career_id=row['career_id'],
                    reasoning_area=row['reasoning_area'],
                    priority=row['priority'],
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                result.created += 1

        if replace_all or dominant_area_import:
            scope_career_ids = {row['career_id'] for row in valid_rows}
            qs = VocationalCareerReasoningMapping.objects.complete().filter(
                object_status=choices.ObjectStatus.ACTIVE,
            )
            if dominant_area_import and not replace_all:
                qs = qs.filter(career_id__in=scope_career_ids)
            for mapping in qs:
                key = (mapping.career_id, mapping.reasoning_area)
                if key not in incoming_keys:
                    mapping.object_status = choices.ObjectStatus.DELETED
                    mapping.save()
                    result.deleted += 1

    try:
        if dry_run:
            with transaction.atomic():
                apply()
                transaction.set_rollback(True)
        else:
            with transaction.atomic():
                apply()
    except Exception as exc:
        result.errors.append(f'Import failed while saving: {exc}')

    return result
