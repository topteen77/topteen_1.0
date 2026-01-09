"""
Django management command to export corrected mappings from database to JSON.
This generates the final combined_report_Average_above_average.json file.
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand
from app_post_matric.models import AptitudeCombinationMapping


class Command(BaseCommand):
    help = 'Export corrected mappings from database to JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-file',
            type=str,
            default='static/data/combined_report_Average_above_average.json',
            help='Output file path for the combined report JSON'
        )

    def handle(self, *args, **options):
        output_file = Path(options['output_file'])
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.stdout.write(self.style.SUCCESS('Starting export of corrected mappings...'))
        
        # Get all aptitude combinations
        combinations = AptitudeCombinationMapping.objects.all().prefetch_related(
            'clusters', 'roles', 'pathways'
        ).order_by('aptitude_code')
        
        total = combinations.count()
        self.stdout.write(f'\nFound {total} aptitude combinations')
        
        # Build rows array
        rows = []
        complete_count = 0
        incomplete_count = 0
        
        for combination in combinations:
            # Get clusters
            clusters = [
                {'id': c.id, 'name': c.name, 'slug': c.slug}
                for c in combination.clusters.all()
            ]
            
            # Get roles
            roles = [
                {'id': r.id, 'name': r.name, 'slug': r.slug}
                for r in combination.roles.all()
            ]
            
            # Get pathways
            pathways = [
                {'id': p.id, 'name': p.name, 'slug': p.slug}
                for p in combination.pathways.all()
            ]
            
            row = {
                'Areas': combination.aptitude_areas,
                'Career Clusters': clusters,
                'Career Roles': roles,
                'Educational Pathways': pathways
            }
            
            rows.append(row)
            
            if combination.is_complete:
                complete_count += 1
            else:
                incomplete_count += 1
        
        # Create output structure
        output_data = {
            'rows': rows,
            'metadata': {
                'total_combinations': total,
                'complete': complete_count,
                'incomplete': incomplete_count,
                'exported_from': 'database'
            }
        }
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Export completed!'))
        self.stdout.write(f'  Output file: {output_file}')
        self.stdout.write(f'  Total combinations: {total}')
        self.stdout.write(f'  Complete: {complete_count}')
        self.stdout.write(f'  Incomplete: {incomplete_count}')
        
        if incomplete_count > 0:
            self.stdout.write(self.style.WARNING(f'\n⚠ {incomplete_count} combinations are incomplete - review in admin'))
