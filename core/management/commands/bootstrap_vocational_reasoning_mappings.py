from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from core import choices
from core.models import VocationalCourse, VocationalCourseReasoningMapping
from core.vocational_reasoning_io import export_csv_zip_bytes, export_json_bytes

LEGACY_BELOW_AREA_TO_VOCATIONAL_NAMES = {
    'NUMERICAL': ['Actuarial Science', 'Data Analytics', 'Accounting'],
    'VERBAL': ['Journalism', 'Content Writing', 'Communication'],
    'LOGICAL': ['Computer Applications', 'IT', 'Software Development'],
    'MECHANICAL': ['Aerospace Engineering', 'Automobile Engineering', 'Mechanical Engineering'],
    'SPATIAL': ['Accessory Designing', 'Fashion Designing', 'Interior Design'],
    'LANGUAGE': ['Foreign Languages', 'Translation', 'Content Writing'],
    'CRITICAL': ['Law', 'Research Methodology', 'Critical Thinking'],
}


def _resolve_course(name):
    course = VocationalCourse.objects.filter(
        name__iexact=name,
        object_status=choices.ObjectStatus.ACTIVE,
    ).first()
    if course:
        return course
    return VocationalCourse.objects.filter(
        name__icontains=name,
        object_status=choices.ObjectStatus.ACTIVE,
    ).order_by('priority', 'name').first()


class Command(BaseCommand):
    help = (
        "Export vocational reasoning mappings (JSON/CSV) and optionally seed "
        "initial mappings from the legacy keyword map."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--export-only",
            action="store_true",
            help="Write export files to disk without changing mappings",
        )
        parser.add_argument(
            "--output-dir",
            default=".",
            help="Directory for --export-only files (default: current directory)",
        )
        parser.add_argument(
            "--seed-legacy",
            action="store_true",
            help="Create mappings from legacy area→keyword map (iexact then icontains match)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="With --seed-legacy, show matches without writing",
        )

    def handle(self, *args, **options):
        export_only = bool(options["export_only"])
        seed_legacy = bool(options["seed_legacy"])
        dry_run = bool(options["dry_run"])
        output_dir = Path(options["output_dir"])

        if export_only:
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / "vocational_reasoning_mappings.json"
            zip_path = output_dir / "vocational_reasoning_export.zip"
            json_path.write_bytes(export_json_bytes())
            zip_path.write_bytes(export_csv_zip_bytes())
            self.stdout.write(self.style.SUCCESS(f"Wrote {json_path}"))
            self.stdout.write(self.style.SUCCESS(f"Wrote {zip_path}"))

        if not seed_legacy:
            if not export_only:
                self.stdout.write("Nothing to do. Use --export-only and/or --seed-legacy.")
            return

        created = skipped = unmatched = 0
        seen_pairs = set()

        def seed():
            nonlocal created, skipped, unmatched
            for area, names in LEGACY_BELOW_AREA_TO_VOCATIONAL_NAMES.items():
                for priority, name in enumerate(names, start=1):
                    course = _resolve_course(name)
                    if not course:
                        unmatched += 1
                        self.stdout.write(self.style.WARNING(f"No course for {area} / {name!r}"))
                        continue
                    key = (course.pk, area)
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    existing = VocationalCourseReasoningMapping.objects.complete().filter(
                        vocational_course_id=course.pk,
                        reasoning_area=area,
                    ).first()
                    if existing:
                        if existing.object_status != choices.ObjectStatus.ACTIVE:
                            existing.object_status = choices.ObjectStatus.ACTIVE
                            existing.priority = priority
                            existing.save()
                            created += 1
                            self.stdout.write(f"Reactivated: {area} → {course.name}")
                        else:
                            skipped += 1
                        continue
                    VocationalCourseReasoningMapping.objects.create(
                        vocational_course=course,
                        reasoning_area=area,
                        priority=priority,
                        object_status=choices.ObjectStatus.ACTIVE,
                    )
                    created += 1
                    self.stdout.write(f"Created: {area} → {course.name} (pk={course.pk})")

        if dry_run:
            with transaction.atomic():
                seed()
                transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run — no changes saved."))
        else:
            with transaction.atomic():
                seed()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {created} created/reactivated, {skipped} already existed, "
                f"{unmatched} keywords unmatched."
            )
        )
