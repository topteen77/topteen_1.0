"""
Verify entrance test prep: compare entrance_test_prep_folder_list.txt with DB.

Produces: Missing in DB, Missing in folder, Wrong category, Duplicates (folder and DB).
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import EntranceTestPrepCategory, EntranceTestPrepExam


def _norm(s: str) -> str:
    """Normalize for matching: strip, collapse spaces, lower."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip()).lower()


def _exam_name_from_filename(filename: str) -> str:
    """Remove .docx / .txt extension."""
    for ext in (".docx", ".txt"):
        if filename.lower().endswith(ext):
            return filename[: -len(ext)].strip()
    return filename.strip()


def parse_folder_list(path: Path) -> list[tuple[str, str, str]]:
    """Parse list file. Returns list of (level, category, exam_name) normalized."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.rstrip() for ln in text.splitlines()]
    result = []
    level, category = "", ""
    for ln in lines:
        if ln.startswith("Total:") or ln.startswith("Source:") or "Entrance test prep folder list" in ln:
            continue
        if not ln.strip():
            continue
        if ln.startswith("    - "):
            filename = ln[6:].strip()
            exam_name = _exam_name_from_filename(filename)
            if level and category and exam_name:
                result.append((_norm(level), _norm(category), _norm(exam_name)))
            continue
        if ln.startswith("  ") and not ln.startswith("    "):
            category = ln.strip()
            continue
        if ln.strip() and not ln.startswith(" "):
            level = ln.strip()
            category = ""
    return result


class Command(BaseCommand):
    help = "Compare entrance_test_prep_folder_list.txt with DB; report missing, wrong category, duplicates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-file",
            default="entrance_test_prep_folder_list.txt",
            help="Path to folder list file (default: project root).",
        )
        parser.add_argument(
            "--output",
            "-o",
            default=None,
            metavar="FILE",
            help="Write full report to this file.",
        )

    def handle(self, *args, **options):
        list_path = Path(options["list_file"]).resolve()
        if not list_path.is_absolute():
            base = getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent.parent)
            list_path = base / options["list_file"]
        if not list_path.exists():
            self.stderr.write(self.style.ERROR(f"List file not found: {list_path}"))
            return

        folder_tuples = parse_folder_list(list_path)
        folder_set = set(folder_tuples)
        folder_by_name = {}  # norm_exam_name -> [(level, category), ...]
        for lev, cat, name in folder_tuples:
            folder_by_name.setdefault(name, []).append((lev, cat))

        exams = EntranceTestPrepExam.objects.select_related("category", "category__parent").all()
        db_tuples = []
        db_by_id = {}
        for e in exams:
            lev = (e.category.parent.name if e.category and e.category.parent else "(level)")
            cat = (e.category.name if e.category else "")
            key = (_norm(lev), _norm(cat), _norm(e.name or ""))
            db_tuples.append(key)
            db_by_id[e.id] = (lev, cat, e.name or "", key)
        db_set = set(db_tuples)

        folder_names = {t[2] for t in folder_tuples}
        db_names = {t[2] for t in db_tuples}

        out_lines = []
        def w(s=""):
            out_lines.append(s)

        w("=" * 70)
        w("ENTRANCE TEST PREP: FOLDER LIST vs DB – VERIFICATION REPORT")
        w("=" * 70)
        w(f"List file: {list_path}")
        w(f"Folder entries: {len(folder_tuples)}  |  DB exams: {exams.count()}")
        w("")

        # Duplicates in folder (same exam name under different level/category)
        dup_folder = {name: locs for name, locs in folder_by_name.items() if len(locs) > 1}
        if dup_folder:
            w("--- DUPLICATES IN FOLDER LIST (same exam name in multiple Level/Category) ---")
            for name in sorted(dup_folder.keys()):
                locs = dup_folder[name]
                w(f"  {name}")
                for lev, cat in locs:
                    w(f"    -> {lev} » {cat}")
            w("")
        else:
            w("--- DUPLICATES IN FOLDER LIST: none ---")
            w("")

        # Duplicates in DB (same normalized name in multiple categories)
        db_by_name = {}
        for e in exams:
            n = _norm(e.name or "")
            if n not in db_by_name:
                db_by_name[n] = []
            lev = e.category.parent.name if e.category and e.category.parent else "(level)"
            cat = e.category.name if e.category else ""
            db_by_name[n].append((e.id, e.name, lev, cat))
        dup_db = {name: locs for name, locs in db_by_name.items() if len(locs) > 1}
        if dup_db:
            w("--- DUPLICATES IN DB (same exam name in multiple categories) ---")
            for name in sorted(dup_db.keys()):
                locs = dup_db[name]
                w(f"  {name}")
                for eid, ename, lev, cat in locs:
                    w(f"    -> id={eid} {lev} » {cat}")
            w("")
        else:
            w("--- DUPLICATES IN DB: none ---")
            w("")

        # Missing in DB (in folder but no matching DB row)
        missing_db = []
        for lev, cat, name in sorted(folder_set):
            if not name:
                continue
            if (lev, cat, name) not in db_set:
                missing_db.append((lev, cat, name))
        w("--- MISSING IN DB (in folder list but no exam with same Level/Category/Name) ---")
        if missing_db:
            w(f"  Total: {len(missing_db)}")
            for lev, cat, name in missing_db[:200]:
                w(f"  {lev} » {cat} | {name}")
            if len(missing_db) > 200:
                w(f"  ... and {len(missing_db) - 200} more.")
        else:
            w("  None")
        w("")

        # Missing in folder (in DB but no matching folder entry)
        missing_folder = []
        for lev, cat, name in sorted(db_set):
            if not name:
                continue
            if (lev, cat, name) not in folder_set:
                missing_folder.append((lev, cat, name))
        w("--- MISSING IN FOLDER (in DB but no matching entry in folder list) ---")
        if missing_folder:
            w(f"  Total: {len(missing_folder)}")
            for lev, cat, name in missing_folder[:200]:
                w(f"  {lev} » {cat} | {name}")
            if len(missing_folder) > 200:
                w(f"  ... and {len(missing_folder) - 200} more.")
        else:
            w("  None")
        w("")

        # Wrong category: same exam name in both, but DB (level, category) != folder (level, category)
        wrong_cat = []
        for e in exams:
            n = _norm(e.name or "")
            if not n or n not in folder_by_name:
                continue
            folder_locs = folder_by_name[n]
            lev_db = e.category.parent.name if e.category and e.category.parent else "(level)"
            cat_db = e.category.name if e.category else ""
            key_db = (_norm(lev_db), _norm(cat_db))
            folder_keys = [(_norm(lev_f), _norm(cat_f)) for lev_f, cat_f in folder_locs]
            if key_db in folder_keys:
                continue
            wrong_cat.append((e.id, e.name, lev_db, cat_db, folder_locs[0][0], folder_locs[0][1]))
        w("--- WRONG CATEGORY (same exam name: DB category differs from folder) ---")
        if wrong_cat:
            w(f"  Total: {len(wrong_cat)}")
            for eid, ename, lev_db, cat_db, lev_f, cat_f in wrong_cat[:200]:
                w(f"  id={eid} {ename!r}")
                w(f"    DB:  {lev_db} » {cat_db}")
                w(f"    Folder: {lev_f} » {cat_f}")
            if len(wrong_cat) > 200:
                w(f"  ... and {len(wrong_cat) - 200} more.")
        else:
            w("  None")
        w("")

        w("=" * 70)
        w("SUMMARY")
        w("=" * 70)
        w(f"  Duplicates in folder: {len(dup_folder)} exam names in multiple level/category")
        w(f"  Duplicates in DB:     {len(dup_db)} exam names in multiple categories")
        w(f"  Missing in DB:       {len(missing_db)}")
        w(f"  Missing in folder:   {len(missing_folder)}")
        w(f"  Wrong category:      {len(wrong_cat)}")
        w("")

        report = "\n".join(out_lines)
        if options.get("output"):
            out_path = Path(options["output"]).resolve()
            if not out_path.is_absolute():
                base = getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent.parent)
                out_path = base / options["output"]
            out_path.write_text(report, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Report written to {out_path}"))
        else:
            self.stdout.write(report)
