from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from app.stream_sorter_guidance import import_catalog_from_json_file

DEFAULT_JSON = (
    Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_stream_sorter_unique_streams.json'
)


class Command(BaseCommand):
    help = 'Seed Class 10 combined report career guidance from unique streams JSON into admin DB.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            default=str(DEFAULT_JSON),
            help='Path to class10_stream_sorter_unique_streams.json',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing streams/careers before import',
        )

    def handle(self, *args, **options):
        result = import_catalog_from_json_file(
            json_path=Path(options['json']),
            replace=options['replace'],
        )
        if not result.get('ok'):
            self.stderr.write(self.style.ERROR(result.get('error', 'Import failed')))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {result.get('streams')} streams, "
                f"{result.get('stream_careers')} stream careers, "
                f"{result.get('future_careers')} future-relevant careers."
            )
        )
