"""
Import Entrance Test Prep HTML (.txt) from converted folder into DB.
Folder structure: Level (After 10 / After 12 / After Graduation) / Category / exam.txt
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import OperationalError

from core import choices
from core.models import (
    EntranceTestPrepCategory,
    EntranceTestPrepExam,
    EntranceTestPrepExamSection,
)


def _normalize_html(s: str) -> str:
    if not s:
        return s
    while "&amp;amp;" in s:
        s = s.replace("&amp;amp;", "&amp;")
    return s


def _remove_empty_paragraphs(html: str) -> str:
    """Remove <p>&nbsp;</p> and variations (empty paragraphs)."""
    if not html:
        return html
    # <p> optional whitespace &nbsp; optional whitespace </p> (case-insensitive)
    return re.sub(r"<p>\s*&nbsp;\s*</p>", "", html, flags=re.IGNORECASE)


def _extract_body_inner_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if not body:
        return _remove_empty_paragraphs(_normalize_html(html.strip()))
    inner = "".join(str(x) for x in body.contents)
    return _remove_empty_paragraphs(_normalize_html(inner.strip()))


class Command(BaseCommand):
    help = (
        "Import entrance test prep from converted HTML (.txt) folder. "
        "Expects structure: Level/Category/exam.txt (e.g. After 10/Engineering/JEE Main.txt). "
        "Re-runs are safe: existing records are matched by (level, category, exam name) and updated; "
        "only missing records are inserted (no duplicates). "
        "Single record: pass two args (folder and file name), e.g. 'After 12/Engineering' 'JEE Main.txt'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "record_folder",
            nargs="?",
            default=None,
            metavar="FOLDER",
            help="Single-record mode (1): folder under source, e.g. 'After 12/Engineering'. Use with RECORD_FILE.",
        )
        parser.add_argument(
            "record_file",
            nargs="?",
            default=None,
            metavar="FILE",
            help="Single-record mode (2): .txt file name, e.g. 'JEE Main.txt'. Use with RECORD_FOLDER.",
        )
        parser.add_argument(
            "--source",
            default="entrance_test_prep_html",
            help="Path to converted HTML root (relative to project root or absolute). Default used when importing one record.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Hard-delete existing categories and exams before importing.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be created/updated; do not write to DB.",
        )
        parser.add_argument(
            "--file",
            dest="single_file",
            metavar="PATH",
            default=None,
            help=(
                "Process a single record: full path to one .txt relative to --source, "
                "e.g. 'After 10/Engineering/JEE Main.txt'. Optional when using FOLDER and FILE args."
            ),
        )

    def handle(self, *args, **options):
        from django.conf import settings
        base = Path(getattr(settings, "BASE_DIR", __file__))
        if not base.is_dir():
            base = Path(__file__).resolve().parent.parent.parent.parent
        source_dir = Path(options["source"]).resolve()
        if not source_dir.is_absolute():
            source_dir = base / source_dir
        replace = options["replace"]
        dry_run = options["dry_run"]
        single_file = options.get("single_file")
        record_folder = options.get("record_folder")
        record_file = options.get("record_file")
        if record_folder is not None and record_file is not None:
            fn = record_file.strip().lstrip("/")
            if fn and not fn.lower().endswith(".txt"):
                fn = f"{fn}.txt"
            single_file = f"{record_folder.strip().rstrip('/')}/{fn}"

        if not source_dir.exists():
            self.stderr.write(self.style.ERROR(f"Source directory not found: {source_dir}"))
            return

        if single_file:
            path = Path(single_file)
            if not path.is_absolute():
                path = (source_dir / path).resolve()
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Single file not found: {path}"))
                return
            if path.suffix.lower() != ".txt":
                self.stderr.write(self.style.ERROR(f"Single file must be a .txt file: {path}"))
                return
            try:
                path.relative_to(source_dir)
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Single file must be under source: {path}"))
                return
            if path.name.startswith("~$"):
                self.stderr.write(self.style.ERROR(f"Single file looks like a lock file: {path.name}"))
                return
            txt_files = [path]
            if replace:
                self.stdout.write(self.style.WARNING("--replace is ignored when using --file (single record)."))
                replace = False
        else:
            txt_files = sorted(
                p for p in source_dir.rglob("*.txt")
                if not p.name.startswith("~$")
            )

        if not txt_files:
            self.stdout.write(self.style.WARNING("No .txt files found to import."))
            return

        if dry_run:
            if single_file:
                txt_path = txt_files[0]
                rel = txt_path.relative_to(source_dir)
                parts = list(rel.parts[:-1])
                if len(parts) < 2:
                    self.stdout.write(self.style.WARNING(f"[DRY RUN] Single file has insufficient path (need Level/Category/file.txt): {rel}"))
                    return
                level_name, category_name = parts[0], parts[1]
                exam_name = txt_path.stem.strip()
                try:
                    parent_cat = EntranceTestPrepCategory._base_manager.filter(
                        parent__isnull=True, name__iexact=level_name
                    ).first()
                    category = None
                    if parent_cat:
                        category = EntranceTestPrepCategory._base_manager.filter(
                            parent=parent_cat, name__iexact=category_name
                        ).first()
                    existing_exam = None
                    if category:
                        existing_exam = (
                            EntranceTestPrepExam._base_manager.filter(
                                category=category, name__iexact=exam_name
                            )
                            .defer("content_json")
                            .first()
                        )
                    action = "update" if existing_exam else "create"
                except Exception:
                    action = "create or update"
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Single record: Level={level_name!r}, Category={category_name!r}, "
                        f"Exam={exam_name!r} -> {action}. No DB changes."
                    )
                )
            else:
                levels = set()
                categories = set()
                exams_count = 0
                for txt_path in txt_files:
                    rel = txt_path.relative_to(source_dir)
                    parts = list(rel.parts[:-1])
                    if len(parts) >= 2:
                        levels.add(parts[0])
                        categories.add((parts[0], parts[1]))
                        exams_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Would process {exams_count} exams, "
                        f"{len(levels)} levels, {len(categories)} categories. No DB changes."
                    )
                )
            return

        with transaction.atomic():
            if replace:
                EntranceTestPrepExamSection._base_manager.all().delete()
                EntranceTestPrepExam._base_manager.all().delete()
                EntranceTestPrepCategory._base_manager.all().delete()

            cat_cache: dict[tuple[int | None, str], EntranceTestPrepCategory] = {}
            created_categories = 0
            created_exams = 0
            updated_exams = 0

            def get_cat(
                name: str,
                parent: EntranceTestPrepCategory | None,
                priority: int,
            ) -> EntranceTestPrepCategory:
                nonlocal created_categories
                key = (parent.id if parent else None, name.strip().lower())
                if key in cat_cache:
                    return cat_cache[key]
                existing = EntranceTestPrepCategory._base_manager.filter(
                    name__iexact=name, parent=parent
                ).first()
                if existing:
                    existing.priority = priority
                    existing.object_status = choices.ObjectStatus.ACTIVE
                    existing.save()
                    cat_cache[key] = existing
                    return existing
                new_cat = EntranceTestPrepCategory.objects.create(
                    name=name.strip(),
                    parent=parent,
                    priority=priority,
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                created_categories += 1
                cat_cache[key] = new_cat
                return new_cat

            level_folders = set()
            category_folders = set()

            for txt_path in txt_files:
                rel = txt_path.relative_to(source_dir)
                parts = list(rel.parts[:-1])
                if len(parts) >= 1:
                    level_folders.add(parts[0])
                if len(parts) >= 2:
                    category_folders.add((parts[0], parts[1]))
                if len(parts) < 2:
                    continue
                parent = None
                for i, part in enumerate(parts, start=1):
                    parent = get_cat(part, parent, i)
                if parent is None:
                    continue

                exam_name = txt_path.stem.strip()
                raw = txt_path.read_text(encoding="utf-8", errors="ignore")
                content_html = _extract_body_inner_html(raw)
                if not content_html:
                    continue

                # No duplicate: lookup by (category, name) case-insensitive. If exists → update; else → insert.
                # Defer content_json so this works when DB has no content_json column yet (e.g. production pre-migration).
                existing_exam = (
                    EntranceTestPrepExam._base_manager.filter(
                        category=parent, name__iexact=exam_name
                    )
                    .defer("content_json")
                    .first()
                )
                if existing_exam:
                    existing_exam.name = exam_name
                    existing_exam.content_html = content_html
                    existing_exam.object_status = choices.ObjectStatus.ACTIVE
                    existing_exam.save(update_fields=["name", "content_html", "object_status"])
                    updated_exams += 1
                else:
                    try:
                        EntranceTestPrepExam.objects.create(
                            category=parent,
                            name=exam_name,
                            content_html=content_html,
                            priority=1,
                            object_status=choices.ObjectStatus.ACTIVE,
                        )
                        created_exams += 1
                    except OperationalError as e:
                        if e.args[0] == 1054 and "content_json" in str(e.args):
                            raise OperationalError(
                                e.args[0],
                                "Cannot create new exams: database table is missing column "
                                "'content_json'. Run: python manage.py migrate core",
                            ) from e
                        raise

            # Completion report
            num_levels = len(level_folders)
            num_cat_folders = len(category_folders)
            num_files = len(txt_files)
            total_categories = len(cat_cache)
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("--- IMPORT COMPLETE ---"))
            self.stdout.write("  Source: %s" % source_dir)
            self.stdout.write("  Level folders: %s" % num_levels)
            self.stdout.write("  Category folders: %s" % num_cat_folders)
            self.stdout.write("  Files (.txt) processed: %s" % num_files)
            self.stdout.write("  Categories: %s created (total: %s)" % (created_categories, total_categories))
            self.stdout.write("  Entrance exams: %s created, %s updated" % (created_exams, updated_exams))
            self.stdout.write(self.style.SUCCESS("------------------------"))
