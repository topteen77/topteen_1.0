from django.core.management.base import BaseCommand

from kaunsa_mirror.sync import check_postgres_connection, sync_both, sync_universities


class Command(BaseCommand):
    help = (
        'Sync Kaunsa API universities list into PostgreSQL mirror (India / international). '
        'Requires KAUNSA_PG_ENABLED=True and running Postgres (e.g. docker compose -f docker/docker-compose.kaunsa-postgres.yml up -d).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'scope',
            nargs='?',
            default='both',
            choices=['india', 'international', 'both'],
            help='Which API endpoint config to sync (default: both)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only verify PostgreSQL connection; do not call API or write snapshots.',
        )

    def handle(self, *args, **options):
        scope = options['scope']
        dry = options['dry_run']

        if dry:
            try:
                ok = check_postgres_connection()
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'PostgreSQL check failed: {e}'))
                return
            if ok:
                self.stdout.write(self.style.SUCCESS('PostgreSQL kaunsa_mirror: connection OK'))
            return

        if scope == 'both':
            results = sync_both()
            for key, res in results.items():
                self._print_result(key, res)
            return

        res = sync_universities(scope)
        self._print_result(scope, res)

    def _print_result(self, label: str, res: dict):
        if res.get('success'):
            if res.get('skipped_no_change'):
                self.stdout.write(self.style.WARNING(f'{label}: unchanged (hash={res.get("hash", "")[:12]}…)'))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{label}: updated hash={res.get("hash", "")[:16]}… rows={res.get("row_count")}'
                    )
                )
        else:
            self.stderr.write(self.style.ERROR(f'{label}: FAILED {res.get("error", "unknown")}'))
