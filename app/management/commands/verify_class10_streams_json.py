import json

from django.core.management.base import BaseCommand

from app.stream_sorter_guidance import (
    UNIQUE_STREAMS_JSON_PATH,
    load_unique_streams_catalog,
    verify_streams_catalog_coverage,
)


class Command(BaseCommand):
    help = (
        'Verify class10_stream_sorter_unique_streams.json defines all standard streams '
        'and that DB Stream names map to the catalog.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            default=str(UNIQUE_STREAMS_JSON_PATH),
            help='Path to class10_stream_sorter_unique_streams.json',
        )

    def handle(self, *args, **options):
        catalog = load_unique_streams_catalog(options['json'])
        report = verify_streams_catalog_coverage(catalog, include_db_streams=True)

        self.stdout.write('JSON stream labels:')
        for label in report['json_stream_labels']:
            self.stdout.write(f'  - {label}')

        self.stdout.write(f"\nJSON stream codes: {', '.join(report['json_stream_codes'])}")
        if report['missing_standard_codes']:
            self.stdout.write(self.style.ERROR(
                f"Missing standard codes in JSON: {', '.join(report['missing_standard_codes'])}"
            ))

        self.stdout.write('\nDB Stream mapping:')
        for row in report['db_streams']:
            style = self.style.SUCCESS if row['mapped'] else self.style.WARNING
            self.stdout.write(style(
                f"  {row['stream_name']!r} codes={row['codes']} mapped={row['mapped']}"
            ))

        if report['db_unmapped']:
            self.stdout.write(self.style.WARNING(
                '\nDB streams not in JSON catalog (no premium list yet):'
            ))
            for name in report['db_unmapped']:
                self.stdout.write(f'  - {name}')

        if report['ok']:
            self.stdout.write(self.style.SUCCESS('\nVerification passed for standard streams.'))
        else:
            self.stdout.write(self.style.WARNING(
                '\nVerification completed with gaps (see unmapped DB streams above).'
            ))

        self.stdout.write(json.dumps(report['catalog_stats'] or catalog.get('stats') or {}, indent=2))
