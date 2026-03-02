"""
Validate student data in the ORIGIN database (topteen12). Read-only; no data is changed.

Ensures no duplicate student entries: checks duplicate emails and duplicate
(institute, student) in StudentManagement. Import to target must never create duplicates.

Modes:
  - Dry-run: only connect, count students (or resolve one), and report what would be validated.
  - Single student: --student-id USER_ID (users_user.id for the student).
  - All students: default when --student-id is not provided.

Usage:
  python manage.py validate_students_origin_db --dry-run
  python manage.py validate_students_origin_db --dry-run --student-id 12345
  python manage.py validate_students_origin_db --student-id 12345
  python manage.py validate_students_origin_db
"""

from django.core.management.base import BaseCommand
from django.db import connections

from institute.student_validation_utils import (
    ensure_connection,
    get_student_user_ids,
    validate_one_student,
    check_duplicate_students,
    STUDENT_RELATED_TABLES,
)

ORIGIN_ALIAS = 'topteen12'


class Command(BaseCommand):
    help = (
        'Validate student data in origin DB (topteen12). Read-only. '
        'Use --dry-run, --student-id ID, or run for all students.'
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

        self.stdout.write(self.style.SUCCESS(f'Origin DB: {ORIGIN_ALIAS} (read-only)\n'))
        ensure_connection(ORIGIN_ALIAS, role='source')
        conn = connections[ORIGIN_ALIAS]

        with conn.cursor() as cursor:
            student_ids = get_student_user_ids(cursor, student_id=student_id)

            if student_id is not None and not student_ids:
                self.stdout.write(
                    self.style.ERROR(f'No student found with user id {student_id}. Exiting.')
                )
                return

            if dry_run:
                if student_id is not None:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[DRY-RUN] Would validate 1 student: user_id={student_id}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[DRY-RUN] Would validate {len(student_ids)} student(s).'
                        )
                    )
                self.stdout.write('Tables considered: ' + ', '.join(STUDENT_RELATED_TABLES[:10]) + '...')
                self.stdout.write(self.style.SUCCESS('\nNo changes made to origin DB.'))
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

            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done. Validated {len(student_ids)} student(s); {errors_count} with issue(s).'
                )
            )
            self.stdout.write('Origin DB was not modified (read-only).')

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
