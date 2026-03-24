"""
Test and fix EntranceTestPrepExam category assignment.

Rules:
- Exams must be under a *leaf* category (category.parent is not None).
- Level categories have parent=None (e.g. After 10, After 12, After Graduation).
- If an exam's category is a level, it is wrong and can be fixed by moving to the first leaf child.

Optional: --source DIR to validate/fix using folder structure (Level/Category/exam.txt).
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from core import choices
from core.models import EntranceTestPrepCategory, EntranceTestPrepExam


class Command(BaseCommand):
    help = (
        "Test and fix exam categories: ensure each exam is under a leaf category (not a level). "
        "Optionally use --source to align with folder structure (Level/Category/exam.txt)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Apply fixes: move exams under a level to the first leaf child of that level.",
        )
        parser.add_argument(
            "--source",
            default=None,
            metavar="DIR",
            help=(
                "Path to converted HTML root (e.g. entrance_test_prep_html). "
                "If set, build expected (level, category) from .txt paths and fix exams that don't match."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be changed; do not write to DB.",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        source_dir = options.get("source")
        dry_run = options["dry_run"]

        if dry_run and fix:
            self.stdout.write(self.style.WARNING("[DRY RUN] No changes will be written."))

        # 1) Find exams under a level (wrong)
        levels = EntranceTestPrepCategory.objects.filter(
            parent__isnull=True,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        level_ids = set(levels.values_list("id", flat=True))

        exams_under_level = list(
            EntranceTestPrepExam._base_manager.filter(
                category_id__in=level_ids,
                object_status=choices.ObjectStatus.ACTIVE,
            ).select_related("category")
        )

        if exams_under_level:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(exams_under_level)} exam(s) under a LEVEL (should be under a leaf category):"
                )
            )
            for exam in exams_under_level:
                self.stdout.write(f"  - id={exam.id} name={exam.name!r} category={exam.category.name!r} (level)")
        else:
            self.stdout.write(self.style.SUCCESS("No exams found under a level (all under leaf categories)."))

        # 2) Build expected (level_name, category_name) -> category_id from source if provided
        source_map = {}
        if source_dir:
            from django.conf import settings
            base = getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent.parent)
            source_path = Path(source_dir) if Path(source_dir).is_absolute() else Path(base) / source_dir
            source_path = source_path.resolve()
            if source_path.exists():
                source_map = self._build_source_map(source_path)
                if source_map:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"Loaded {len(source_map)} (level, category, exam_name) paths from {source_path}."
                        )
                    )
                else:
                    self.stdout.write(self.style.WARNING(f"No .txt files found under {source_path}."))
            else:
                self.stdout.write(self.style.ERROR(f"Source directory not found: {source_path}"))

        # 3) Fix: exams under level -> first leaf child
        fixed_level = 0
        if fix and exams_under_level and not dry_run:
            with transaction.atomic():
                for exam in exams_under_level:
                    level = exam.category
                    first_leaf = (
                        EntranceTestPrepCategory.objects.filter(
                            parent=level,
                            object_status=choices.ObjectStatus.ACTIVE,
                        ).order_by("priority", "name").first()
                    )
                    if first_leaf:
                        exam.category = first_leaf
                        exam.save(update_fields=["category"])
                        fixed_level += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Fixed id={exam.id} {exam.name!r}: {level.name!r} -> {first_leaf.name!r}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"  Level {level.name!r} has no children; cannot fix exam id={exam.id} {exam.name!r}")
                        )
            if fixed_level:
                self.stdout.write(self.style.SUCCESS(f"Moved {fixed_level} exam(s) from level to first leaf."))

        if fix and dry_run and exams_under_level:
            first_leaf_per_level = {}
            for exam in exams_under_level:
                level = exam.category
                if level.id not in first_leaf_per_level:
                    first_leaf_per_level[level.id] = (
                        EntranceTestPrepCategory.objects.filter(
                            parent=level,
                            object_status=choices.ObjectStatus.ACTIVE,
                        ).order_by("priority", "name").first()
                    )
                first_leaf = first_leaf_per_level[level.id]
                if first_leaf:
                    self.stdout.write(
                        f"  [DRY RUN] Would fix id={exam.id} {exam.name!r}: {level.name!r} -> {first_leaf.name!r}"
                    )
                else:
                    self.stdout.write(f"  [DRY RUN] Would skip id={exam.id} (no leaf under {level.name!r})")

        # 4) Optional: fix using source map (exam name -> expected category)
        if source_map and fix and not dry_run:
            with transaction.atomic():
                fixed_source = self._fix_from_source(source_map)
            if fixed_source:
                self.stdout.write(self.style.SUCCESS(f"Adjusted {fixed_source} exam(s) to match source folder."))
        elif source_map and fix and dry_run:
            self._report_source_fixes(source_map)

    def _build_source_map(self, source_path: Path) -> dict:
        """Build (level_name, category_name, exam_name) -> (level_name, category_name) from .txt paths."""
        out = {}
        for txt_path in source_path.rglob("*.txt"):
            if txt_path.name.startswith("~"):
                continue
            try:
                rel = txt_path.relative_to(source_path)
                parts = list(rel.parts[:-1])
                if len(parts) < 2:
                    continue
                level_name, category_name = parts[0], parts[1]
                exam_name = txt_path.stem.strip()
                key = (level_name.lower(), category_name.lower(), exam_name.lower())
                out[key] = (level_name, category_name)
            except ValueError:
                continue
        return out

    def _get_leaf_category(self, level_name: str, category_name: str):
        """Resolve level name + category name to leaf category (same logic as import)."""
        level = EntranceTestPrepCategory.objects.filter(
            parent__isnull=True,
            name__iexact=level_name,
            object_status=choices.ObjectStatus.ACTIVE,
        ).first()
        if not level:
            return None
        leaf = EntranceTestPrepCategory.objects.filter(
            parent=level,
            name__iexact=category_name,
            object_status=choices.ObjectStatus.ACTIVE,
        ).first()
        return leaf

    def _fix_from_source(self, source_map: dict) -> int:
        """For each exam, if source has exactly one (level, category) for that name, fix if different."""
        fixed = 0
        # Group by exam name (lower) -> list of (level_name, category_name)
        from collections import defaultdict
        name_to_paths = defaultdict(list)
        for (_, _, exam_name), (ln, cn) in source_map.items():
            name_to_paths[exam_name].append((ln, cn))

        exams = EntranceTestPrepExam.objects.filter(
            object_status=choices.ObjectStatus.ACTIVE,
        ).select_related("category", "category__parent")
        for exam in exams:
            key_name = exam.name.lower() if exam.name else ""
            paths = name_to_paths.get(key_name, [])
            # Dedupe by (level, category)
            unique_paths = list(dict.fromkeys(paths))
            if len(unique_paths) != 1:
                continue
            level_name, category_name = unique_paths[0]
            expected_leaf = self._get_leaf_category(level_name, category_name)
            if not expected_leaf or expected_leaf.id == exam.category_id:
                continue
            exam.category = expected_leaf
            exam.save(update_fields=["category"])
            fixed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  id={exam.id} {exam.name!r}: "
                    f"{exam.category.name!r} -> {expected_leaf.name!r} (from source {level_name}/{category_name})"
                )
            )
        return fixed

    def _report_source_fixes(self, source_map: dict) -> None:
        """Dry-run: report what would be fixed from source."""
        from collections import defaultdict
        name_to_paths = defaultdict(list)
        for (_, _, exam_name), (ln, cn) in source_map.items():
            name_to_paths[exam_name].append((ln, cn))

        exams = EntranceTestPrepExam.objects.filter(
            object_status=choices.ObjectStatus.ACTIVE,
        ).select_related("category", "category__parent")
        for exam in exams:
            key_name = exam.name.lower() if exam.name else ""
            paths = name_to_paths.get(key_name, [])
            unique_paths = list(dict.fromkeys(paths))
            if len(unique_paths) != 1:
                continue
            level_name, category_name = unique_paths[0]
            expected_leaf = self._get_leaf_category(level_name, category_name)
            if not expected_leaf or expected_leaf.id == exam.category_id:
                continue
            level_cur = exam.category.parent
            cur_level_name = level_cur.name if level_cur else "(level)"
            self.stdout.write(
                f"  [DRY RUN] Would fix id={exam.id} {exam.name!r}: "
                f"{cur_level_name}/{exam.category.name!r} -> {level_name}/{expected_leaf.name!r}"
            )
