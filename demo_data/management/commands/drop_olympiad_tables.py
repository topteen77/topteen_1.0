"""
Drop olympiad app tables from the database (use after removing the olympiad app).
Run once on production/staging if those tables exist and you no longer use the app.

  python manage.py drop_olympiad_tables
"""
from django.core.management.base import BaseCommand
from django.db import connection


# Tables in dependency order (children first)
OLYMPIAD_TABLES = [
    'olympiad_olympiadresponse',
    'olympiad_olympiadsession',
    'olympiad_olympiadregistration',
    'olympiad_olympiadexamquestionset',
    'olympiad_olympiadquestion',
    'olympiad_olympiadexam',
]


class Command(BaseCommand):
    help = 'Drop olympiad app tables (run after removing olympiad from INSTALLED_APPS).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt for confirmation.',
        )

    def handle(self, *args, **options):
        if not options['no_input']:
            confirm = input(
                'Drop olympiad tables? This cannot be undone. Type "yes" to continue: '
            )
            if confirm != 'yes':
                self.stdout.write('Aborted.')
                return

        with connection.cursor() as cursor:
            for table in OLYMPIAD_TABLES:
                cursor.execute(
                    "DROP TABLE IF EXISTS %s" % table  # table name is safe (no user input)
                )
                self.stdout.write('Dropped table (if existed): %s' % table)

            # Remove migration history for olympiad so Django does not expect the app
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = 'olympiad'"
            )
            self.stdout.write("Cleared django_migrations entries for app 'olympiad'.")

        self.stdout.write(self.style.SUCCESS('Olympiad tables dropped.'))
