#!/usr/bin/env python3
"""
Management command to convert <li> tags containing numbers or bullets to <p> tags.
If an <li> contains a number (1., 2., etc.) or bullet (•, ·, etc.), convert it to <p> 
and remove the list structure, keeping the number/bullet in the content.
"""

import re
from django.core.management.base import BaseCommand
from careers.models import Career


class Command(BaseCommand):
    help = 'Convert <li> tags with numbers/bullets to <p> tags in career descriptions'

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
        
        def convert_li_to_p(text):
            """Convert <li> tags with numbers/bullets to <p> tags."""
            if not text:
                return text
            
            def process_li_tag(match):
                li_tag = match.group(0)
                li_content = match.group(2)  # Content inside <li>...</li>
                
                # Check if content has numbers (1., 2., 3., etc.) or bullets (•, ·, ▪, etc.)
                has_number = bool(re.search(r'\d+\.\s', li_content))
                has_bullet = bool(re.search(r'[•·▪▫‣⁃\-\*\+]\s', li_content))
                
                if has_number or has_bullet:
                    # Convert <li> to <p>, keeping the content (with number/bullet)
                    # Extract any attributes from <li> tag
                    li_attrs_match = match.group(1)  # Attributes from <li([^>]*)>
                    li_attrs = li_attrs_match if li_attrs_match else ''
                    
                    # Convert to <p> tag
                    return f'<p{li_attrs}>{li_content}</p>'
                else:
                    # No number/bullet, keep as <li>
                    return li_tag
            
            # Process all <li> tags
            text = re.sub(
                r'<li([^>]*)>(.*?)</li>',
                process_li_tag,
                text,
                flags=re.IGNORECASE | re.DOTALL
            )
            
            # Remove empty <ul> and <ol> tags (after converting their <li> to <p>)
            # Pattern: <ul>...</ul> or <ol>...</ol> that now only contains <p> tags
            def remove_empty_lists(match):
                list_tag = match.group(0)
                list_content = match.group(2)  # Content inside list tags
                
                # If the list only contains <p> tags (no <li>), remove the list wrapper
                if '<li' not in list_content.lower():
                    # Return just the content (the <p> tags)
                    return list_content
                return list_tag
            
            # Remove <ul> tags that now only contain <p> tags
            text = re.sub(
                r'<ul([^>]*)>(.*?)</ul>',
                remove_empty_lists,
                text,
                flags=re.IGNORECASE | re.DOTALL
            )
            
            # Remove <ol> tags that now only contain <p> tags
            text = re.sub(
                r'<ol([^>]*)>(.*?)</ol>',
                remove_empty_lists,
                text,
                flags=re.IGNORECASE | re.DOTALL
            )
            
            # Clean up any double spaces
            text = re.sub(r'\s+', ' ', text)
            # Clean up spaces between tags
            text = re.sub(r'>\s+<', '><', text)
            
            return text
        
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
                # Try to get the field (might be a translation field)
                if field_name == 'description':
                    # Process both description and description_en
                    fields_to_process = ['description']
                    # Check if description_en exists (django-modeltranslation)
                    if hasattr(career, 'description_en'):
                        fields_to_process.append('description_en')
                else:
                    fields_to_process = [field_name]
            
            for field_name_actual in fields_to_process:
                field_value = getattr(career, field_name_actual, None)
                
                if not field_value:
                    continue
                
                # Check if field contains <li> tags with numbers or bullets
                has_li_with_numbers = bool(re.search(
                    r'<li[^>]*>.*?\d+\.\s',
                    field_value,
                    re.IGNORECASE | re.DOTALL
                ))
                has_li_with_bullets = bool(re.search(
                    r'<li[^>]*>.*?[•·▪▫‣⁃\-\*\+]\s',
                    field_value,
                    re.IGNORECASE | re.DOTALL
                ))
                
                if has_li_with_numbers or has_li_with_bullets:
                    fixed_value = convert_li_to_p(field_value)
                    
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
                            original_li_count = len(re.findall(r'<li[^>]*>', field_value, re.IGNORECASE))
                            fixed_li_count = len(re.findall(r'<li[^>]*>', fixed_value, re.IGNORECASE))
                            new_p_count = len(re.findall(r'<p[^>]*>.*?(?:\d+\.\s|[•·▪▫‣⁃\-\*\+]\s)', fixed_value, re.IGNORECASE | re.DOTALL))
                            
                            self.stdout.write(
                                f'  Found {original_li_count} <li> tags'
                            )
                            self.stdout.write(
                                f'  After fix: {fixed_li_count} <li> tags remaining, {new_p_count} <p> tags created'
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
                                        f'Converted <li> tags to <p> tags in {field_name_actual}'
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
