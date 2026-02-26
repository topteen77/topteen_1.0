"""
Compare career tables between topteen12 (source) and topteen12-old (target).

Prints row counts per table and, for careers_career, which career IDs exist only in
source or only in target. Use this to verify sync or debug FK errors.

Usage:
  python manage.py compare_career_tables_topteen12_to_old
  python manage.py compare_career_tables_topteen12_to_old --show-ids
"""

from django.core.management.base import BaseCommand
from django.db import connections
from django.conf import settings
from decouple import config

SOURCE_ALIAS = 'topteen12'
TARGET_ALIAS = 'topteen12-old'

CAREER_TABLES = [
    'careers_careerpathstep',
    'careers_skill',
    'careers_prospectiveemploymentarea',
    'careers_prospectiverecruiter',
    'careers_careertags',
    'careers_videocategory',
    'careers_careercluster',
    'careers_careerpath',
    'careers_videos',
    'careers_career',
    'careers_careerrating',
    'careers_careermedia',
    'careers_profession',
    'careers_careerfaq',
    'careers_careershortlist',
    'careers_riaseccareer',
    'career_embeddings',
    'careers_careerpath_career_path_steps',
    'careers_career_skills',
    'careers_career_prospective_employment_areas',
    'careers_career_prospective_recruiters',
    'careers_career_career_tags',
    'careers_career_courses',
    'careers_career_career_cluster',
    'careers_career_career_paths',
    'careers_career_videos',
    'careers_videos_category',
    'careers_videos_shortlist',
    'careers_riaseccareer_careers',
]

CAREER_TABLE = 'careers_career'


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
            settings.DATABASES[target_alias] = dict(settings.DATABASES.get('default', {})) if settings.DATABASES.get('default') else cfg
        else:
            settings.DATABASES[target_alias] = cfg


def get_table_count(cursor, table):
    try:
        cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        return cursor.fetchone()[0]
    except Exception as e:
        return (None, str(e))


class Command(BaseCommand):
    help = 'Compare career table row counts and careers_career IDs between topteen12 and topteen12-old.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-ids',
            action='store_true',
            help='Print career IDs only-in-source and only-in-target (can be many).',
        )

    def handle(self, *args, **options):
        show_ids = options['show_ids']
        self.stdout.write(self.style.SUCCESS(f'Compare: {SOURCE_ALIAS} (source) vs {TARGET_ALIAS} (target)\n'))
        ensure_connections(SOURCE_ALIAS, TARGET_ALIAS)
        conn_src = connections[SOURCE_ALIAS]
        conn_tgt = connections[TARGET_ALIAS]

        with conn_src.cursor() as src_cur, conn_tgt.cursor() as tgt_cur:
            # Row counts per table
            self.stdout.write('Row counts:')
            self.stdout.write(f'  {"Table":<45} {"Source":>10} {"Target":>10} {"Diff":>8}')
            self.stdout.write('  ' + '-' * 75)
            for table in CAREER_TABLES:
                src_count = get_table_count(src_cur, table)
                tgt_count = get_table_count(tgt_cur, table)
                if isinstance(src_count, tuple):
                    self.stdout.write(self.style.WARNING(f'  {table:<45} source error: {src_count[1]}'))
                    continue
                if isinstance(tgt_count, tuple):
                    self.stdout.write(self.style.WARNING(f'  {table:<45} {src_count or 0:>10} target error: {tgt_count[1]}'))
                    continue
                diff = (src_count or 0) - (tgt_count or 0)
                diff_str = f'{diff:+d}' if diff != 0 else '0'
                style = self.style.ERROR if diff != 0 else None
                msg = f'  {table:<45} {src_count or 0:>10} {tgt_count or 0:>10} {diff_str:>8}'
                if style:
                    self.stdout.write(style(msg))
                else:
                    self.stdout.write(msg)

            # careers_career: IDs only in source / only in target
            self.stdout.write('')
            src_cur.execute(f"SELECT id FROM `{CAREER_TABLE}`")
            src_ids = {row[0] for row in src_cur.fetchall()}
            tgt_cur.execute(f"SELECT id FROM `{CAREER_TABLE}`")
            tgt_ids = {row[0] for row in tgt_cur.fetchall()}
            only_in_source = src_ids - tgt_ids
            only_in_target = tgt_ids - src_ids
            self.stdout.write(self.style.SUCCESS('careers_career ID comparison:'))
            self.stdout.write(f'  Source count: {len(src_ids)}, Target count: {len(tgt_ids)}')
            self.stdout.write(f'  IDs only in source (missing in target): {len(only_in_source)}')
            self.stdout.write(f'  IDs only in target (extra in target):   {len(only_in_target)}')
            if only_in_source and show_ids:
                sample = sorted(only_in_source)[:50]
                self.stdout.write(f'    Only in source (sample): {sample}' + (' ...' if len(only_in_source) > 50 else ''))
            if only_in_target and show_ids:
                sample = sorted(only_in_target)[:50]
                self.stdout.write(f'    Only in target (sample): {sample}' + (' ...' if len(only_in_target) > 50 else ''))

            # Child tables with career_id: how many rows reference a career_id not in target?
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Child rows with career_id not in target (causes FK errors):'))
            self.stdout.write('  (These career_ids appear in source child table but not in target careers_career; use --show-ids to list them)')
            child_tables = [
                'careers_career_skills',
                'careers_career_prospective_employment_areas',
                'careers_career_prospective_recruiters',
                'careers_career_videos',
                'careers_riaseccareer_careers',
            ]
            for table in child_tables:
                if table not in CAREER_TABLES:
                    continue
                try:
                    src_cur.execute(f"SELECT DISTINCT career_id FROM `{table}`")
                    src_career_ids = {row[0] for row in src_cur.fetchall()}
                    # Exclude NULLs: only real ids that are missing from target
                    non_null = {x for x in src_career_ids if x is not None}
                    missing = non_null - tgt_ids
                    null_count = len(src_career_ids) - len(non_null)
                    if missing:
                        src_cur.execute(
                            f"SELECT COUNT(*) FROM `{table}` WHERE career_id IN ({','.join(['%s'] * len(missing))})",
                            list(missing)
                        )
                        orphan_count = src_cur.fetchone()[0]
                        msg = f'  {table}: {orphan_count} rows reference {len(missing)} career_id(s) not in target'
                        if null_count:
                            msg += f' (+ {null_count} NULL career_id)'
                        self.stdout.write(self.style.ERROR(msg))
                        if show_ids or len(missing) <= 30:
                            sample = sorted(missing)[:50]
                            self.stdout.write(f'    Missing career_ids: {sample}' + (' ...' if len(missing) > 50 else ''))
                        elif not show_ids:
                            self.stdout.write(f'    Run with --show-ids to list the {len(missing)} missing career_id(s)')
                    elif null_count:
                        self.stdout.write(self.style.WARNING(f'  {table}: {null_count} row(s) with NULL career_id (skipped for FK check)'))
                    else:
                        self.stdout.write(f'  {table}: all career_ids present in target')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  {table}: skip ({e})'))

        self.stdout.write(self.style.SUCCESS('\nDone.'))
