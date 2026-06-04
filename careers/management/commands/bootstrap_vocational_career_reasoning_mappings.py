from __future__ import annotations

import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.models import Career, VocationalCareerReasoningMapping
from careers.vocational_career_reasoning_io import export_csv_zip_bytes, export_json_bytes
from careers.vocational_cluster import vocational_career_cluster_id
from core import choices
from core.models import VocationalCourseReasoningMapping

LEGACY_BELOW_AREA_TO_CAREER_NAMES = {
    'NUMERICAL': ['Data Analyst', 'Accountant', 'Actuary'],
    'VERBAL': ['Media & Communication Professional', 'Content Writer', 'Journalist'],
    'LOGICAL': ['Software Developer', 'Computer Programmer', 'IT Support Specialist'],
    'MECHANICAL': ['Automobile Technician', 'Mechanical Engineer', 'Aerospace Engineer'],
    'SPATIAL': ['Fashion Designer', 'Interior Designer', 'Graphic Designer'],
    'LANGUAGE': ['Translator', 'Foreign Language Specialist', 'Content Writer'],
    'CRITICAL': ['Lawyer', 'Legal Researcher', 'Policy Analyst'],
}

_PREFIX_RE = re.compile(
    r'^(b\.?\s*voc\.?\s+in\s+|certificate\s+in\s+|diploma\s+in\s+|basics?\s+of\s+|basic\s+)',
    re.IGNORECASE,
)


def _normalize_lookup_name(name):
    text = (name or '').strip().lower()
    text = _PREFIX_RE.sub('', text)
    return re.sub(r'\s+', ' ', text).strip()


def _vocational_careers_by_name():
    cluster_id = vocational_career_cluster_id()
    careers = Career.objects.filter(
        career_cluster__id=cluster_id,
        publish_status=choices.PublishStatus.PUBLISHED,
        object_status=choices.ObjectStatus.ACTIVE,
    ).distinct()
    by_exact = {}
    by_normalized = {}
    for career in careers:
        raw = (career.name or '').strip().lower()
        if raw and raw not in by_exact:
            by_exact[raw] = career
        norm = _normalize_lookup_name(career.name)
        if norm and norm not in by_normalized:
            by_normalized[norm] = career
    return by_exact, by_normalized


def _resolve_career_for_course(course_name, by_exact, by_normalized):
    raw = (course_name or '').strip().lower()
    if raw in by_exact:
        return by_exact[raw]
    norm = _normalize_lookup_name(course_name)
    if norm in by_normalized:
        return by_normalized[norm]
    if norm:
        matches = [c for key, c in by_normalized.items() if norm in key or key in norm]
        if len(matches) == 1:
            return matches[0]
    return None


def _resolve_career_by_keyword(name, by_exact, by_normalized):
    raw = (name or '').strip().lower()
    career = by_exact.get(raw) or by_normalized.get(_normalize_lookup_name(name))
    if career:
        return career
    token = raw.split()[0] if raw else ''
    if len(token) < 4:
        return None
    matches = [c for key, c in by_normalized.items() if token in key]
    if len(matches) == 1:
        return matches[0]
    return matches[0] if matches else None


class Command(BaseCommand):
    help = (
        'Export vocational career reasoning mappings and optionally seed from '
        'existing course mappings or the legacy area keyword map.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--export-only', action='store_true')
        parser.add_argument('--output-dir', default='.')
        parser.add_argument(
            '--from-course-mappings',
            action='store_true',
            help='Create career mappings by matching vocational course reasoning mappings',
        )
        parser.add_argument(
            '--seed-legacy',
            action='store_true',
            help='Create mappings from legacy area→career keyword map',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        export_only = bool(options['export_only'])
        from_courses = bool(options['from_course_mappings'])
        seed_legacy = bool(options['seed_legacy'])
        dry_run = bool(options['dry_run'])
        output_dir = Path(options['output_dir'])

        if export_only:
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / 'vocational_career_reasoning_mappings.json'
            zip_path = output_dir / 'vocational_career_reasoning_export.zip'
            json_path.write_bytes(export_json_bytes())
            zip_path.write_bytes(export_csv_zip_bytes())
            self.stdout.write(self.style.SUCCESS(f'Wrote {json_path}'))
            self.stdout.write(self.style.SUCCESS(f'Wrote {zip_path}'))

        if not from_courses and not seed_legacy:
            if not export_only:
                self.stdout.write('Nothing to do. Use --export-only, --from-course-mappings, and/or --seed-legacy.')
            return

        by_exact, by_normalized = _vocational_careers_by_name()
        created = skipped = unmatched = 0
        seen_pairs = set()

        def upsert(career, area, priority, source_label):
            nonlocal created, skipped, unmatched
            if not career:
                unmatched += 1
                self.stdout.write(self.style.WARNING(f'No career for {area} / {source_label!r}'))
                return
            key = (career.pk, area)
            if key in seen_pairs:
                return
            seen_pairs.add(key)
            existing = VocationalCareerReasoningMapping.objects.complete().filter(
                career_id=career.pk,
                reasoning_area=area,
            ).first()
            if existing:
                changed = False
                if existing.object_status != choices.ObjectStatus.ACTIVE:
                    existing.object_status = choices.ObjectStatus.ACTIVE
                    changed = True
                if existing.priority != priority:
                    existing.priority = priority
                    changed = True
                if changed:
                    existing.save()
                    created += 1
                    self.stdout.write(f'Reactivated: {area} → {career.name}')
                else:
                    skipped += 1
                return
            VocationalCareerReasoningMapping.objects.create(
                career=career,
                reasoning_area=area,
                priority=priority,
                object_status=choices.ObjectStatus.ACTIVE,
            )
            created += 1
            self.stdout.write(f'Created: {area} → {career.name} (pk={career.pk})')

        def seed():
            nonlocal created, skipped, unmatched
            if from_courses:
                course_mappings = (
                    VocationalCourseReasoningMapping.objects.filter(
                        object_status=choices.ObjectStatus.ACTIVE,
                        vocational_course__object_status=choices.ObjectStatus.ACTIVE,
                    )
                    .select_related('vocational_course')
                    .order_by('reasoning_area', 'priority', 'vocational_course__name')
                )
                for mapping in course_mappings:
                    course_name = mapping.vocational_course.name
                    career = _resolve_career_for_course(course_name, by_exact, by_normalized)
                    upsert(career, mapping.reasoning_area, mapping.priority, course_name)

            if seed_legacy:
                for area, names in LEGACY_BELOW_AREA_TO_CAREER_NAMES.items():
                    for priority, name in enumerate(names, start=1):
                        career = _resolve_career_by_keyword(name, by_exact, by_normalized)
                        upsert(career, area, priority, name)

        if dry_run:
            with transaction.atomic():
                seed()
                transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('Dry run — no changes saved.'))
        else:
            with transaction.atomic():
                seed()

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed complete: {created} created/reactivated, {skipped} already existed, '
                f'{unmatched} unmatched.'
            )
        )
