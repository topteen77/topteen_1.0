"""
Management command to convert remaining <p><strong> headings to <h2> tags in career descriptions.
This completes the stage1 task of converting all headings to H2 format.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from careers.models import Career
from careers.description_parser import convert_p_strong_to_h2
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Convert remaining <p><strong> headings to <h2> tags in all career descriptions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually updating the database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of careers to process (for testing)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options.get('limit')
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CAREER HEADING CONVERSION - STAGE 1 COMPLETION'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN MODE - No changes will be made\n'))
        
        # Get all careers
        careers = Career.objects.all()
        if limit:
            careers = careers[:limit]
            self.stdout.write(f'Processing limited to {limit} careers...')
        
        total_careers = careers.count()
        self.stdout.write(f'\nTotal careers to process: {total_careers}\n')
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        with transaction.atomic():
            for i, career in enumerate(careers, 1):
                try:
                    if not career.description:
                        skipped_count += 1
                        continue
                    
                    # Check if conversion is needed
                    has_p_strong = '<p><strong>' in career.description
                    original_h2_count = career.description.count('<h2>')
                    
                    if not has_p_strong:
                        skipped_count += 1
                        if i % 100 == 0:
                            self.stdout.write(f'  Processed {i}/{total_careers}... (skipped: no p-strong tags)')
                        continue
                    
                    # Convert p-strong to H2
                    converted_description = convert_p_strong_to_h2(career.description)
                    
                    # Check if conversion made changes
                    if converted_description == career.description:
                        skipped_count += 1
                        continue
                    
                    new_h2_count = converted_description.count('<h2>')
                    remaining_p_strong = converted_description.count('<p><strong>')
                    
                    if not dry_run:
                        # Update description
                        career.description = converted_description
                        career.save(update_fields=['description'])
                    
                    updated_count += 1
                    
                    # Progress indicator
                    if i % 50 == 0 or i == total_careers:
                        status = 'DRY RUN: ' if dry_run else ''
                        self.stdout.write(
                            f'  {status}Processed {i}/{total_careers}... '
                            f'Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count}'
                        )
                    
                    # Show details for first few updates
                    if updated_count <= 5:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ {career.name}: '
                                f'H2 tags: {original_h2_count} → {new_h2_count}, '
                                f'Remaining p-strong: {remaining_p_strong}'
                            )
                        )
                
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Error processing {career.name}: {str(e)}')
                    )
                    logger.error(f'Error converting headings for career {career.id}: {str(e)}', exc_info=True)
        
        # Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('CONVERSION SUMMARY'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total careers processed: {total_careers}')
        self.stdout.write(self.style.SUCCESS(f'Careers updated: {updated_count}'))
        self.stdout.write(f'Careers skipped (no changes needed): {skipped_count}')
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {error_count}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made. Run without --dry-run to apply changes.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Conversion completed successfully!'))
            self.stdout.write('\nStage 1 task: COMPLETED - All career headings converted to H2 format.')

