"""
List and convert bold-only lines in Career.description to <h2> headings.

A bold line is a <p> whose visible text is entirely one <strong> or <b> element.
Skips India:/International: sub-labels, including "International (for …):" (see careers.career_description_html).
Also splits glued lines like "Entrance Tests RequiredIndia:" into H2 + bold "India:" before converting.

Use --dry-run to preview groups per career; omit it to apply conversions.
Use --only-indices with a single --career-id to convert specific lines only.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from careers.career_description_html import (
    convert_bold_candidates_to_h2,
    find_bold_heading_candidates,
    format_bold_candidates_preview,
    format_career_html_changes,
    split_glued_required_region_labels,
)
from careers.models import Career


class Command(BaseCommand):
    help = (
        "Convert bold-only paragraph lines in career descriptions to H2. "
        "Lists candidates per career; use --dry-run first, then --career-id for one career."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List bold-line groups only; do not write to the database.",
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
            help="Print HTML snippets for each candidate line.",
        )
        parser.add_argument(
            "--only-indices",
            default=None,
            help=(
                "Comma-separated candidate indices to convert (per career), e.g. 0,2,5. "
                "Only applies when exactly one career is matched or --career-id is set."
            ),
        )
        parser.add_argument(
            "--convert-skipped",
            action="store_true",
            help="Also convert skipped lines (India:/International:); not recommended.",
        )
        parser.add_argument(
            "--only-changes",
            action="store_true",
            help="Only list careers that would be saved (hide review-only careers with all lines skipped).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        slug = options.get("slug")
        career_id = options.get("career_id")
        name = options.get("name")
        limit = options.get("limit")
        only_indices_raw = options.get("only_indices")

        only_indices = None
        if only_indices_raw:
            try:
                only_indices = {
                    int(x.strip()) for x in only_indices_raw.split(",") if x.strip()
                }
            except ValueError:
                self.stderr.write(
                    self.style.ERROR("--only-indices must be comma-separated integers.")
                )
                return

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

        if only_indices is not None and qs.count() != 1:
            self.stderr.write(
                self.style.ERROR(
                    "--only-indices requires a single career (--career-id or --slug)."
                )
            )
            return

        total_scanned = 0
        total_updated = 0
        total_reviewed = 0
        total_candidates = 0
        total_convertible = 0
        only_changes = options["only_changes"]

        for career in qs:
            total_scanned += 1
            if not career.description or not str(career.description).strip():
                continue

            working_html = career.description
            working_html, glue_changes = split_glued_required_region_labels(working_html)

            candidates = find_bold_heading_candidates(working_html)
            if not candidates and not glue_changes:
                continue

            convertible = [c for c in candidates if c.convertible]
            total_candidates += len(candidates)
            total_convertible += len(convertible)

            indices_to_apply = only_indices
            if indices_to_apply is None and not options["convert_skipped"]:
                indices_to_apply = {c.index for c in convertible}
            elif indices_to_apply is None and options["convert_skipped"]:
                indices_to_apply = {c.index for c in candidates}

            would_save = bool(glue_changes or indices_to_apply)
            if only_changes and not would_save:
                continue

            total_reviewed += 1

            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Career [{career.id}] {career.name} (slug={career.slug})"
                )
            )

            if would_save:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Summary: {len(glue_changes)} glue split(s), "
                        f"{len(convertible)} bold line(s) → H2"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Summary: no database changes — {len(candidates)} bold line(s) "
                        f"reviewed, all skipped (see existing / Into below)"
                    )
                )

            self.stdout.write(format_bold_candidates_preview(
                candidates,
                glue_changes=glue_changes or None,
            ))

            if not indices_to_apply and not glue_changes:
                continue

            if indices_to_apply:
                new_html, changes = convert_bold_candidates_to_h2(
                    working_html,
                    only_indices=indices_to_apply,
                )
            else:
                new_html, changes = working_html, []

            if new_html == career.description and not glue_changes:
                continue

            if dry_run:
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("  [DRY RUN] would save to database."))
                total_updated += 1
                continue

            with transaction.atomic():
                career.description = new_html
                career.save(update_fields=["description"])
            total_updated += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Saved ({len(glue_changes)} glue split(s), {len(changes)} H2 conversion(s))."
                )
            )

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned} career(s); "
            f"printed {total_reviewed} career report(s); "
            f"found {total_candidates} bold line(s) ({total_convertible} would become H2); "
            f"{'would update' if dry_run else 'updated'} {total_updated} career(s) in database."
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete — no DB changes. Run without --dry-run to apply."
                )
            )
