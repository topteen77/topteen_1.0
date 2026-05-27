"""Import manually curated related careers from CSV (admin upload or management command)."""

import csv
import io
import re
from dataclasses import dataclass, field


# Maximum related careers stored per career when importing from CSV.
CSV_IMPORT_MAX_RELATED = 3


@dataclass
class RelatedCareersImportResult:
    updated: int = 0
    skipped: int = 0
    cleared: int = 0
    truncated: int = 0
    errors: list = field(default_factory=list)

    def summary(self):
        return (
            f'Updated: {self.updated}, skipped: {self.skipped}, '
            f'cleared-only: {self.cleared}, truncated to {CSV_IMPORT_MAX_RELATED}: {self.truncated}, '
            f'errors: {len(self.errors)}'
        )


def _split_ids(value):
    if not value or not str(value).strip():
        return []
    parts = re.split(r'[,|;]+', str(value))
    ids = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except (TypeError, ValueError):
            continue
    return ids


def _normalize_header(name):
    return (name or '').strip().lower().replace(' ', '_')


def import_related_careers_from_csv(
    file_obj,
    *,
    dry_run=False,
    clear_existing=False,
    max_related=CSV_IMPORT_MAX_RELATED,
):
    """
    CSV must include career ``id`` and one of:
      - related_career_ids
      - related_careers
      - related career id  (export column name; usually cluster id — ignored unless numeric career ids)

    Extra columns (career name, cluster, etc.) are ignored.
    """
    from careers.models import Career

    if hasattr(file_obj, 'read'):
        raw = file_obj.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(raw))
    else:
        reader = csv.DictReader(file_obj)

    if not reader.fieldnames:
        result = RelatedCareersImportResult()
        result.errors.append('CSV has no header row.')
        return result

    header_map = {_normalize_header(h): h for h in reader.fieldnames}
    id_key = header_map.get('id')
    if not id_key:
        result = RelatedCareersImportResult()
        result.errors.append('CSV must have an "id" column (career id).')
        return result

    related_key = (
        header_map.get('related_career_ids')
        or header_map.get('related_careers')
        or header_map.get('related_career_ids')
    )
    if not related_key:
        result = RelatedCareersImportResult()
        result.errors.append(
            'CSV must have a "related_career_ids" column (comma-separated career ids).'
        )
        return result

    result = RelatedCareersImportResult()
    career_ids = set(Career.objects.values_list('id', flat=True))

    for row_num, row in enumerate(reader, start=2):
        try:
            career_id = int((row.get(id_key) or '').strip())
        except (TypeError, ValueError):
            result.skipped += 1
            result.errors.append(f'Row {row_num}: invalid career id.')
            continue

        if career_id not in career_ids:
            result.skipped += 1
            result.errors.append(f'Row {row_num}: career id {career_id} not found.')
            continue

        related_ids = _split_ids(row.get(related_key))
        related_ids = [i for i in related_ids if i != career_id]
        if len(related_ids) > max_related:
            result.truncated += 1
            result.errors.append(
                f'Row {row_num}: only first {max_related} related career id(s) imported '
                f'(had {len(related_ids)}).'
            )
            related_ids = related_ids[:max_related]
        unknown = [i for i in related_ids if i not in career_ids]
        if unknown:
            result.errors.append(
                f'Row {row_num}: unknown related career id(s): {", ".join(map(str, unknown))}'
            )
            related_ids = [i for i in related_ids if i in career_ids]

        if not related_ids:
            if clear_existing:
                result.cleared += 1
                if not dry_run:
                    Career.objects.get(pk=career_id).related_careers.clear()
            else:
                result.skipped += 1
            continue

        if dry_run:
            result.updated += 1
            continue

        career = Career.objects.get(pk=career_id)
        career.related_careers.set(related_ids)
        result.updated += 1

    return result
