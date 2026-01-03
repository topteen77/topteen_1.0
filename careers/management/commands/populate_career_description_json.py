"""
Django management command to populate description_json field for existing careers.

This command:
1. Iterates through all Career objects
2. Generates JSON structure from description field
3. Stores the JSON in description_json field
4. Provides progress reporting and error handling
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from careers.models import Career
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate description_json field for existing careers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--career-id',
            type=int,
            help='Process only a specific career by ID'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of careers to process'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip careers that already have description_json populated'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making database changes (preview mode)'
        )

    def handle(self, *args, **options):
        career_id = options.get('career_id')
        limit = options.get('limit')
        skip_existing = options.get('skip_existing')
        dry_run = options.get('dry_run')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        # Get careers to process
        if career_id:
            careers = Career.objects.filter(id=career_id)
            if not careers.exists():
                raise CommandError(f'Career with ID {career_id} not found')
        else:
            careers = Career.objects.all()
            if skip_existing:
                careers = careers.filter(description_json__isnull=True)
        
        if limit:
            careers = careers[:limit]

        total = careers.count()
        self.stdout.write(f'Processing {total} career(s)...')

        success_count = 0
        error_count = 0
        skipped_count = 0

        for idx, career in enumerate(careers, 1):
            try:
                # Check if should skip
                if skip_existing and career.description_json:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'[{idx}/{total}] Skipping career {career.id} ({career.name}) - already has JSON')
                    )
                    continue

                self.stdout.write(f'[{idx}/{total}] Processing career {career.id}: {career.name}...')

                # Generate JSON
                json_data = career.generate_description_json()
                
                if json_data:
                    if not dry_run:
                        # Update the career
                        career.description_json = json_data
                        career.save(update_fields=['description_json'])
                    
                    sections_found = len(json_data.get('metadata', {}).get('sections_found', []))
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Generated JSON with {sections_found} sections'
                        )
                    )
                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠ No JSON generated (empty description?)')
                    )
                    error_count += 1

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error processing career {career.id}: {str(e)}')
                )
                logger.error(f'Error processing career {career.id}: {str(e)}', exc_info=True)

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(f'  Total processed: {total}')
        self.stdout.write(self.style.SUCCESS(f'  Success: {success_count}'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'  Skipped: {skipped_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))
        self.stdout.write('=' * 60)

        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a DRY RUN - No changes were saved'))

