"""
Import student(s) from origin DB (topteen12) to target DB (topteen12-old).

Identification by email only — never overwrite:
- If a student with the same email already exists in target -> use existing id (skip insert).
- If email does not exist in target -> insert as new student and use the new id for all related rows.

Logs: "Student inserted as new, id=X" or "Student exists (email=...), using existing id X".

Usage:
  python manage.py import_student_from_origin --student-id 2576
  python manage.py import_student_from_origin --student-id 2576 --dry-run
  python manage.py import_student_from_origin  (all students)
"""

from django.core.management.base import BaseCommand
from django.db import connections

from institute.student_validation_utils import (
    ensure_connection,
    get_student_user_ids,
    resolve_or_insert_student_in_target,
    copy_user_table_rows,
)

SOURCE_ALIAS = 'topteen12'
TARGET_ALIAS = 'topteen12-old'


class Command(BaseCommand):
    help = (
        'Import students from origin (topteen12) to target (topteen12-old). '
        'Identify by email: skip if email exists (use existing id), else insert as new. '
        'Use --student-id ID or run for all students. --dry-run to preview.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--student-id',
            type=int,
            default=None,
            metavar='USER_ID',
            help='Import a single student by source user id. If omitted, import all students.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not insert; only show resolve/insert decision and log message for each student.',
        )

    def handle(self, *args, **options):
        student_id = options['student_id']
        dry_run = options['dry_run']

        self.stdout.write(self.style.SUCCESS(f'Import: {SOURCE_ALIAS} -> {TARGET_ALIAS}\n'))
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] No data will be written to target.\n'))
        ensure_connection(SOURCE_ALIAS, role='source')
        ensure_connection(TARGET_ALIAS, role='target')

        conn_src = connections[SOURCE_ALIAS]
        conn_tgt = connections[TARGET_ALIAS]

        with conn_src.cursor() as src_cur, conn_tgt.cursor() as tgt_cur:
            student_ids = get_student_user_ids(src_cur, student_id=student_id)
            if not student_ids:
                self.stdout.write(self.style.ERROR(f'No student(s) found in source. Exiting.'))
                return

            self.stdout.write(f'Resolving/inserting {len(student_ids)} student(s) by email (do not overwrite).\n')
            inserted_new = 0
            used_existing = 0
            errors = 0
            id_map = {}  # source_user_id -> target_user_id for use in related-table copy later

            for src_uid in student_ids:
                target_id, status, log_msg = resolve_or_insert_student_in_target(
                    src_cur, tgt_cur, src_uid, dry_run=dry_run
                )
                if status == 'new' or status == 'would_insert':
                    if status == 'new':
                        inserted_new += 1
                        id_map[src_uid] = target_id
                    self.stdout.write(self.style.SUCCESS(f'  [student_id={src_uid}] {log_msg}'))
                elif status == 'existing':
                    used_existing += 1
                    id_map[src_uid] = target_id
                    self.stdout.write(self.style.SUCCESS(f'  [student_id={src_uid}] {log_msg}'))
                else:
                    errors += 1
                    self.stdout.write(self.style.ERROR(f'  [student_id={src_uid}] {log_msg}'))

            # Copy test results and related user tables (use target user_id from id_map)
            if id_map and not dry_run:
                self.stdout.write('')
                self.stdout.write('Copying student test data (Results, TestCompletion)...')
                for table, user_col in [
                    ('app_results', 'user_id'),
                    ('app_testcompletion', 'user_id'),
                ]:
                    n, err = copy_user_table_rows(
                        src_cur, tgt_cur, table, user_col, id_map, dry_run=False
                    )
                    if err:
                        self.stdout.write(self.style.WARNING(f'  {table}: {err}'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  {table}: {n} row(s) copied'))

            if not dry_run and (inserted_new or used_existing or id_map):
                conn_tgt.commit()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'Done. Inserted as new: {inserted_new}, using existing id: {used_existing}, errors: {errors}.'
            ))
            if dry_run:
                self.stdout.write(self.style.WARNING('Dry-run: no changes were committed to target.'))
            else:
                self.stdout.write('Origin DB was not modified. Target DB was updated only for new students.')
