"""Seed Class 12 aptitude real-life signs, impacts, and consolidated ID lists."""

from django.core.management.base import BaseCommand

from app.class12_aptitude_signs_impact import (
    seed_consolidated_sign_impact_ids,
    seed_master_signs_impact_from_legacy,
)


class Command(BaseCommand):
    help = (
        'Seed master real-life signs / daily-life impacts from legacy JSON, '
        'then populate consolidated row ID lists from each row codes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite-master',
            action='store_true',
            help='Replace master sign/impact rows from legacy JSON.',
        )
        parser.add_argument(
            '--overwrite-ids',
            action='store_true',
            help='Replace consolidated sign/impact ID lists even when already set.',
        )
        parser.add_argument(
            '--master-only',
            action='store_true',
            help='Only seed master sign/impact tables.',
        )
        parser.add_argument(
            '--ids-only',
            action='store_true',
            help='Only seed consolidated ID lists (master rows must exist).',
        )

    def handle(self, *args, **options):
        if not options['ids_only']:
            result = seed_master_signs_impact_from_legacy(
                overwrite=options['overwrite_master'],
            )
            if not result.get('ok'):
                self.stderr.write(self.style.ERROR(result.get('error', 'Master seed failed.')))
                return
            self.stdout.write(
                self.style.SUCCESS(
                    f"Master signs: {result.get('sign_count', 0)}, "
                    f"impacts: {result.get('impact_count', 0)}"
                )
            )

        if not options['master_only']:
            result = seed_consolidated_sign_impact_ids(overwrite=options['overwrite_ids'])
            if not result.get('ok'):
                self.stderr.write(self.style.ERROR(result.get('error', 'ID seed failed.')))
                return
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated consolidated ID lists on {result.get('count', 0)} row(s)."
                )
            )
