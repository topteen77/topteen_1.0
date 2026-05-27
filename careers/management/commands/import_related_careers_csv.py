"""Import related careers from CSV into Career.related_careers M2M."""

from pathlib import Path

from django.core.management.base import BaseCommand

from careers.related_careers_import import import_related_careers_from_csv


class Command(BaseCommand):
    help = (
        'Import related careers from CSV (max 3 per career). '
        'Required columns: id, related_career_ids. Example: 1315,"1354,1336,1876"'
    )

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate only; do not write to the database',
        )
        parser.add_argument(
            '--clear-empty',
            action='store_true',
            help='Clear related careers when related_career_ids is empty',
        )

    def handle(self, *args, **options):
        path = Path(options['csv_file'])
        if not path.is_file():
            self.stderr.write(self.style.ERROR(f'File not found: {path}'))
            return

        with open(path, newline='', encoding='utf-8-sig') as f:
            result = import_related_careers_from_csv(
                f,
                dry_run=options['dry_run'],
                clear_existing=options['clear_empty'],
            )

        self.stdout.write(result.summary())
        for err in result.errors[:50]:
            self.stdout.write(self.style.WARNING(err))
        if len(result.errors) > 50:
            self.stdout.write(f'… and {len(result.errors) - 50} more errors')

        if options['dry_run']:
            self.stdout.write(self.style.NOTICE('Dry run — no changes saved.'))
