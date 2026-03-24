"""
List entrance test prep folder structure (Level / Category / exam files) for manual check.

Output is category/subcategory wise: Level -> Category -> list of exam file names.
Supports .docx and .txt. Run and redirect to a file for manual review.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "List folder structure: Level -> Category -> exam files (.docx or .txt) for manual check. "
        "Redirect output to a file, e.g. ... > career_list.txt"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="/home/itpc6/Public/share/content- Topteen/Entrance test prep 2026",
            metavar="DIR",
            help="Source directory (default: Entrance test prep 2026 folder).",
        )
        parser.add_argument(
            "--ext",
            default=".docx,.txt",
            help="Comma-separated extensions to include (default: .docx,.txt).",
        )
        parser.add_argument(
            "--output",
            "-o",
            default=None,
            metavar="FILE",
            help="Write list to this file (default: stdout).",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress startup/log output; only print the list and total.",
        )

    def handle(self, *args, **options):
        quiet = options.get("quiet", False)
        out_path = options.get("output")
        out_file = None
        if out_path:
            out_file = open(out_path, "w", encoding="utf-8")  # noqa: SIM115
            if not quiet:
                self.stdout.write(f"Writing to {out_path}")

        def write(line: str = "") -> None:
            if out_file:
                out_file.write(line + "\n")
            else:
                self.stdout.write(line)

        try:
            return self._run(options, write, quiet)
        finally:
            if out_file:
                out_file.close()

    def _run(self, options, write, quiet):
        source_dir = Path(options["source"]).resolve()
        if not source_dir.is_absolute():
            base = getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent.parent)
            source_dir = (Path(base) / options["source"]).resolve()

        exts = {e.strip().lower() for e in options["ext"].split(",") if e.strip()}
        if not exts:
            exts = {".docx", ".txt"}
        # ensure leading dot
        exts = {e if e.startswith(".") else f".{e}" for e in exts}

        if not source_dir.exists():
            self.stderr.write(self.style.ERROR(f"Source directory not found: {source_dir}"))
            return

        # Collect (level, category, filename) for each file
        by_level_cat = {}  # (level, category) -> [filename, ...]
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            if path.name.startswith("~"):
                continue
            try:
                rel = path.relative_to(source_dir)
                parts = rel.parts[:-1]
                name = path.name
                if len(parts) == 0:
                    level, category = "(root)", "(root)"
                elif len(parts) == 1:
                    level, category = parts[0], "(uncategorized)"
                else:
                    level, category = parts[0], parts[1]
                key = (level, category)
                by_level_cat.setdefault(key, []).append(name)
            except ValueError:
                continue

        # Sort: by level then category, and sort filenames
        write("Entrance test prep folder list (Level / Category / exam files) – for manual check")
        write("Source: " + str(source_dir))
        write("")
        for key in sorted(by_level_cat.keys(), key=lambda x: (x[0].lower(), x[1].lower())):
            level, category = key
            files = sorted(by_level_cat[key], key=str.lower)
            write("")
            write(f"{level}")
            write(f"  {category}")
            for f in files:
                write(f"    - {f}")
            write("")

        total = sum(len(v) for v in by_level_cat.values())
        write(f"Total: {len(by_level_cat)} level/category groups, {total} files.")
        if not quiet and options.get("output"):
            self.stdout.write(self.style.SUCCESS(f"Wrote list. Total: {len(by_level_cat)} groups, {total} files."))
