"""
Django management command to extract degrees from career HTML files.

This command:
1. Reads HTML files from career_html_output folder
2. Extracts "Study Route & Eligibility Criteria" section
3. Parses degree information from Route sections
4. Creates/updates Degree objects
5. Links degrees to Career via ManyToManyField
6. Uses mediator JSON for corrections/overrides
7. Generates error report for verification
"""

import os
import json
import re
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from bs4 import BeautifulSoup
from careers.models import Career, CareerTags
from courses.models import Degree
from core import choices


class Command(BaseCommand):
    help = 'Extract degrees from career HTML files and link them to careers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-dir',
            type=str,
            default='career_html_output',
            help='Directory containing the .txt files (default: career_html_output)'
        )
        parser.add_argument(
            '--mediator-file',
            type=str,
            default='careers/management/commands/degree_extraction_mediator.json',
            help='Path to mediator JSON file for corrections (see doc-md/README_DEGREE_EXTRACTION.md)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making database changes (preview mode)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of files to process (for testing)'
        )
        parser.add_argument(
            '--report-file',
            type=str,
            default='degree_extraction_report.json',
            help='Output file for extraction report'
        )

    def handle(self, *args, **options):
        input_dir = options['input_dir']
        mediator_file = options['mediator_file']
        dry_run = options['dry_run']
        limit = options.get('limit', None)
        report_file = options['report_file']
        
        if not os.path.exists(input_dir):
            raise CommandError(f'Input directory does not exist: {input_dir}')
        
        # Load mediator JSON
        self.mediator_data = self.load_mediator(mediator_file)
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting degree extraction from: {input_dir}')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No database changes will be made')
            )
        
        # Initialize report
        self.report = {
            'total_files': 0,
            'processed': 0,
            'careers_found': 0,
            'careers_not_found': [],
            'degrees_created': 0,
            'degrees_linked': 0,
            'errors': [],
            'warnings': [],
            'career_details': {}
        }
        
        # Process all .txt files
        self.process_txt_files(input_dir, dry_run, limit)
        
        # Save report
        self.save_report(report_file)
        
        # Print summary
        self.print_summary(dry_run)

    def load_mediator(self, mediator_file):
        """Load mediator JSON file for corrections/overrides."""
        if not os.path.exists(mediator_file):
            self.stdout.write(
                self.style.WARNING(f'Mediator file not found: {mediator_file}. Creating default...')
            )
            return self.get_default_mediator()
        
        try:
            with open(mediator_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading mediator file: {e}. Using default.')
            )
            return self.get_default_mediator()

    def get_default_mediator(self):
        """Return default mediator structure."""
        return {
            "version": "1.0",
            "career_overrides": {},
            "degree_mappings": {},
            "ignore_careers": [],
            "parsing_rules": {
                "skip_patterns": ["Entrance Exam", "Eligibility Criteria", "Admission Process"],
                "degree_patterns": {
                    "bachelor": ["Bachelor", "B.", "B.Sc", "B.A", "B.Com", "B.E", "B.Tech"],
                    "master": ["Master", "M.", "M.Sc", "M.A", "M.Com", "M.E", "M.Tech"],
                    "phd": ["Ph.D", "PhD", "Doctorate", "Doctor of"]
                }
            }
        }

    def process_txt_files(self, input_dir, dry_run, limit=None):
        """Process all .txt files in the input directory."""
        input_path = Path(input_dir)
        txt_files = list(input_path.rglob("*.txt"))
        
        if limit:
            txt_files = txt_files[:limit]
        
        self.report['total_files'] = len(txt_files)
        self.stdout.write(f'Found {len(txt_files)} .txt files to process')
        
        for txt_file in txt_files:
            try:
                result = self.process_single_file(txt_file, dry_run)
                self.report['processed'] += 1
                
                if result.get('career_found'):
                    self.report['careers_found'] += 1
                else:
                    self.report['careers_not_found'].append({
                        'file': str(txt_file),
                        'career_name': result.get('career_name', 'Unknown')
                    })
                
                if result.get('degrees_created'):
                    self.report['degrees_created'] += result['degrees_created']
                if result.get('degrees_linked'):
                    self.report['degrees_linked'] += result['degrees_linked']
                
                if result.get('errors'):
                    self.report['errors'].extend(result['errors'])
                if result.get('warnings'):
                    self.report['warnings'].extend(result['warnings'])
                
                # Store career details
                if result.get('career_slug'):
                    self.report['career_details'][result['career_slug']] = {
                        'career_name': result.get('career_name'),
                        'degrees_extracted': result.get('degrees_extracted', []),
                        'degrees_linked_count': result.get('degrees_linked', 0),
                        'has_eligibility': result.get('has_eligibility', False)
                    }
                
            except Exception as e:
                error_msg = f"{txt_file}: {str(e)}"
                self.report['errors'].append(error_msg)
                self.stdout.write(
                    self.style.ERROR(f'Error processing {txt_file}: {str(e)}')
                )

    def process_single_file(self, txt_file, dry_run):
        """Process a single .txt file and extract degrees."""
        result = {
            'career_found': False,
            'career_name': None,
            'career_slug': None,
            'degrees_created': 0,
            'degrees_linked': 0,
            'degrees_extracted': [],
            'has_eligibility': False,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Read HTML content from file
            with open(txt_file, 'r', encoding='utf-8') as f:
                html_content = f.read().strip()
            
            if not html_content:
                result['errors'].append(f'{txt_file}: Empty file')
                return result
            
            # Extract career name from title tag or filename
            career_name = self.extract_career_name_from_content(html_content, txt_file.stem)
            result['career_name'] = career_name
            
            # Find career in database
            career = Career.objects.filter(name__iexact=career_name).first()
            
            if not career:
                # Try to find by slug
                career_slug = slugify(career_name)
                career = Career.objects.filter(slug=career_slug).first()
            
            if not career:
                result['warnings'].append(f'{txt_file}: Career not found in database: {career_name}')
                return result
            
            result['career_found'] = True
            result['career_slug'] = career.slug
            
            # Check if career should be ignored
            if career.slug in self.mediator_data.get('ignore_careers', []):
                result['warnings'].append(f'{txt_file}: Career ignored via mediator: {career_name}')
                return result
            
            # Check for override in mediator
            if career.slug in self.mediator_data.get('career_overrides', {}):
                override = self.mediator_data['career_overrides'][career.slug]
                self.stdout.write(f'  → Using override for: {career_name}')
                degrees_data = override.get('degrees', [])
            else:
                # Extract eligibility section
                eligibility_html = self.extract_eligibility_section(html_content)
                result['has_eligibility'] = bool(eligibility_html)
                
                if not eligibility_html:
                    result['warnings'].append(f'{txt_file}: No eligibility section found for: {career_name}')
                    return result
                
                # Extract degrees from eligibility
                degrees_data = self.extract_degrees_from_eligibility(eligibility_html, career_name)
            
            if not degrees_data:
                result['warnings'].append(f'{txt_file}: No degrees extracted for: {career_name}')
                return result
            
            result['degrees_extracted'] = degrees_data
            
            # Create/update degrees and link to career
            if not dry_run:
                with transaction.atomic():
                    degrees_created, degrees_linked = self.create_and_link_degrees(
                        career, degrees_data
                    )
                    result['degrees_created'] = degrees_created
                    result['degrees_linked'] = degrees_linked
            else:
                result['degrees_created'] = len(degrees_data)
                result['degrees_linked'] = len(degrees_data)
            
            self.stdout.write(
                f'✓ {career_name}: {result["degrees_linked"]} degrees linked'
            )
            
        except Exception as e:
            result['errors'].append(f'{txt_file}: {str(e)}')
        
        return result

    def extract_career_name_from_content(self, html_content, filename):
        """Extract career name from title tag or use filename as fallback."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                career_name = title_tag.get_text().strip()
                if career_name:
                    return career_name
            return filename
        except Exception as e:
            return filename

    def extract_eligibility_section(self, html_content):
        """Extract 'Study Route & Eligibility Criteria' section from HTML."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find "Study Route & Eligibility Criteria" heading
            heading = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
                text = (tag.get_text() or '').strip().lower()
                if 'study route' in text and 'eligibility' in text:
                    heading = tag
                    break
            
            if not heading:
                return None
            
            # Collect all content until next major heading
            eligibility_sections = []
            current = heading
            
            # Include the heading itself
            eligibility_sections.append(str(heading))
            
            # Collect following siblings until next major heading
            while current:
                current = current.find_next_sibling()
                if not current:
                    break
                if current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    # Check if it's a new major section
                    text = (current.get_text() or '').strip().lower()
                    if any(keyword in text for keyword in ['pros', 'cons', 'skills', 'employment', 'recruiter']):
                        break
                eligibility_sections.append(str(current))
            
            return ''.join(eligibility_sections)
            
        except Exception as e:
            return None

    def extract_degrees_from_eligibility(self, eligibility_html, career_name):
        """Extract degrees from Study Route section."""
        soup = BeautifulSoup(eligibility_html, 'html.parser')
        degrees = []
        
        # Find all Route sections
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
            text = (tag.get_text() or '').strip().lower()
            if 'route' in text and any(char.isdigit() for char in text):
                # This is a Route section
                ul = tag.find_next_sibling(['ul', 'ol'])
                if not ul:
                    # Try finding ul in next siblings
                    current = tag
                    for _ in range(5):  # Look ahead max 5 siblings
                        current = current.find_next_sibling()
                        if not current:
                            break
                        if current.name in ['ul', 'ol']:
                            ul = current
                            break
                
                if ul:
                    for li in ul.find_all('li', recursive=False):
                        degree_text = li.get_text(strip=True)
                        if degree_text:
                            degree_info = self.parse_degree_text(degree_text)
                            if degree_info:
                                degrees.append(degree_info)
        
        # Also check for degrees in regular list items
        if not degrees:
            for li in soup.find_all('li'):
                text = li.get_text(strip=True)
                # Check if it looks like a degree
                if any(pattern in text for pattern in ['Bachelor', 'Master', 'Ph.D', 'Doctor', 'B.', 'M.']):
                    degree_info = self.parse_degree_text(text)
                    if degree_info:
                        degrees.append(degree_info)
        
        # Remove duplicates
        seen = set()
        unique_degrees = []
        for deg in degrees:
            key = (deg.get('name', '').lower(), deg.get('abbreviation', '').lower())
            if key not in seen and key[0]:  # Only add if name exists
                seen.add(key)
                unique_degrees.append(deg)
        
        return unique_degrees

    def parse_degree_text(self, text):
        """Parse degree text to extract name, abbreviation, and duration."""
        if not text or len(text) < 5:
            return None
        
        # Check mediator degree mappings first
        for abbrev, mapping in self.mediator_data.get('degree_mappings', {}).items():
            if abbrev in text:
                return {
                    'name': mapping.get('standard_name', text),
                    'abbreviation': mapping.get('abbreviation', abbrev),
                    'duration': mapping.get('duration', ''),
                    'stream_category': mapping.get('stream_category', '')
                }
        
        # Extract abbreviation in parentheses (e.g., "(B.V.Sc. & A.H.)")
        abbrev_match = re.search(r'\(([A-Z][\w\.\s&]+)\)', text)
        abbreviation = abbrev_match.group(1) if abbrev_match else ''
        
        # Extract duration in parentheses (e.g., "(5-5.5 years)")
        duration_match = re.search(r'\((\d+[\.\-\d]*\s*(?:years?|months?|yrs?))\)', text)
        duration = duration_match.group(1) if duration_match else ''
        
        # Remove abbreviations and durations from text to get degree name
        degree_name = text
        if abbrev_match:
            degree_name = degree_name.replace(abbrev_match.group(0), '').strip()
        if duration_match:
            degree_name = degree_name.replace(duration_match.group(0), '').strip()
        
        # Clean up degree name
        degree_name = re.sub(r'^\d+\.\s*', '', degree_name)  # Remove numbering
        degree_name = re.sub(r'^\d+\)\s*', '', degree_name)  # Remove numbering with )
        degree_name = degree_name.strip()
        
        # Skip if it's not actually a degree (check skip patterns)
        skip_patterns = self.mediator_data.get('parsing_rules', {}).get('skip_patterns', [])
        if any(pattern.lower() in text.lower() for pattern in skip_patterns):
            return None
        
        # Must contain degree indicators
        degree_indicators = ['Bachelor', 'Master', 'Ph.D', 'PhD', 'Doctor', 'B.', 'M.', 'Diploma', 'Certificate']
        if not any(indicator in text for indicator in degree_indicators):
            return None
        
        if not degree_name or len(degree_name) < 5:
            return None
        
        return {
            'name': degree_name,
            'abbreviation': abbreviation,
            'duration': duration,
            'stream_category': ''  # Will be determined later or from mediator
        }

    def create_and_link_degrees(self, career, degrees_data):
        """Create or update Degree objects and link them to career."""
        degrees_created = 0
        degrees_linked = 0
        
        for deg_data in degrees_data:
            degree_name = deg_data.get('name', '').strip()
            if not degree_name:
                continue
            
            # Create or get degree
            # Note: Currently Degree model only has 'name' field
            # Additional fields (abbreviation, description, duration) will be added via migration
            degree, created = Degree.objects.get_or_create(
                name=degree_name
            )
            
            if created:
                degrees_created += 1
            
            # TODO: Update degree with additional info once fields are added via migration
            # if deg_data.get('abbreviation') and hasattr(degree, 'abbreviation'):
            #     degree.abbreviation = deg_data['abbreviation']
            #     degree.save(update_fields=['abbreviation', 'modified'])
            
            # Link to career if not already linked
            if degree not in career.degrees.all():
                career.degrees.add(degree)
                degrees_linked += 1
        
        return degrees_created, degrees_linked

    def save_report(self, report_file):
        """Save extraction report to JSON file."""
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, indent=2, ensure_ascii=False)
            self.stdout.write(
                self.style.SUCCESS(f'\nReport saved to: {report_file}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error saving report: {e}')
            )

    def print_summary(self, dry_run):
        """Print processing summary."""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('DEGREE EXTRACTION SUMMARY'))
        self.stdout.write('='*80)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made to database'))
        
        self.stdout.write(f'Total files found: {self.report["total_files"]}')
        self.stdout.write(f'Files processed: {self.report["processed"]}')
        self.stdout.write(f'Careers found: {self.report["careers_found"]}')
        self.stdout.write(f'Careers not found: {len(self.report["careers_not_found"])}')
        self.stdout.write(f'Degrees created: {self.report["degrees_created"]}')
        self.stdout.write(f'Degrees linked: {self.report["degrees_linked"]}')
        self.stdout.write(f'Errors: {len(self.report["errors"])}')
        self.stdout.write(f'Warnings: {len(self.report["warnings"])}')
        
        if self.report['careers_not_found']:
            self.stdout.write('\n' + self.style.WARNING('CAREERS NOT FOUND:'))
            for item in self.report['careers_not_found'][:10]:  # Show first 10
                self.stdout.write(f'  - {item["career_name"]} (from {item["file"]})')
        
        if self.report['errors']:
            self.stdout.write('\n' + self.style.ERROR('ERRORS:'))
            for error in self.report['errors'][:10]:  # Show first 10
                self.stdout.write(f'  - {error}')
        
        if self.report['warnings']:
            self.stdout.write('\n' + self.style.WARNING('WARNINGS (first 10):'))
            for warning in self.report['warnings'][:10]:
                self.stdout.write(f'  - {warning}')
        
        self.stdout.write('\n' + self.style.SUCCESS('Extraction completed!'))
        self.stdout.write(self.style.SUCCESS(f'Check {self.report.get("report_file", "degree_extraction_report.json")} for detailed report.'))

