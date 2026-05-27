"""
Remove completely blank lines from Career.description HTML:

- empty <p> (whitespace / &nbsp; / <br> only)
- empty headings <h1>–<h6> (e.g. <h2>&nbsp;</h2> — often show as blank accordion rows)
- empty spacer <div> (no text, or only <br> children)

Does not remove tags that contain tables, lists, images, or real text.

Use --dry-run first, then --slug or --career-id for one career.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.career_description_html import audit_blank_lines, remove_completely_blank_lines
from careers.models import Career


class Command(BaseCommand):
    help = (
        "Remove empty paragraph/blank-line tags from career descriptions. "
        "Use --dry-run first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes only; do not write to the database.",
        )
        parser.add_argument(
            "--slug",
            default=None,
            help="Process a single career by slug.",
        )
        parser.add_argument(
            "--career-id",
            type=int,
            default=None,
            help="Process a single career by primary key.",
        )
        parser.add_argument(
            "--name",
            default=None,
            help="Process career(s) whose name contains this string (case-insensitive).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of careers to process (after filters).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print every removed tag and a breakdown (empty <p> vs empty headings).",
        )
        parser.add_argument(
            "--audit-only",
            action="store_true",
            help="Print blank-tag counts per career; do not change HTML (implies --dry-run).",
        )

    def handle(self, *args, **options):
        audit_only = options["audit_only"]
        dry_run = options["dry_run"] or audit_only
        verbose = options["verbose"] or audit_only
        slug = options.get("slug")
        career_id = options.get("career_id")
        name = options.get("name")
        limit = options.get("limit")

        qs = Career.objects.all().order_by("id")
        if career_id:
            qs = qs.filter(pk=career_id)
        elif slug:
            qs = qs.filter(slug=slug)
        elif name:
            qs = qs.filter(name__icontains=name)

        if limit:
            qs = qs[:limit]

        if not qs.exists():
            self.stderr.write(self.style.ERROR("No careers matched the filter."))
            return

        total_scanned = 0
        total_updated = 0
        total_removed = 0

        for career in qs:
            total_scanned += 1
            if not career.description or not str(career.description).strip():
                continue

            audit = audit_blank_lines(career.description)
            new_html, changes = remove_completely_blank_lines(career.description)
            if new_html == career.description or not changes:
                if audit_only and audit["total_removable"]:
                    self.stdout.write("")
                    self.stdout.write(
                        self.style.MIGRATE_HEADING(
                            f"Career [{career.id}] {career.name} (slug={career.slug})"
                        )
                    )
                    self._print_audit(audit)
                continue

            total_updated += 1
            total_removed += len(changes)

            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Career [{career.id}] {career.name} (slug={career.slug})"
                )
            )
            if verbose:
                self._print_audit(audit)
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"  [DRY RUN] would remove {len(changes)} blank line(s):")
                )
            else:
                self.stdout.write(f"  Removed {len(changes)} blank line(s):")

            for line in changes:
                if verbose or dry_run:
                    self.stdout.write(f"    {line}")

            if dry_run or audit_only:
                continue

            with transaction.atomic():
                career.description = new_html
                career.save(update_fields=["description"])
            self.stdout.write(self.style.SUCCESS("  Saved."))

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned} career(s); "
            f"{'would update' if dry_run else 'updated'} {total_updated} career(s); "
            f"{total_removed} blank tag(s) removed."
        )
        if audit_only:
            self.stdout.write(self.style.NOTICE("Audit only — no DB changes."))
        elif dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — no DB changes."))

    def _print_audit(self, audit: dict) -> None:
        self.stdout.write(
            f"  Breakdown: {audit['empty_p']} empty <p>, "
            f"{audit['empty_heading']} empty heading(s) (h1–h6), "
            f"{audit['empty_div']} empty <div> "
            f"→ {audit['total_removable']} removable tag(s) total"
        )
