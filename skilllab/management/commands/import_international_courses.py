from django.core.management.base import BaseCommand

from skilllab.international_courses_data import INTERNATIONAL_COURSES
from skilllab.models import InternationalOnlineCourse


class Command(BaseCommand):
    help = "Import international online courses from international_courses_data.py into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing international online courses before importing",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = InternationalOnlineCourse.objects.complete().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing course(s)."))

        created = 0
        updated = 0
        for priority, course in enumerate(INTERNATIONAL_COURSES):
            obj, was_created = InternationalOnlineCourse.objects.update_or_create(
                title=course["title"],
                institute=course["institute"],
                defaults={
                    "description": course["description"],
                    "url": course["url"],
                    "subject": course["subject"],
                    "priority": priority,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {created} created, {updated} updated "
                f"({InternationalOnlineCourse.objects.count()} total active)."
            )
        )
