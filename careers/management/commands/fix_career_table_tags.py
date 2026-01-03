#!/usr/bin/env python3
"""
Management command to replace <th> tags with <td> tags in career descriptions.
This fixes table header tags that should be table data tags. 
and remove the list structure, keeping the number/bullet in the content.
"""

import re
from django.core.management.base import BaseCommand
from careers.models import Career


class Command(BaseCommand):
    help = 'Replace <th> tags with <td> tags in career descriptions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )
        parser.add_argument(
            '--single',
            type=int,
            help='Process only one career with the given ID',
        )
        parser.add_argument(
            '--field',
            type=str,
            default='description',
            help='Field to fix (default: description). Use "description_en" for English translation.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        single_id = options.get('single')
        field_name = options['field']
        
        def replace_th_tags(text):
            """Replace <th> and </th> tags with <td> and </td> tags."""
            if not text:
                return text
            
            # Replace opening <th> tags (with or without attributes)
            text = re.sub(r'<th(\s[^>]*)?>', r'<td\1>', text, flags=re.IGNORECASE)
            
            # Replace closing </th> tags
            text = re.sub(r'</th>', '</td>', text, flags=re.IGNORECASE)
            
            return text
        
        # Verify no content loss
        def verify_no_content_loss(original, fixed):
            """Verify that replacement didn't lose any content."""
            # Remove all tags and compare text content
            original_text = re.sub(r'<[^>]+>', '', original)
            fixed_text = re.sub(r'<[^>]+>', '', fixed)
            
            # Compare text content (normalize whitespace)
            original_text_normalized = ' '.join(original_text.split())
            fixed_text_normalized = ' '.join(fixed_text.split())
            
            # Check that all <th> tags were replaced
            remaining_th = len(re.findall(r'<th[^>]*>|</th>', fixed, re.IGNORECASE))
            
            return {
                'text_preserved': original_text_normalized == fixed_text_normalized,
                'text_length_original': len(original_text_normalized),
                'text_length_fixed': len(fixed_text_normalized),
                'remaining_th_tags': remaining_th,
                'all_th_replaced': remaining_th == 0
            }
        
        # Get careers to process
        if single_id:
            careers = Career.objects.filter(id=single_id)
            if not careers.exists():
                self.stdout.write(
                    self.style.ERROR(f'Career with ID {single_id} not found')
                )
                return
            self.stdout.write(f'Processing single career ID: {single_id}')
        else:
            careers = Career.objects.all()
            self.stdout.write(f'Processing {careers.count()} careers...')

        fixed_count = 0
        checked_count = 0

        for career in careers:
            checked_count += 1
            
            # Process both description and description_en fields
            fields_to_process = []
            
            # Check if field_name is a direct field or translation field
            if hasattr(career, field_name):
                fields_to_process.append(field_name)
            else:
                # Process the field
                fields_to_process = [field_name]
            
            for field_name_actual in fields_to_process:
                field_value = getattr(career, field_name_actual, None)
                
                if not field_value:
                    continue
                
                # Check if field contains <li> tags with numbers or bullets
                has_th_tags = bool(re.search(
                    r'<th[^>]*>|</th>',
                    field_value,
                    re.IGNORECASE | re.DOTALL
                ))
                if has_th_tags:
                    fixed_value = replace_th_tags(field_value)
                    verification = verify_no_content_loss(field_value, fixed_value)
                    
                    if fixed_value != field_value:
                        if dry_run:
                            # Show preview
                            self.stdout.write(
                                self.style.WARNING(
                                    f'\n{"="*80}'
                                )
                            )
                            self.stdout.write(
                                f'Career ID: {career.id} | Name: "{career.name}"'
                            )
                            self.stdout.write(f'Field: {field_name_actual}')
                            
                            # Count changes
                            th_open_count = len(re.findall(r'<th[^>]*>', field_value, re.IGNORECASE))
                            th_close_count = len(re.findall(r'</th>', field_value, re.IGNORECASE))
                            # Removed - not needed
                            # Removed - not needed
                            
                            self.stdout.write(
                                f'  Found {th_count} <th> tags'
                            )
                            self.stdout.write(
                                f'  Found {th_open_count} opening <th> tags and {th_close_count} closing </th> tags'
                            )
                            
                            # Show before/after example
                            self.stdout.write('\n  BEFORE (example):')
                            before_match = re.search(
                                r'(<li[^>]*>.*?(?:\d+\.\s|[•·▪▫‣⁃\-\*\+]\s)[^<]{0,100})',
                                field_value,
                                re.IGNORECASE | re.DOTALL
                            )
                            if before_match:
                                self.stdout.write(f'    {before_match.group(0)[:200]}')
                            
                            self.stdout.write('\n  AFTER (example):')
                            after_match = re.search(
                                r'(<p[^>]*>.*?(?:\d+\.\s|[•·▪▫‣⁃\-\*\+]\s)[^<]{0,100})',
                                fixed_value,
                                re.IGNORECASE | re.DOTALL
                            )
                            if after_match:
                                self.stdout.write(f'    {after_match.group(0)[:200]}')
                            
                            fixed_count += 1
                        else:
                            # Make the change
                            setattr(career, field_name_actual, fixed_value)
                            try:
                                career.save()
                                fixed_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f'✓ Fixed career "{career.name}" (ID: {career.id}) - '
                                        f'Replaced <th> tags with <td> tags in {field_name_actual}'
                                    )
                                )
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f'✗ Error fixing career "{career.name}" (ID: {career.id}): {str(e)}'
                                    )
                                )

        # Summary
        self.stdout.write('\n' + '='*80)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN - Checked {checked_count} careers, would fix {fixed_count} fields'
                )
            )
            if fixed_count > 0:
                self.stdout.write(
                    self.style.SUCCESS('\nTo apply these changes, run without --dry-run flag')
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully fixed {fixed_count} fields out of {checked_count} checked careers'
                )
            )
