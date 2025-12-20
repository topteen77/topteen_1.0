"""
Django management command to import extracurricular activities and sections from JSON files.
Supports single file or batch processing.
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max

from core import choices
from core.models import (
    ExtracurricularActivity,
    ExtracurricularActivityCategory,
    ExtracurricularActivitySection
)


# Category metadata mapping
CAT_META = {
    "Academic & Competitive Activities": ("academic", "bx bx-brain"),
    "Sports & Physical Activities": ("sports", "bx bx-football"),
    "Arts & Cultural Pursuits": ("arts", "bx bx-palette"),
    "Community Service, Leadership & Social Initiatives": ("leadership", "bx bx-group"),
    "Technology, Innovation & Entrepreneurship": ("technology", "bx bx-code-alt"),
    "Cultural & Language Clubs": ("arts", "bx bx-world"),
    "Other Enriching Activities": ("international", "bx bx-globe"),
    "International Extracurricular Activities": ("technology", "bx bx-bulb"),
}


class Command(BaseCommand):
    help = "Import extracurricular activities and sections from JSON files into DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            default="scripts/extracurricular_json_output",
            help="Absolute path to the JSON files directory or single JSON file",
        )
        parser.add_argument(
            "--file",
            type=str,
            help="Process a single JSON file (overrides --source)",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing sections for activities before importing",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source = options["source"]
        single_file = options.get("file")
        replace = options.get("replace", False)

        if single_file:
            # Single file mode
            json_path = Path(single_file)
            if not json_path.exists():
                raise CommandError(f"JSON file not found: {json_path}")

            if not json_path.suffix.lower() == '.json':
                raise CommandError(f"File must be a .json file: {json_path}")

            self.stdout.write(f"Processing single file: {json_path}")
            self.process_single_file(json_path, replace)
        else:
            # Directory mode (all files)
            source_dir = Path(source)
            if not source_dir.exists():
                raise CommandError(f"Source directory not found: {source_dir}")

            json_files = sorted(source_dir.rglob("*.json"))
            if not json_files:
                self.stdout.write(self.style.WARNING("No .json files found to import."))
                return

            self.stdout.write(f"Found {len(json_files)} JSON files to process")
            self.process_directory(json_files, replace)

    def process_single_file(self, json_path: Path, replace: bool):
        """Process a single JSON file."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            result = self.import_activity_data(data, replace)
            self.print_result(result, single_file=True)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in {json_path}: {e}")
        except Exception as e:
            raise CommandError(f"Error processing {json_path}: {e}")

    def process_directory(self, json_files: list, replace: bool):
        """Process all JSON files in directory."""
        stats = {
            'total': len(json_files),
            'processed': 0,
            'created_activities': 0,
            'updated_activities': 0,
            'created_sections': 0,
            'updated_sections': 0,
            'errors': 0,
            'error_details': []
        }

        for json_path in json_files:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                result = self.import_activity_data(data, replace)
                
                stats['processed'] += 1
                stats['created_activities'] += result['created_activity']
                stats['updated_activities'] += result['updated_activity']
                stats['created_sections'] += result['created_sections']
                stats['updated_sections'] += result['updated_sections']

            except json.JSONDecodeError as e:
                stats['errors'] += 1
                stats['error_details'].append(f"{json_path}: Invalid JSON - {e}")
            except Exception as e:
                stats['errors'] += 1
                stats['error_details'].append(f"{json_path}: {e}")

        self.print_summary(stats)

    def import_activity_data(self, data: dict, replace: bool) -> dict:
        """
        Import activity and sections from JSON data.
        Returns statistics dictionary.
        """
        activity_name = data.get('activity_name', '').strip()
        category_name = data.get('category_name', '').strip()
        sections_data = data.get('sections', [])

        if not activity_name:
            raise ValueError("Missing 'activity_name' in JSON data")
        if not category_name:
            raise ValueError("Missing 'category_name' in JSON data")

        # Get or create category
        css_class, icon_class = CAT_META.get(category_name, ("", "bx bx-star"))
        
        category = ExtracurricularActivityCategory.objects.filter(
            name__iexact=category_name
        ).first()
        
        if not category:
            # Find max priority for new category
            max_priority = ExtracurricularActivityCategory.objects.aggregate(
                max_priority=Max('priority')
            )['max_priority'] or 0
            
            category = ExtracurricularActivityCategory.objects.create(
                name=category_name,
                css_class=css_class,
                icon_class=icon_class,
                priority=max_priority + 1,
                object_status=choices.ObjectStatus.ACTIVE,
            )
        else:
            # Update category metadata
            category.css_class = css_class
            category.icon_class = icon_class
            category.object_status = choices.ObjectStatus.ACTIVE
            category.save()

        # Get or create activity
        activity = ExtracurricularActivity.objects.filter(
            category=category,
            name__iexact=activity_name
        ).first()

        created_activity = 0
        updated_activity = 0

        if not activity:
            # Find max priority for new activity in this category
            max_priority = ExtracurricularActivity.objects.filter(
                category=category
            ).aggregate(max_priority=Max('priority'))['max_priority'] or 0

            activity = ExtracurricularActivity.objects.create(
                category=category,
                name=activity_name,
                priority=max_priority + 1,
                object_status=choices.ObjectStatus.ACTIVE,
            )
            created_activity = 1
        else:
            activity.name = activity_name
            activity.object_status = choices.ObjectStatus.ACTIVE
            activity.save()
            updated_activity = 1

        # Handle sections
        if replace:
            # Delete existing sections
            ExtracurricularActivitySection.objects.filter(activity=activity).delete()

        created_sections = 0
        updated_sections = 0

        for section_data in sections_data:
            section_id = section_data.get('section_id', '').strip()
            if not section_id:
                continue

            section = ExtracurricularActivitySection.objects.filter(
                activity=activity,
                section_id=section_id
            ).first()

            if not section:
                section = ExtracurricularActivitySection.objects.create(
                    activity=activity,
                    section_id=section_id,
                    title=section_data.get('title', ''),
                    content_html=section_data.get('content_html', ''),
                    order=section_data.get('order', 1),
                    icon=section_data.get('icon', 'bx-star'),
                    description=section_data.get('description', ''),
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                created_sections += 1
            else:
                section.title = section_data.get('title', '')
                section.content_html = section_data.get('content_html', '')
                section.order = section_data.get('order', 1)
                section.icon = section_data.get('icon', 'bx-star')
                section.description = section_data.get('description', '')
                section.object_status = choices.ObjectStatus.ACTIVE
                section.save()
                updated_sections += 1

        return {
            'created_activity': created_activity,
            'updated_activity': updated_activity,
            'created_sections': created_sections,
            'updated_sections': updated_sections,
        }

    def print_result(self, result: dict, single_file: bool = False):
        """Print import result for single file."""
        if single_file:
            self.stdout.write(self.style.SUCCESS(
                f"Activity: {'Created' if result['created_activity'] else 'Updated'}, "
                f"Sections: {result['created_sections']} created, "
                f"{result['updated_sections']} updated"
            ))

    def print_summary(self, stats: dict):
        """Print summary statistics."""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("IMPORT SUMMARY"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"Total files processed: {stats['processed']}/{stats['total']}")
        self.stdout.write(f"Activities created: {stats['created_activities']}")
        self.stdout.write(f"Activities updated: {stats['updated_activities']}")
        self.stdout.write(f"Sections created: {stats['created_sections']}")
        self.stdout.write(f"Sections updated: {stats['updated_sections']}")
        
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f"\nErrors: {stats['errors']}"))
            for error in stats['error_details']:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ All files processed successfully!"))

