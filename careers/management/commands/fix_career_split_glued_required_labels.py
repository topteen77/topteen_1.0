"""
Split glued entrance-test region labels in Career.description.

  existing:
  Entrance Tests RequiredIndia:
  Into:
  <h2>Entrance Tests Required</h2>
  <p><strong>India:</strong></p>

Also fixes "Entrance Tests RequiredInternational:" the same way.

Use --dry-run first, then --slug or --career-id for one career.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.career_description_html import (
    format_career_html_changes,
    split_glued_required_region_labels,
)
from careers.models import Career


class Command(BaseCommand):
    help = (
        "Split glued lines like 'Entrance Tests RequiredIndia:' into H2 + bold India:/International:. "
        "Shows existing / Into for each change. Use --dry-run first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show before/after only; do not write to the database.",
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

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
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
        total_splits = 0

        for career in qs:
            total_scanned += 1
            if not career.description or not str(career.description).strip():
                continue

            new_html, changes = split_glued_required_region_labels(career.description)
            if new_html == career.description or not changes:
                continue

            total_updated += 1
            total_splits += len(changes)

            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Career [{career.id}] {career.name} (slug={career.slug})"
                )
            )
            if dry_run:
                self.stdout.write(self.style.WARNING("  [DRY RUN] would apply:"))
            else:
                self.stdout.write(self.style.SUCCESS("  Applied:"))

            self.stdout.write(format_career_html_changes(changes))

            if dry_run:
                continue

            with transaction.atomic():
                career.description = new_html
                career.save(update_fields=["description"])
            self.stdout.write(self.style.SUCCESS("  Saved."))

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned} career(s); "
            f"{'would update' if dry_run else 'updated'} {total_updated} career(s); "
            f"{total_splits} split(s)."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — no DB changes."))
