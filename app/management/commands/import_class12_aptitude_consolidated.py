"""
Import Class 11–12 aptitude consolidated report from Excel.

Phase 1: --dry-run validates only (no JSON, no DB).
Phase 2+: --write-json / --import-db (not enabled until manually verified).
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from app.class12_aptitude_consolidated_io import (
    EXPECTED_ROW_COUNT,
    VALID_CODES,
    build_json_payload,
    import_rows_to_db,
    load_and_validate,
)

DEFAULT_EXCEL = (
    Path(settings.BASE_DIR).parent
    / 'final CONSOLIDATED REPORT FOR 11TH-12TH.xlsx'
)
DEFAULT_JSON = (
    Path(settings.BASE_DIR) / 'app' / 'data' / 'class12_aptitude_consolidated_report.json'
)


class Command(BaseCommand):
    help = (
        'Validate (and optionally import) Class 11–12 aptitude consolidated report Excel. '
        'Use --dry-run first to validate without writing anything.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--excel-file',
            type=str,
            default=str(DEFAULT_EXCEL),
            help='Path to consolidated report Excel workbook',
        )
        parser.add_argument(
            '--output',
            type=str,
            default=str(DEFAULT_JSON),
            help='Output JSON path (Phase 2; requires --write-json)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate only; do not write JSON or database records',
        )
        parser.add_argument(
            '--write-json',
            action='store_true',
            help='Write validated data to JSON (disabled when --dry-run is set)',
        )
        parser.add_argument(
            '--import-db',
            action='store_true',
            help='Upsert Django model rows from validated Excel',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print sample rows and per-key statistics',
        )
        parser.add_argument(
            '--fail-fast',
            action='store_true',
            help='Stop after first validation error message',
        )

    def handle(self, *args, **options):
        excel_path = Path(options['excel_file'])
        dry_run = bool(options['dry_run'])
        write_json = bool(options['write_json'])
        import_db = bool(options['import_db'])
        verbose = bool(options['verbose'])

        if dry_run and write_json:
            self.stdout.write(
                self.style.WARNING('--dry-run set: JSON will NOT be written.')
            )
            write_json = False

        if dry_run and import_db:
            self.stdout.write(
                self.style.WARNING('--dry-run set: database will NOT be updated.')
            )
            import_db = False

        if not dry_run and not write_json and not import_db:
            dry_run = True
            self.stdout.write(
                self.style.WARNING(
                    'No action flags given; defaulting to --dry-run (validate only).'
                )
            )

        self.stdout.write(self.style.MIGRATE_HEADING('Class 12 Aptitude Consolidated Report Import'))
        self.stdout.write(f'Source: {excel_path}')

        try:
            result = load_and_validate(excel_path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f'Failed to read Excel: {exc}') from exc

        self._print_summary(result, dry_run=dry_run, verbose=verbose)

        if options['fail_fast'] and result.errors:
            raise CommandError(result.errors[0])

        if not result.ok:
            raise CommandError(
                f'Validation failed with {len(result.errors)} error(s). '
                'Fix the Excel file and re-run with --dry-run.'
            )

        if write_json:
            output_path = Path(options['output'])
            payload = build_json_payload(result.rows, source=excel_path.name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
            self.stdout.write(
                self.style.SUCCESS(f'Wrote {len(result.rows)} combinations to {output_path}')
            )

        if import_db:
            db_result = import_rows_to_db(rows=result.rows, source='rows', replace=True)
            if not db_result.get('ok'):
                raise CommandError(db_result.get('error', 'Database import failed.'))
            self.stdout.write(
                self.style.SUCCESS(
                    f'Imported {db_result.get("count", 0)} rows into '
                    'Class 12 Aptitude Consolidated Report admin model.'
                )
            )

        if dry_run and not write_json and not import_db:
            self.stdout.write(
                self.style.SUCCESS(
                    '\nDRY RUN complete — no files or database records were modified.'
                )
            )
            self.stdout.write(
                'Next: run with --write-json and/or --import-db after verification.'
            )

    def _print_summary(self, result, *, dry_run: bool, verbose: bool):
        rows = result.rows
        single_count = sum(1 for r in rows if len(r.get('codes') or []) == 1)
        combo_count = len(rows) - single_count

        mode = 'DRY RUN' if dry_run else 'IMPORT'
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_LABEL(f'{mode} — validation summary'))
        self.stdout.write(f'  Rows read:        {len(rows)} (expected {EXPECTED_ROW_COUNT})')
        self.stdout.write(f'  Unique keys:      {len({r["reasoning_combination"] for r in rows})}')
        self.stdout.write(f'  Single-code rows: {single_count}')
        self.stdout.write(f'  Combination rows: {combo_count}')
        self.stdout.write(f'  Valid codes:      {", ".join(sorted(VALID_CODES))}')
        self.stdout.write(f'  Errors:           {len(result.errors)}')
        self.stdout.write(f'  Warnings:         {len(result.warnings)}')

        if result.errors:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Errors:'))
            for err in result.errors:
                self.stdout.write(self.style.ERROR(f'  - {err}'))

        if result.warnings:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Warnings:'))
            for warn in result.warnings:
                self.stdout.write(self.style.WARNING(f'  - {warn}'))

        if verbose and rows:
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_LABEL('Sample rows (first 3):'))
            for row in rows[:3]:
                self.stdout.write(f'  [{row["reasoning_combination"]}]')
                self.stdout.write(f'    Description: {row["aptitude_description"][:80]}...')
                self.stdout.write(
                    f'    Clusters ({len(row["career_clusters"])}): '
                    f'{row["career_clusters"][:2]}...'
                )
                self.stdout.write(
                    f'    Pathways ({len(row["career_pathways"])}): '
                    f'{row["career_pathways"][:3]}'
                )
                self.stdout.write(
                    f'    Degrees ({len(row["degree_pathways"])}): '
                    f'{row["degree_pathways"][:3]}'
                )

            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_LABEL('Sample combination row:'))
            combo_sample = next(
                (r for r in rows if len(r.get('codes') or []) > 1),
                None,
            )
            if combo_sample:
                key = combo_sample['reasoning_combination']
                self.stdout.write(f'  Key: {key}')
                self.stdout.write(f'  Codes: {combo_sample["codes"]}')
                self.stdout.write(
                    f'  Narrative: {combo_sample["interpretation_narrative"][:120]}...'
                )

        if result.ok:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Validation PASSED.'))
