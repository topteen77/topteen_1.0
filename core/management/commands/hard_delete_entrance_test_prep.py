"""
Hard delete all Entrance Test Prep data: sections, exams, and categories.
Uses _base_manager so soft-deleted rows are also removed from the database.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    EntranceTestPrepCategory,
    EntranceTestPrepExam,
    EntranceTestPrepExamSection,
)


class Command(BaseCommand):
    help = "Hard delete all Entrance Test Prep sections, exams, and categories (including soft-deleted)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show counts; do not delete.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        sections = EntranceTestPrepExamSection._base_manager
        exams = EntranceTestPrepExam._base_manager
        categories = EntranceTestPrepCategory._base_manager

        count_sections = sections.count()
        count_exams = exams.count()
        count_categories = categories.count()

        self.stdout.write(
            "Entrance Test Prep counts: sections=%s, exams=%s, categories=%s"
            % (count_sections, count_exams, count_categories)
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes made."))
            return

        if count_sections == 0 and count_exams == 0 and count_categories == 0:
            self.stdout.write("Nothing to delete.")
            return

        with transaction.atomic():
            sections.all().delete()
            self.stdout.write("Deleted %s section(s)." % count_sections)
            exams.all().delete()
            self.stdout.write("Deleted %s exam(s)." % count_exams)
            categories.all().delete()
            self.stdout.write("Deleted %s category(ies)." % count_categories)

        self.stdout.write(self.style.SUCCESS("Hard delete complete."))
