"""
Validate student data in the TARGET database (topteen12-old) after import. Read-only.

Ensures no duplicate student entries: checks duplicate emails and duplicate
(institute, student) in StudentManagement. When importing, never create duplicate entries.

Modes:
  - Dry-run: only connect, count students (or resolve one), and report what would be validated.
  - Single student: --student-id USER_ID (users_user.id for the student).
  - All students: default when --student-id is not provided.

Usage:
  python manage.py validate_students_target_db --dry-run
  python manage.py validate_students_target_db --dry-run --student-id 12345
  python manage.py validate_students_target_db --student-id 12345
  python manage.py validate_students_target_db
"""

from django.core.management.base import BaseCommand
from django.db import connections

from institute.student_validation_utils import (
    ensure_connection,
    get_student_user_ids,
    validate_one_student,
    check_duplicate_students,
    get_student_data_prepared_for_insert,
    format_student_data_prepared_for_insert,
    STUDENT_RELATED_TABLES,
)

TARGET_ALIAS = 'topteen12-old'
SOURCE_ALIAS = 'topteen12'


class Command(BaseCommand):
    help = (
        'Validate student data in target DB (topteen12-old). Read-only. '
        'Use --dry-run, --student-id ID, or run for all students. No duplicate entries allowed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report student count and what would be validated; do not run full validation.',
        )
        parser.add_argument(
            '--student-id',
            type=int,
            default=None,
            metavar='USER_ID',
            help='Validate a single student by user id (users_user.id). If omitted, validate all students.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        student_id = options['student_id']

        self.stdout.write(self.style.SUCCESS(f'Target DB: {TARGET_ALIAS} (read-only)\n'))
        ensure_connection(TARGET_ALIAS, role='target')

        if dry_run and student_id is not None:
            # Show student data prepared for insert (from source DB)
            ensure_connection(SOURCE_ALIAS, role='source')
            conn_src = connections[SOURCE_ALIAS]
            with conn_src.cursor() as cursor:
                data = get_student_data_prepared_for_insert(cursor, student_id)
            self.stdout.write(
                self.style.SUCCESS(
                    f'[DRY-RUN] Student data prepared for insert (from source {SOURCE_ALIAS}, user_id={student_id}):'
                )
            )
            self.stdout.write('')
            for line in format_student_data_prepared_for_insert(data):
                self.stdout.write(line)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('No duplicate student entries should be created on import.'))
            self.stdout.write(self.style.SUCCESS('No changes made to target DB.'))
            return

        conn = connections[TARGET_ALIAS]
        with conn.cursor() as cursor:
            student_ids = get_student_user_ids(cursor, student_id=student_id)

            if student_id is not None and not student_ids:
                self.stdout.write(
                    self.style.ERROR(f'No student found with user id {student_id}. Exiting.')
                )
                return

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[DRY-RUN] Would validate {len(student_ids)} student(s).'
                    )
                )
                self.stdout.write('Tables considered: ' + ', '.join(STUDENT_RELATED_TABLES[:10]) + '...')
                self.stdout.write(self.style.WARNING('No duplicate student entries should be created on import.'))
                self.stdout.write(self.style.SUCCESS('\nNo changes made to target DB.'))
                return

            # Duplicate check (no duplicate student entries should exist)
            dup = check_duplicate_students(cursor)
            if dup['duplicate_emails']:
                self.stdout.write(
                    self.style.ERROR(
                        f"Duplicate students by email: {len(dup['duplicate_emails'])} email(s) used by more than one user."
                    )
                )
                for email, cnt in dup['duplicate_emails'][:20]:
                    self.stdout.write(self.style.ERROR(f"  - {email!r}: {cnt} rows"))
                if len(dup['duplicate_emails']) > 20:
                    self.stdout.write(self.style.ERROR(f"  ... and {len(dup['duplicate_emails']) - 20} more"))
            if dup['duplicate_student_management']:
                self.stdout.write(
                    self.style.ERROR(
                        f"Duplicate StudentManagement: {len(dup['duplicate_student_management'])} (student_id, institute_id) with multiple rows."
                    )
                )
                for sid, iid, cnt in dup['duplicate_student_management'][:20]:
                    self.stdout.write(self.style.ERROR(f"  - student_id={sid} institute_id={iid}: {cnt} rows"))
            if dup['duplicate_emails'] or dup['duplicate_student_management']:
                self.stdout.write(self.style.WARNING("Import must never create duplicate entries; use exists-check or INSERT IGNORE.\n"))

            # Full validation
            if student_id is not None:
                self.stdout.write(f'Validating 1 student: user_id={student_id}\n')
            else:
                self.stdout.write(f'Validating {len(student_ids)} student(s)\n')

            errors_count = 0
            for uid in student_ids:
                result = validate_one_student(cursor, uid)
                self._print_result(result)
                if result['issues']:
                    errors_count += 1

            # When validating a single student (no dry-run), show full student data from target DB
            if student_id is not None and not dry_run and student_ids:
                data = get_student_data_prepared_for_insert(cursor, student_id)
                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS(f'Student data in target DB ({TARGET_ALIAS}, user_id={student_id}):')
                )
                self.stdout.write('')
                for line in format_student_data_prepared_for_insert(data):
                    self.stdout.write(line)
                self.stdout.write('')

            self.stdout.write(
                self.style.SUCCESS(
                    f'Done. Validated {len(student_ids)} student(s); {errors_count} with issue(s).'
                )
            )
            self.stdout.write('Target DB was not modified (read-only).')

    def _print_result(self, result):
        line = (
            f"  user_id={result['user_id']} email={result['email'] or '-'} "
            f"name={result['name'] or '-'} class={result['class'] or '-'} "
            f"school={result['is_school_student']}"
        )
        if result['issues']:
            self.stdout.write(self.style.ERROR(line))
            for issue in result['issues']:
                self.stdout.write(self.style.ERROR(f"    - {issue}"))
        else:
            self.stdout.write(self.style.SUCCESS(line))
        counts = result.get('counts') or {}
        if counts:
            parts = [f"{t}:{c}" for t, c in sorted(counts.items()) if c]
            if parts:
                self.stdout.write(f"    counts: {', '.join(parts)}")
