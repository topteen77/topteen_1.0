"""
List and convert bold-only lines in VocationalCourse.content_html to <h2> headings.

Same rules as fix_career_bold_lines_to_h2 (careers.career_description_html).

Use --dry-run first; --course-id for one course.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.career_description_html import (
    convert_bold_candidates_to_h2,
    find_bold_heading_candidates,
    format_bold_candidates_preview,
    split_glued_required_region_labels,
)
from core.accordion_utils import content_json_from_html
from core.management.commands._vocational_course_filters import (
    add_vocational_course_arguments,
    vocational_course_queryset,
)


class Command(BaseCommand):
    help = (
        "Convert bold-only paragraph lines in vocational content_html to H2. "
        "Use --dry-run first."
    )

    def add_arguments(self, parser):
        add_vocational_course_arguments(parser)
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print HTML snippets for each candidate line.",
        )
        parser.add_argument(
            "--only-indices",
            default=None,
            help="Comma-separated candidate indices (single --course-id only).",
        )
        parser.add_argument(
            "--convert-skipped",
            action="store_true",
            help="Also convert skipped lines (India:/International:).",
        )
        parser.add_argument(
            "--only-changes",
            action="store_true",
            help="Only list courses that would be saved.",
        )
        parser.add_argument(
            "--refresh-json",
            action="store_true",
            help="Regenerate content_json after saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        only_changes = options["only_changes"]
        refresh_json = options["refresh_json"]

        only_indices = None
        if options.get("only_indices"):
            try:
                only_indices = {
                    int(x.strip()) for x in options["only_indices"].split(",") if x.strip()
                }
            except ValueError:
                self.stderr.write(self.style.ERROR("--only-indices must be integers."))
                return

        qs = vocational_course_queryset(options)
        if not qs.exists():
            self.stderr.write(self.style.ERROR("No vocational courses matched."))
            return
        if only_indices is not None and qs.count() != 1:
            self.stderr.write(self.style.ERROR("--only-indices requires a single --course-id."))
            return

        total_scanned = 0
        total_updated = 0
        total_reviewed = 0

        for course in qs:
            total_scanned += 1
            html = course.content_html or ""
            if not str(html).strip():
                continue

            working_html, glue_changes = split_glued_required_region_labels(html)
            candidates = find_bold_heading_candidates(working_html)
            if not candidates and not glue_changes:
                continue

            convertible = [c for c in candidates if c.convertible]
            indices_to_apply = only_indices
            if indices_to_apply is None and not options["convert_skipped"]:
                indices_to_apply = {c.index for c in convertible}
            elif indices_to_apply is None:
                indices_to_apply = {c.index for c in candidates}

            would_save = bool(glue_changes or indices_to_apply)
            if only_changes and not would_save:
                continue

            total_reviewed += 1
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(f"Course [{course.id}] {course.name}")
            )
            self.stdout.write(
                format_bold_candidates_preview(candidates, glue_changes=glue_changes or None)
            )

            if not would_save:
                continue

            if indices_to_apply:
                new_html, changes = convert_bold_candidates_to_h2(
                    working_html, only_indices=indices_to_apply
                )
            else:
                new_html, changes = working_html, []

            if new_html == html and not glue_changes:
                continue

            if dry_run:
                self.stdout.write(self.style.WARNING("  [DRY RUN] would save."))
                total_updated += 1
                continue

            with transaction.atomic():
                course.content_html = new_html
                update_fields = ["content_html"]
                if refresh_json:
                    course.content_json = content_json_from_html(new_html, program_title=course.name)
                    update_fields.append("content_json")
                course.save(update_fields=update_fields)
            total_updated += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Saved ({len(glue_changes)} glue split(s), {len(changes)} H2 conversion(s))."
                )
            )

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned}; reviewed {total_reviewed}; "
            f"{'would update' if dry_run else 'updated'} {total_updated}."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB changes."))
