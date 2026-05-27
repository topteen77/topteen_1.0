"""
Export all careers with cluster assignments to CSV for related-career planning.

One row per (career, cluster) pair. Careers with no cluster get a single row with
empty cluster columns.

related cluster id:
  - If the assigned cluster has a parent → parent cluster id
  - If the assigned cluster is top-level → comma-separated child cluster ids
"""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from careers.models import Career, CareerCluster
from core import choices


def related_cluster_ids_for(cluster):
    """
    Related clusters for spreadsheet planning:
    - Valid parent cluster id (when parent is not self)
    - Else sibling cluster ids (same parent, excluding self)
    - Else child cluster ids (excluding self; skips broken self-referential rows)
    """
    parent_id = cluster.parent_id
    if parent_id and parent_id != cluster.id:
        return str(parent_id)

    sibling_ids = list(
        CareerCluster.objects.filter(parent_id=parent_id)
        .exclude(id=cluster.id)
        .order_by('id')
        .values_list('id', flat=True)
    ) if parent_id else []

    if sibling_ids:
        return ','.join(str(i) for i in sibling_ids)

    child_ids = list(
        CareerCluster.objects.filter(parent_id=cluster.id)
        .exclude(id=cluster.id)
        .order_by('id')
        .values_list('id', flat=True)
    )
    return ','.join(str(i) for i in child_ids) if child_ids else ''


class Command(BaseCommand):
    help = (
        'Export all careers with cluster_id, cluster name, and related cluster id '
        'to all_careers.csv (for related-career linking spreadsheets).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='all_careers.csv',
            help='Output CSV path (default: all_careers.csv in project root)',
        )
        parser.add_argument(
            '--published-only',
            action='store_true',
            help='Only include careers with publish_status=PUBLISHED',
        )

    def handle(self, *args, **options):
        output_path = Path(options['output'])
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path

        qs = Career.objects.all().order_by('name', 'id')
        if options['published_only']:
            qs = qs.filter(publish_status=choices.PublishStatus.PUBLISHED)

        careers = qs.prefetch_related('career_cluster').select_related()

        fieldnames = ['id', 'career', 'cluster_id', 'cluster name', 'related cluster id']
        rows_written = 0

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for career in careers:
                clusters = list(career.career_cluster.all().order_by('id'))
                if not clusters:
                    writer.writerow({
                        'id': career.id,
                        'career': career.name or '',
                        'cluster_id': '',
                        'cluster name': '',
                        'related cluster id': '',
                    })
                    rows_written += 1
                    continue

                for cluster in clusters:
                    writer.writerow({
                        'id': career.id,
                        'career': career.name or '',
                        'cluster_id': cluster.id,
                        'cluster name': cluster.name or '',
                        'related cluster id': related_cluster_ids_for(cluster),
                    })
                    rows_written += 1

        career_count = qs.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Wrote {rows_written} row(s) for {career_count} career(s) → {output_path}'
            )
        )
