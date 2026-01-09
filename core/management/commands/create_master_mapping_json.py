"""
Django management command to create master JSON files from database.
Exports CareerCluster, Career, and Course data to JSON files for mapping purposes.
"""

import json
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from careers.models import CareerCluster, Career
from courses.models import Course
from core import choices


class Command(BaseCommand):
    help = 'Create master JSON files from database (CareerCluster, Career, Course)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='static/data/combined_report_data',
            help='Output directory for JSON files (default: static/data/combined_report_data)'
        )

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir'])
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stdout.write(self.style.SUCCESS('Starting master JSON export...'))
        
        # Export Career Clusters
        self.export_career_clusters(output_dir)
        
        # Export Career Roles (Careers)
        self.export_career_roles(output_dir)
        
        # Export Educational Pathways (Courses)
        self.export_educational_pathways(output_dir)
        
        self.stdout.write(self.style.SUCCESS('\n✓ Master JSON files created successfully!'))

    def export_career_clusters(self, output_dir):
        """Export all CareerCluster records to JSON"""
        self.stdout.write('\nExporting Career Clusters...')
        
        clusters = CareerCluster.objects.filter(
            object_status=choices.ObjectStatus.ACTIVE
        ).order_by('id').values('id', 'name', 'slug')
        
        clusters_list = list(clusters)
        
        output_data = {
            "clusters": clusters_list,
            "total_count": len(clusters_list),
            "exported_at": str(Path(__file__).stat().st_mtime)
        }
        
        output_file = output_dir / 'master_career_clusters.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'  ✓ Exported {len(clusters_list)} career clusters to {output_file}'
            )
        )

    def export_career_roles(self, output_dir):
        """Export all Career records to JSON (these are the career roles)"""
        self.stdout.write('\nExporting Career Roles (Careers)...')
        
        careers = Career.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).order_by('id').values('id', 'name', 'slug')
        
        careers_list = list(careers)
        
        output_data = {
            "roles": careers_list,
            "total_count": len(careers_list),
            "exported_at": str(Path(__file__).stat().st_mtime)
        }
        
        output_file = output_dir / 'master_career_roles.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'  ✓ Exported {len(careers_list)} career roles to {output_file}'
            )
        )

    def export_educational_pathways(self, output_dir):
        """Export all Course records to JSON (these are the educational pathways)"""
        self.stdout.write('\nExporting Educational Pathways (Courses)...')
        
        courses = Course.objects.all().order_by('id').values('id', 'name', 'slug')
        
        courses_list = list(courses)
        
        output_data = {
            "pathways": courses_list,
            "total_count": len(courses_list),
            "exported_at": str(Path(__file__).stat().st_mtime)
        }
        
        output_file = output_dir / 'master_educational_pathways.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'  ✓ Exported {len(courses_list)} educational pathways to {output_file}'
            )
        )
