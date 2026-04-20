"""One-time fix: resume section tables were latin1 while UserResume is utf8mb4.

Unicode in experience bullets (e.g. ₹) caused MySQL error 1366 on INSERT.
Run: python manage.py fix_resume_section_tables_utf8mb4
"""

from django.core.management.base import BaseCommand
from django.db import connection


TABLES = (
    "users_userresumeactivity",
    "users_userresumecertificate",
    "users_userresumeinternship",
    "users_userresumeskill",
    "users_userresumevolunteerinvolvement",
)


class Command(BaseCommand):
    help = (
        "Convert users_userresume* section tables to utf8mb4_unicode_ci "
        "(matches users_userresume)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print ALTER statements only.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        for table in TABLES:
            sql = (
                f"ALTER TABLE `{table}` "
                "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            if dry:
                self.stdout.write(sql)
                continue
            with connection.cursor() as cursor:
                cursor.execute(sql)
            self.stdout.write(self.style.SUCCESS(f"Converted {table}"))
        if dry:
            self.stdout.write(self.style.WARNING("Dry run: no changes applied."))
