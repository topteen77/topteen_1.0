from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from app.stream_sorter_unique_streams import (
    DEFAULT_OUTPUT,
    DEFAULT_SOURCE,
    write_unique_streams_json,
)


class Command(BaseCommand):
    help = (
        'Build class10_stream_sorter_unique_streams.json: unique streams with '
        'careers deduped per stream (same career name may repeat across streams).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default=str(DEFAULT_SOURCE),
            help='Input class10_stream_sorter_guidance.json path',
        )
        parser.add_argument(
            '--output',
            default=str(DEFAULT_OUTPUT),
            help='Output unique streams JSON path',
        )

    def handle(self, *args, **options):
        source = Path(options['source'])
        output = Path(options['output'])
        write_unique_streams_json(output_path=output, source_path=source)
        self.stdout.write(self.style.SUCCESS(f'Wrote unique stream careers JSON -> {output}'))
