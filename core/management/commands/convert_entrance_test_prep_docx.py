"""
Convert Entrance Test Prep 2026 .docx files to HTML (.txt) preserving folder structure.
Uses scripts.convert_docx_to_html for the actual conversion.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


def _remove_empty_paragraphs(html: str) -> str:
    """Remove <p> that contain only whitespace, &nbsp;, or &#160; (e.g. <p>&nbsp;</p>)."""
    if not html or not html.strip():
        return html
    # Match <p>...</p> with only optional whitespace and &nbsp;/&#160; inside
    pattern = re.compile(
        r"<p(?:\s[^>]*)?>\s*(?:&nbsp;|&#160;|\s)*\s*</p>",
        re.IGNORECASE,
    )
    return pattern.sub("", html)


# Default source: user's Entrance test prep 2026 folder
DEFAULT_SOURCE = "/home/itpc6/Public/share/content- Topteen/Entrance test prep 2026"
# Default output: under project root
DEFAULT_OUTPUT = "entrance_test_prep_html"


class Command(BaseCommand):
    help = (
        "Convert Entrance Test Prep 2026 .docx files to HTML (.txt). "
        "Preserves folder structure (After 10/..., After 12/..., After Graduation/...)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=DEFAULT_SOURCE,
            help=f"Source directory containing .docx files (default: {DEFAULT_SOURCE})",
        )
        parser.add_argument(
            "--output",
            default=DEFAULT_OUTPUT,
            help=f"Output directory for .txt HTML files (default: {DEFAULT_OUTPUT}). If relative, under project root.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list files that would be converted; do not write any output.",
        )

    def handle(self, *args, **options):
        source_dir = Path(options["source"]).resolve()
        output_dir = Path(options["output"]).resolve()
        if not output_dir.is_absolute():
            base = getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent.parent)
            output_dir = Path(base) / output_dir
        dry_run = options["dry_run"]

        if not source_dir.exists():
            self.stderr.write(self.style.ERROR(f"Source directory not found: {source_dir}"))
            return

        docx_files = sorted(
            f for f in source_dir.rglob("*.docx")
            if not f.name.startswith("~$")
        )
        total = len(docx_files)

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would convert {total} .docx files (no output written)."))
            for i, p in enumerate(docx_files[:20], 1):
                self.stdout.write(f"  {i}. {p.relative_to(source_dir)}")
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more.")
            return

        try:
            from scripts.convert_docx_to_html import convert_docx_to_html
        except ImportError:
            self.stderr.write(
                self.style.ERROR(
                    "Could not import scripts.convert_docx_to_html. "
                    "Ensure the script exists and project root is on PYTHONPATH."
                )
            )
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        success = 0
        errors = 0
        for docx_path in docx_files:
            try:
                html_content = convert_docx_to_html(docx_path)
                if not html_content:
                    errors += 1
                    self.stdout.write(self.style.WARNING(f"Skip (empty): {docx_path.relative_to(source_dir)}"))
                    continue
                html_content = _remove_empty_paragraphs(html_content)
                rel = docx_path.relative_to(source_dir)
                out_file = (output_dir / rel).with_suffix(".txt")
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(html_content, encoding="utf-8")
                success += 1
                self.stdout.write(f"OK: {rel}")
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"Failed {docx_path}: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Success: {success}, Errors: {errors}, Output: {output_dir}"
            )
        )
