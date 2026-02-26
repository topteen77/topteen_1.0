"""
Import missing careers and their child rows from topteen12 (source) to topteen12-old (target).

Use when compare_career_tables_topteen12_to_old shows "career_id(s) not in target":
those careers exist in source but were never in target, so their child rows could not
be imported. This command inserts those careers from source to target, then inserts
all child rows that reference them (INSERT IGNORE).

Options:
  --career-ids ID1,ID2,...   Comma-separated career IDs to import (e.g. 100,117,118).
  --discover                 Find all career_ids that appear in source child tables
                             but not in target careers_career, then import them and
                             their child rows (no need to list IDs manually).

Source: topteen12. Target: topteen12-old.
"""

from django.core.management.base import BaseCommand
from django.db import connections
from django.conf import settings
from decouple import config

SOURCE_ALIAS = 'topteen12'
TARGET_ALIAS = 'topteen12-old'

CAREER_TABLE = 'careers_career'
CHILD_TABLES_WITH_CAREER_FK = [
    'careers_career_skills',
    'careers_career_prospective_employment_areas',
    'careers_career_prospective_recruiters',
    'careers_career_videos',
    'careers_riaseccareer_careers',
]


def get_db_config(prefix):
    base = settings.DATABASES.get('default', {}).copy()
    base.update({
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config(f'{prefix}NAME', default=base.get('NAME', '')),
        'USER': config(f'{prefix}USER', default=base.get('USER', config('DB_USER', default=''))),
        'PASSWORD': config(f'{prefix}PASSWORD', default=base.get('PASSWORD', config('DB_PASSWORD', default=''))),
        'HOST': config(f'{prefix}HOST', default=base.get('HOST', config('DB_HOST', default='127.0.0.1'))),
        'PORT': config(f'{prefix}PORT', default=base.get('PORT', config('DB_PORT', default='3306'))),
        'OPTIONS': base.get('OPTIONS', {}) or {'charset': 'utf8mb4'},
    })
    return base


def ensure_connections(source_alias, target_alias):
    default_db = settings.DATABASES.get('default', {})
    if source_alias not in settings.DATABASES:
        cfg = get_db_config('DB_SOURCE_')
        if not cfg.get('NAME'):
            raise ValueError(
                f'Source DB not configured. Set DB_SOURCE_NAME (and DB_SOURCE_*) in .env or add "{source_alias}" to settings.DATABASES.'
            )
        settings.DATABASES[source_alias] = cfg
    if target_alias not in settings.DATABASES:
        cfg = get_db_config('DB_TARGET_')
        if not cfg.get('NAME'):
            settings.DATABASES[target_alias] = dict(default_db) if default_db else cfg
        else:
            settings.DATABASES[target_alias] = cfg


def get_table_columns(cursor, table):
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
        [table]
    )
    return [row[0] for row in cursor.fetchall()]


def get_columns_for_copy(source_cursor, target_cursor, table):
    src_cols = set(get_table_columns(source_cursor, table))
    tgt_cols = set(get_table_columns(target_cursor, table))
    common = src_cols & tgt_cols
    src_ordered = get_table_columns(source_cursor, table)
    return [c for c in src_ordered if c in common]


class Command(BaseCommand):
    help = (
        'Import missing careers (and their child rows) from topteen12 to topteen12-old. '
        'Use --career-ids 100,117,... or --discover to find IDs from source child tables.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--career-ids',
            type=str,
            default=None,
            help='Comma-separated career IDs to import (e.g. 100,117,118,119).',
        )
        parser.add_argument(
            '--discover',
            action='store_true',
            help='Find career_ids that appear in source child tables but not in target, then import them.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not insert; only show what would be done.',
        )

    def handle(self, *args, **options):
        career_ids_arg = options.get('career_ids')
        discover = options.get('discover')
        dry_run = options.get('dry_run')

        if not career_ids_arg and not discover:
            self.stdout.write(
                self.style.ERROR('Provide --career-ids ID1,ID2,... and/or --discover.')
            )
            return

        ensure_connections(SOURCE_ALIAS, TARGET_ALIAS)
        conn_src = connections[SOURCE_ALIAS]
        conn_tgt = connections[TARGET_ALIAS]

        with conn_src.cursor() as src_cur, conn_tgt.cursor() as tgt_cur:
            # Resolve career IDs to import
            if discover:
                tgt_cur.execute(f"SELECT id FROM `{CAREER_TABLE}`")
                tgt_ids = {row[0] for row in tgt_cur.fetchall()}
                src_cur.execute(f"SELECT id FROM `{CAREER_TABLE}`")
                src_career_ids = {row[0] for row in src_cur.fetchall()}
                missing = set()
                for table in CHILD_TABLES_WITH_CAREER_FK:
                    try:
                        src_cur.execute(f"SELECT DISTINCT career_id FROM `{table}` WHERE career_id IS NOT NULL")
                        for row in src_cur.fetchall():
                            cid = row[0]
                            if cid not in tgt_ids and cid in src_career_ids:
                                missing.add(cid)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'  {table}: skip ({e})'))
                career_ids = sorted(missing)
                self.stdout.write(self.style.SUCCESS(f'[Discover] Found {len(career_ids)} career_id(s) in source (in child tables but missing in target).'))
                if not career_ids:
                    self.stdout.write('Nothing to import.')
                    return
            else:
                career_ids = [int(x.strip()) for x in career_ids_arg.split(',') if x.strip()]
                self.stdout.write(self.style.SUCCESS(f'[Career IDs] {len(career_ids)} IDs to import: {career_ids[:20]}' + (' ...' if len(career_ids) > 20 else '')))

            # Only insert careers that are actually missing in target
            tgt_cur.execute(f"SELECT id FROM `{CAREER_TABLE}`")
            tgt_career_ids = {row[0] for row in tgt_cur.fetchall()}
            to_insert = [c for c in career_ids if c not in tgt_career_ids]
            career_ids_for_children = career_ids  # insert child rows for all requested IDs

            self.stdout.write('\n[1] Inserting missing careers from source to target...')
            if not to_insert:
                self.stdout.write(self.style.SUCCESS(f'  All {len(career_ids)} career ID(s) already in target; skip career insert.'))
            cols = get_columns_for_copy(src_cur, tgt_cur, CAREER_TABLE)
            if not cols:
                self.stdout.write(self.style.WARNING(f'  {CAREER_TABLE}: no common columns, skip'))
            elif to_insert:
                col_list = ", ".join(f"`{c}`" for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))
                inserted = 0
                for cid in to_insert:
                    src_cur.execute(f"SELECT {col_list} FROM `{CAREER_TABLE}` WHERE id = %s", [cid])
                    row = src_cur.fetchone()
                    if not row:
                        self.stdout.write(self.style.WARNING(f'  Career id={cid} not found in source, skip'))
                        continue
                    if dry_run:
                        inserted += 1
                        continue
                    try:
                        tgt_cur.execute(
                            f"INSERT INTO `{CAREER_TABLE}` ({col_list}) VALUES ({placeholders})",
                            row
                        )
                        inserted += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  Career id={cid}: {e}'))
                self.stdout.write(f'  {CAREER_TABLE}: {inserted} career(s) inserted.')

            # 2) Insert child rows where career_id IN (career_ids_for_children)
            self.stdout.write('\n[2] Inserting child rows (INSERT IGNORE)...')
            for table in CHILD_TABLES_WITH_CAREER_FK:
                try:
                    tgt_cols = get_table_columns(tgt_cur, table)
                    src_cols = get_table_columns(src_cur, table)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  {table}: skip ({e})'))
                    continue
                cols = get_columns_for_copy(src_cur, tgt_cur, table)
                if not cols or 'career_id' not in cols:
                    self.stdout.write(f'  {table}: no common columns or no career_id, skip')
                    continue
                col_list = ", ".join(f"`{c}`" for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))
                career_id_idx = cols.index('career_id')
                # Fetch only rows whose career_id is in our list
                placeholders_in = ",".join(["%s"] * len(career_ids_for_children))
                src_cur.execute(
                    f"SELECT {col_list} FROM `{table}` WHERE career_id IN ({placeholders_in})",
                    career_ids_for_children
                )
                rows = src_cur.fetchall()
                if dry_run:
                    self.stdout.write(f'  [DRY RUN] {table}: would INSERT IGNORE {len(rows)} rows')
                    continue
                inserted = 0
                for row in rows:
                    try:
                        tgt_cur.execute(
                            f"INSERT IGNORE INTO `{table}` ({col_list}) VALUES ({placeholders})",
                            row
                        )
                        if tgt_cur.rowcount:
                            inserted += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  {table} row: {e}'))
                self.stdout.write(f'  {table}: {inserted} rows inserted (INSERT IGNORE)')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes were made.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport of missing careers and child rows completed.'))
