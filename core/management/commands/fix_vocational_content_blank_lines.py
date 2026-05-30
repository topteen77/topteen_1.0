"""
Remove completely blank lines from VocationalCourse.content_html:

- empty <p> (whitespace / &nbsp; / <br> only)
- empty headings <h1>–<h6>
- empty spacer <div>

Same logic as careers (careers.career_description_html).

Use --dry-run first, then --course-id for one course.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.career_description_html import audit_blank_lines, remove_completely_blank_lines
from core.accordion_utils import content_json_from_html
from core.management.commands._vocational_course_filters import (
    add_vocational_course_arguments,
    vocational_course_queryset,
)


class Command(BaseCommand):
    help = (
        "Remove empty paragraph/blank-line tags from vocational course content_html. "
        "Use --dry-run first."
    )

    def add_arguments(self, parser):
        add_vocational_course_arguments(parser)
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print every removed tag and a breakdown.",
        )
        parser.add_argument(
            "--audit-only",
            action="store_true",
            help="Print blank-tag counts per course; do not change HTML.",
        )
        parser.add_argument(
            "--refresh-json",
            action="store_true",
            help="Regenerate content_json from content_html after saving.",
        )

    def handle(self, *args, **options):
        audit_only = options["audit_only"]
        dry_run = options["dry_run"] or audit_only
        verbose = options["verbose"] or audit_only
        refresh_json = options["refresh_json"]

        qs = vocational_course_queryset(options)
        if not qs.exists():
            self.stderr.write(self.style.ERROR("No vocational courses matched the filter."))
            return

        total_scanned = 0
        total_updated = 0
        total_removed = 0

        for course in qs:
            total_scanned += 1
            html = course.content_html or ""
            if not str(html).strip():
                continue

            audit = audit_blank_lines(html)
            new_html, changes = remove_completely_blank_lines(html)
            if new_html == html or not changes:
                if audit_only and audit["total_removable"]:
                    self._print_course_header(course)
                    self._print_audit(audit)
                continue

            total_updated += 1
            total_removed += len(changes)
            self._print_course_header(course)
            if verbose:
                self._print_audit(audit)
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"  [DRY RUN] would remove {len(changes)} blank tag(s)")
                )
            else:
                self.stdout.write(f"  Removed {len(changes)} blank tag(s)")
            for line in changes:
                if verbose or dry_run:
                    self.stdout.write(f"    {line}")

            if dry_run or audit_only:
                continue

            with transaction.atomic():
                course.content_html = new_html
                update_fields = ["content_html"]
                if refresh_json:
                    course.content_json = content_json_from_html(new_html, program_title=course.name)
                    update_fields.append("content_json")
                course.save(update_fields=update_fields)
            self.stdout.write(self.style.SUCCESS("  Saved."))

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned} course(s); "
            f"{'would update' if dry_run else 'updated'} {total_updated}; "
            f"{total_removed} blank tag(s) removed."
        )
        if audit_only:
            self.stdout.write(self.style.NOTICE("Audit only — no DB changes."))
        elif dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — no DB changes."))

    def _print_course_header(self, course):
        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Course [{course.id}] {course.name}")
        )

    def _print_audit(self, audit: dict) -> None:
        self.stdout.write(
            f"  Breakdown: {audit['empty_p']} empty <p>, "
            f"{audit['empty_heading']} empty heading(s), "
            f"{audit['empty_div']} empty <div> "
            f"→ {audit['total_removable']} removable"
        )
