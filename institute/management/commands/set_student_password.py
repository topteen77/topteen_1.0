"""
Set a student's password in the default DB (the one used for login).

Useful after importing students from origin: imported users keep the source
hashed password, so a known password like 12345 will not work until set here.

Usage:
  python manage.py set_student_password --email shivagujral03@gmail.com --password 12345
  python manage.py set_student_password --email student@example.com --password 12345 --student-only
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.choices import UserType


class Command(BaseCommand):
    help = (
        'Set password for a user by email in the default DB. '
        'Use --student-only to restrict to student accounts.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='User email')
        parser.add_argument('--password', required=True, help='New password (plain text)')
        parser.add_argument(
            '--student-only',
            action='store_true',
            help='Only update if user is a student (user_type=STUDENT).',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        email = (options['email'] or '').strip()
        password = options['password']
        student_only = options['student_only']

        if not email:
            self.stderr.write(self.style.ERROR('--email is required and must be non-empty.'))
            return

        qs = User.objects.filter(email__iexact=email)
        if student_only:
            qs = qs.filter(user_type=UserType.STUDENT)

        user = qs.first()
        if not user:
            msg = f'No user found with email {email!r}'
            if student_only:
                msg += ' (student only)'
            self.stderr.write(self.style.ERROR(msg))
            return

        user.set_password(password)
        user.save(update_fields=['password'])
        self.stdout.write(
            self.style.SUCCESS(f'Password updated for {user.email} (id={user.id}). You can now log in with the new password.')
        )
