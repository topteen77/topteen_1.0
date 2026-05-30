"""
Convert remaining <p><strong> section headings to <h2> in VocationalCourse.content_html.

Same rules as fix_vocational_bold_lines_to_h2 (skips subsection labels ending with :, etc.).
Use --dry-run first; --course-id for one course.
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.career_description_html import (
    convert_bold_candidates_to_h2,
    find_bold_heading_candidates,
    format_bold_candidates_preview,
)
from core.accordion_utils import content_json_from_html
from core.management.commands._vocational_course_filters import (
    add_vocational_course_arguments,
    vocational_course_queryset,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Convert <p><strong> headings to <h2> in vocational course content_html "
        "(skips labels like Core Subjects:). Use --dry-run first."
    )

    def add_arguments(self, parser):
        add_vocational_course_arguments(parser)
        parser.add_argument(
            "--only-changes",
            action="store_true",
            help="Only list courses that would get at least one H2 conversion.",
        )
        parser.add_argument(
            "--refresh-json",
            action="store_true",
            help="Regenerate content_json after saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        only_changes = options["only_changes"]
        refresh_json = options["refresh_json"]
        qs = vocational_course_queryset(options)

        if not qs.exists():
            self.stderr.write(self.style.ERROR("No vocational courses matched."))
            return

        total_scanned = 0
        total_reviewed = 0
        total_updated = 0
        total_skipped_empty = 0

        for course in qs:
            total_scanned += 1
            html = course.content_html or ""
            if not str(html).strip():
                total_skipped_empty += 1
                continue

            candidates = find_bold_heading_candidates(html)
            convertible = [c for c in candidates if c.convertible]

            if not candidates:
                if only_changes:
                    continue
                self.stdout.write("")
                self.stdout.write(
                    self.style.MIGRATE_HEADING(f"Course [{course.id}] {course.name}")
                )
                self.stdout.write("    No <p><strong>…</strong></p> heading lines found.")
                continue

            new_html, changes = convert_bold_candidates_to_h2(html)
            h2_before = html.count("<h2")
            h2_after = new_html.count("<h2")
            p_strong_before = html.count("<p><strong>")
            p_strong_after = new_html.count("<p><strong>")

            would_save = len(changes) > 0
            html_reformat_only = (
                not would_save and new_html != html
            )

            if only_changes and not would_save:
                continue

            total_reviewed += 1
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(f"Course [{course.id}] {course.name}")
            )
            self.stdout.write(
                format_bold_candidates_preview(candidates)
            )

            if would_save:
                self.stdout.write("")
                self.stdout.write(
                    f"    Summary: {len(changes)} line(s) → <h2>; "
                    f"H2 count {h2_before} → {h2_after}; "
                    f"<p><strong> {p_strong_before} → {p_strong_after}"
                )
                for i, ch in enumerate(changes, 1):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"    [{i}] {ch.before_display!r}  →  {ch.after_display}"
                        )
                    )
            elif html_reformat_only:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        "    No heading conversions (all bold lines skipped or already H2). "
                        "BeautifulSoup would only reformat whitespace — not saving."
                    )
                )
            else:
                self.stdout.write("")
                self.stdout.write(
                    "    No changes — content already matches conversion rules."
                )

            if not would_save:
                continue

            if dry_run:
                self.stdout.write(self.style.WARNING("  [DRY RUN] would save."))
                total_updated += 1
                continue

            with transaction.atomic():
                course.content_html = new_html
                update_fields = ["content_html"]
                if refresh_json:
                    course.content_json = content_json_from_html(
                        new_html, program_title=course.name
                    )
                    update_fields.append("content_json")
                course.save(update_fields=update_fields)
            total_updated += 1
            self.stdout.write(
                self.style.SUCCESS(f"  Saved ({len(changes)} H2 conversion(s)).")
            )

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned}; reviewed {total_reviewed}; "
            f"empty content skipped {total_skipped_empty}; "
            f"{'would update' if dry_run else 'updated'} {total_updated}."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB changes."))
