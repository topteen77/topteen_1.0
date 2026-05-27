"""
Wrap the last meaningful paragraph of Career.description in a conclusion block
(div.career-description-conclusion) for gradient-box rendering on career detail pages.

The career detail view also extracts the last paragraph at render time, so wrapping is
optional for display. Use this command to persist the structure in the admin editor.

Use --dry-run first, then --career-id / --slug for one career, then run without filters for all.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.career_description_html import (
    split_trailing_conclusion_from_description,
    wrap_last_paragraph_as_conclusion,
)
from careers.models import Career


class Command(BaseCommand):
    help = (
        "Wrap the last paragraph of career descriptions as a conclusion block. "
        "Use --dry-run first, then --slug or --career-id for one career."
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
            help="Process a single career by slug (for testing).",
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
            help="Print conclusion text preview for each change.",
        )
        parser.add_argument(
            "--list-only",
            action="store_true",
            help="Only list careers that would get a conclusion wrap (no HTML changes).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        list_only = options["list_only"]
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
        total_skipped = 0

        for career in qs:
            total_scanned += 1
            if not career.description or not str(career.description).strip():
                total_skipped += 1
                continue

            body, conclusion = split_trailing_conclusion_from_description(career.description)
            new_html, changes = wrap_last_paragraph_as_conclusion(career.description)

            if new_html == career.description:
                if list_only and conclusion and "career-description-conclusion" not in career.description:
                    self.stdout.write(
                        f"  [{career.id}] {career.name} — has trailing conclusion (view-only), not wrapped"
                    )
                total_skipped += 1
                continue

            total_updated += 1
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Career [{career.id}] {career.name} (slug={career.slug})"
                )
            )
            if dry_run or list_only:
                self.stdout.write(self.style.WARNING("  [DRY RUN] would update description:"))
            for line in changes:
                self.stdout.write(f"    {line}")
            if verbose and conclusion:
                preview = conclusion[:200].replace("\n", " ")
                self.stdout.write(f"    conclusion preview: {preview}…")

            if dry_run or list_only:
                continue

            with transaction.atomic():
                career.description = new_html
                career.save(update_fields=["description"])
            self.stdout.write(self.style.SUCCESS("  Saved."))

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned} career(s); "
            f"{'would update' if dry_run else 'updated'} {total_updated} career(s); "
            f"skipped {total_skipped}."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — no DB changes."))
