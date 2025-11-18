#!/usr/bin/env python3
"""
Management command to fix Unicode characters in existing career records.
This converts problematic Unicode characters to HTML entities.
"""

from django.core.management.base import BaseCommand
from careers.models import Career
import html


class Command(BaseCommand):
    help = 'Fix Unicode characters in career records by converting them to HTML entities'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        def to_numeric_entities_preserve_html(text):
            """Unescape existing HTML, then convert non-ASCII to numeric entities, preserving tags."""
            if not text:
                return text
            unescaped = html.unescape(text)
            return unescaped.encode('ascii', 'xmlcharrefreplace').decode('ascii')

        careers = Career.objects.all()
        fixed_count = 0
        
        self.stdout.write(f'Processing {careers.count()} careers...')
        
        for career in careers:
            changed = False
            
            # Check each field for Unicode characters
            fields_to_check = ['name', 'summary', 'description', 'role_description', 'eligibility', 'pros_cons']
            
            for field_name in fields_to_check:
                field_value = getattr(career, field_name)
                if field_value:
                    converted_value = to_numeric_entities_preserve_html(field_value)
                    # Handle field length constraints
                    if field_name == 'summary' and len(converted_value) > 250:
                        converted_value = converted_value[:247] + '...'
                    elif field_name == 'name' and len(converted_value) > 500:
                        converted_value = converted_value[:497] + '...'

                    if converted_value != field_value:
                        if dry_run:
                            self.stdout.write(
                                f'Would fix {field_name} in career "{career.name}" (ID: {career.id})'
                            )
                        else:
                            setattr(career, field_name, converted_value)
                            changed = True
            
            if changed and not dry_run:
                try:
                    career.save()
                    fixed_count += 1
                    self.stdout.write(f'Fixed career: {career.name} (ID: {career.id})')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error fixing career {career.name} (ID: {career.id}): {str(e)}')
                    )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fixed {fixed_count} careers')
            )
