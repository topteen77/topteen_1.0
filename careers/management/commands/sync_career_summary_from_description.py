"""
Django management command to set Career.summary from the start of Career.description.

For each career with a description, extracts the intro/summary (content before the first
<h2> heading, or first few paragraphs if no heading) and updates the summary field.
"""

from django.core.management.base import BaseCommand
from careers.models import Career
from careers.utils import extract_summary_from_description


class Command(BaseCommand):
    help = 'Set career summary from the start of career description (content before first H2)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--career-id',
            type=int,
            help='Process only this career ID',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Max number of careers to process',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only print what would be updated, do not save',
        )

    def handle(self, *args, **options):
        career_id = options.get('career_id')
        limit = options.get('limit')
        dry_run = options.get('dry_run')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be saved'))

        qs = Career.objects.all().order_by('id')
        if career_id:
            qs = qs.filter(id=career_id)
            if not qs.exists():
                self.stdout.write(self.style.ERROR(f'Career id={career_id} not found'))
                return
        if limit:
            qs = qs[:limit]

        total = qs.count()
        updated = 0
        skipped = 0

        for career in qs:
            if not career.description or not career.description.strip():
                skipped += 1
                continue
            summary = extract_summary_from_description(career.description)
            if not summary.strip():
                skipped += 1
                continue
            if career.summary != summary:
                if not dry_run:
                    career.summary = summary
                    career.save(update_fields=['summary'])
                updated += 1
                self.stdout.write(
                    f"  [{career.id}] {career.name[:50]}... summary len={len(summary)}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {updated} updated, {skipped} skipped (no description or empty summary)"
            )
        )
        if dry_run and updated:
            self.stdout.write(self.style.WARNING('Run without --dry-run to apply changes'))
