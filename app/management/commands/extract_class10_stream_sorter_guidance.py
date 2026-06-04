import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from app.stream_sorter_extraction import build_guidance_payload
from app.stream_sorter_unique_streams import write_unique_streams_json

DEFAULT_SOURCE = Path(
    '/home/itpc6/Documents/arvinder/new/10 CLASS RIASAC- STREAM SORTER'
)
DEFAULT_OUTPUT = Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_stream_sorter_guidance.json'


class Command(BaseCommand):
    help = (
        'Extract Stream-Wise Premium Career Options and Most Future-Relevant Careers '
        'from Class 10 RIASEC Stream Sorter .docx files into JSON.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default=str(DEFAULT_SOURCE),
            help='Directory containing the six RIASEC .docx files',
        )
        parser.add_argument(
            '--output',
            default=str(DEFAULT_OUTPUT),
            help='Output JSON path',
        )

    def handle(self, *args, **options):
        source_dir = Path(options['source'])
        output_path = Path(options['output'])
        payload = build_guidance_payload(source_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        file_count = len(payload.get('files') or {})
        code_count = len(payload.get('category_code_to_letter') or {})
        self.stdout.write(
            self.style.SUCCESS(
                f'Wrote {file_count} RIASEC file(s), {code_count} category code(s) -> {output_path}'
            )
        )
        unique_path = write_unique_streams_json(source_path=output_path)
        stats = json.loads(unique_path.read_text(encoding='utf-8')).get('stats', {})
        self.stdout.write(
            self.style.SUCCESS(
                f'Wrote unique streams ({stats.get("unique_streams", 0)} streams, '
                f'{stats.get("total_stream_career_entries", 0)} careers) -> {unique_path}'
            )
        )
