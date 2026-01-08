"""
Django management command to generate a JSON file containing all career cluster names
from the database. This JSON can be used for folder name verification.
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand
from careers.models import CareerCluster
from core import choices


class Command(BaseCommand):
    help = 'Generate JSON file with all career cluster names from database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='scripts/career_cluster_names.json',
            help='Output JSON file path (default: scripts/career_cluster_names.json)'
        )
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Include inactive/deleted clusters in the output'
        )

    def handle(self, *args, **options):
        output_path = options['output']
        include_inactive = options['include_inactive']
        
        # Get all career clusters
        if include_inactive:
            # Use complete manager to include soft-deleted clusters
            complete_mgr = CareerCluster.objects.complete() if hasattr(CareerCluster.objects, 'complete') else CareerCluster._base_manager
            clusters = complete_mgr.all().order_by('name')
        else:
            # Only active clusters
            clusters = CareerCluster.objects.filter(
                object_status=choices.ObjectStatus.ACTIVE
            ).order_by('name')
        
        # Build JSON structure
        cluster_data = {
            'total_clusters': clusters.count(),
            'include_inactive': include_inactive,
            'clusters': []
        }
        
        for cluster in clusters:
            cluster_info = {
                'id': cluster.id,
                'name': cluster.name,
                'slug': cluster.slug,
                'object_status': getattr(cluster, 'object_status', None),
                'status_display': 'ACTIVE' if getattr(cluster, 'object_status', None) == choices.ObjectStatus.ACTIVE else 'INACTIVE/DELETED',
                'normalized_name': cluster.name.lower().strip() if cluster.name else '',
            }
            
            # Add parent cluster info if exists
            if cluster.parent:
                cluster_info['parent'] = {
                    'id': cluster.parent.id,
                    'name': cluster.parent.name,
                    'slug': cluster.parent.slug
                }
            
            cluster_data['clusters'].append(cluster_info)
        
        # Write to JSON file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cluster_data, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully generated cluster names JSON file'
            )
        )
        self.stdout.write(f'  Output file: {output_file.resolve()}')
        self.stdout.write(f'  Total clusters: {cluster_data["total_clusters"]}')
        
        # Count by status
        active_count = sum(1 for c in cluster_data['clusters'] if c['object_status'] == choices.ObjectStatus.ACTIVE)
        inactive_count = cluster_data['total_clusters'] - active_count
        
        self.stdout.write(f'  Active clusters: {active_count}')
        if include_inactive:
            self.stdout.write(f'  Inactive/Deleted clusters: {inactive_count}')
        
        # Show sample clusters
        self.stdout.write(f'\n  Sample clusters (first 10):')
        for cluster in cluster_data['clusters'][:10]:
            status_icon = '✓' if cluster['object_status'] == choices.ObjectStatus.ACTIVE else '✗'
            self.stdout.write(f'    {status_icon} {cluster["name"]} (ID: {cluster["id"]})')
        
        if cluster_data['total_clusters'] > 10:
            self.stdout.write(f'    ... and {cluster_data["total_clusters"] - 10} more')
        
        self.stdout.write('\n' + self.style.SUCCESS('JSON file generation completed!'))

