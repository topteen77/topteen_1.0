from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field

from django.db import transaction

from core import choices
from core.choices import ReasoningArea
from core.models import VocationalCourse, VocationalCourseReasoningMapping

EXPORT_VERSION = 1

OBJECT_STATUS_LABEL = {
    choices.ObjectStatus.ACTIVE: 'active',
    choices.ObjectStatus.INACTIVE: 'inactive',
    choices.ObjectStatus.DELETED: 'deleted',
}


def _object_status_label(status):
    return OBJECT_STATUS_LABEL.get(status, str(status))


def _course_row(course):
    return {
        'id': course.pk,
        'name': course.name,
        'category': course.category.name if course.category_id else '',
        'object_status': _object_status_label(course.object_status),
    }


def build_export_payload():
    courses = list(
        VocationalCourse.objects.filter(object_status=choices.ObjectStatus.ACTIVE)
        .select_related('category')
        .order_by('name')
    )
    mappings_qs = (
        VocationalCourseReasoningMapping.objects.filter(object_status=choices.ObjectStatus.ACTIVE)
        .select_related('vocational_course')
        .order_by('reasoning_area', 'priority', 'vocational_course__name')
    )
    mapped_course_ids = set(mappings_qs.values_list('vocational_course_id', flat=True))
    mappings = [
        {
            'course_id': mapping.vocational_course_id,
            'course_name': mapping.vocational_course.name,
            'reasoning_area': mapping.reasoning_area,
            'priority': mapping.priority,
        }
        for mapping in mappings_qs
    ]
    return {
        'version': EXPORT_VERSION,
        'reasoning_area_choices': ReasoningArea.ALL,
        'courses': [_course_row(course) for course in courses],
        'mappings': mappings,
        'unmapped_course_ids': [course.pk for course in courses if course.pk not in mapped_course_ids],
    }


def export_json_bytes():
    return json.dumps(build_export_payload(), indent=2).encode('utf-8')


def _csv_mappings_rows(mappings):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['course_id', 'course_name', 'reasoning_area', 'priority'])
    for row in mappings:
        writer.writerow([
            row['course_id'],
            row['course_name'],
            row['reasoning_area'],
            row['priority'],
        ])
    return buffer.getvalue()


def _csv_catalog_rows(courses):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['# reasoning_area_choices: ' + '|'.join(ReasoningArea.ALL)])
    writer.writerow(['id', 'name', 'category', 'object_status'])
    for row in courses:
        writer.writerow([row['id'], row['name'], row['category'], row['object_status']])
    return buffer.getvalue()


def export_csv_zip_bytes():
    payload = build_export_payload()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('vocational_courses_catalog.csv', _csv_catalog_rows(payload['courses']))
        zf.writestr('vocational_reasoning_mappings.csv', _csv_mappings_rows(payload['mappings']))
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
        return data['mappings']
    if isinstance(data, list):
        return data
    raise ValueError('JSON must be an object with a "mappings" array or a list of mapping rows.')


def _parse_mappings_from_csv(raw_bytes):
    text = raw_bytes.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError('CSV has no header row.')
    required = {'course_id', 'reasoning_area'}
    missing = required - {h.strip().lower() for h in reader.fieldnames if h}
    if missing:
        raise ValueError(f'CSV missing required columns: {", ".join(sorted(missing))}')
    field_map = {name.strip().lower(): name for name in reader.fieldnames if name}
    rows = []
    for line_no, row in enumerate(reader, start=2):
        if not any((value or '').strip() for value in row.values()):
            continue
        rows.append({
            'course_id': row.get(field_map.get('course_id', 'course_id'), '').strip(),
            'course_name': row.get(field_map.get('course_name', 'course_name'), '').strip(),
            'reasoning_area': row.get(field_map.get('reasoning_area', 'reasoning_area'), '').strip().upper(),
            'priority': row.get(field_map.get('priority', 'priority'), '1').strip() or '1',
            '_line': line_no,
        })
    return rows


def _normalize_mapping_rows(rows):
    normalized = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        line = row.get('_line', index)
        try:
            course_id = int(row.get('course_id'))
        except (TypeError, ValueError):
            normalized.append({'error': f'Line {line}: invalid course_id "{row.get("course_id")}".'})
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
        key = (course_id, area)
        if key in seen:
            normalized.append({'error': f'Line {line}: duplicate mapping for course_id={course_id}, area={area}.'})
            continue
        seen.add(key)
        normalized.append({
            'course_id': course_id,
            'reasoning_area': area,
            'priority': priority,
            'line': line,
        })
    return normalized


def import_mappings(raw_bytes, filename='', *, dry_run=False, replace_all=False):
    filename_lower = (filename or '').lower()
    if filename_lower.endswith('.json'):
        rows = _parse_mappings_from_json(raw_bytes)
    else:
        rows = _parse_mappings_from_csv(raw_bytes)

    normalized = _normalize_mapping_rows(rows)
    result = ImportResult()
    valid_rows = []
    for item in normalized:
        if 'error' in item:
            result.errors.append(item['error'])
        else:
            valid_rows.append(item)

    if result.errors:
        return result

    course_ids = {row['course_id'] for row in valid_rows}
    existing_courses = set(
        VocationalCourse.objects.filter(pk__in=course_ids).values_list('pk', flat=True)
    )
    for row in valid_rows:
        if row['course_id'] not in existing_courses:
            result.errors.append(
                f'Line {row["line"]}: course_id {row["course_id"]} does not exist.'
            )
    if result.errors:
        return result

    incoming_keys = {(row['course_id'], row['reasoning_area']) for row in valid_rows}

    def apply():
        existing = {
            (mapping.vocational_course_id, mapping.reasoning_area): mapping
            for mapping in VocationalCourseReasoningMapping.objects.complete().filter(
                vocational_course_id__in=course_ids,
            )
        }
        for row in valid_rows:
            key = (row['course_id'], row['reasoning_area'])
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
                VocationalCourseReasoningMapping.objects.create(
                    vocational_course_id=row['course_id'],
                    reasoning_area=row['reasoning_area'],
                    priority=row['priority'],
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                result.created += 1

        if replace_all:
            for mapping in VocationalCourseReasoningMapping.objects.complete().filter(
                object_status=choices.ObjectStatus.ACTIVE,
            ):
                key = (mapping.vocational_course_id, mapping.reasoning_area)
                if key not in incoming_keys:
                    mapping.object_status = choices.ObjectStatus.DELETED
                    mapping.save()
                    result.deleted += 1

    if dry_run:
        with transaction.atomic():
            apply()
            transaction.set_rollback(True)
    else:
        with transaction.atomic():
            apply()

    return result
