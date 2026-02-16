from django.core.management.base import BaseCommand
from demo_data.demo_dataset import create_demo_dataset


class Command(BaseCommand):
    help = "Create the fixed demo dataset (institute, students, parent, links, results). Only system-flagged data is created."

    def handle(self, *args, **options):
        self.stdout.write("Creating demo dataset...")
        try:
            result = create_demo_dataset()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo dataset created: institute_id={result['institute_id']}, "
                    f"students={len(result['student_user_ids'])}, parent_id={result['parent_user_id']}"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            raise
