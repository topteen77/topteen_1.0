from django.core.management.base import BaseCommand
from demo_data.demo_dataset import reset_demo_data


class Command(BaseCommand):
    help = "Reset demo data: delete only system-flagged demo data, then recreate the fixed dataset. No actual user data is affected."

    def handle(self, *args, **options):
        self.stdout.write("Resetting demo data...")
        try:
            result = reset_demo_data()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo data reset complete: institute_id={result['institute_id']}, "
                    f"students={len(result['student_user_ids'])}"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            raise
