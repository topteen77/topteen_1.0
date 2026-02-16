from django.core.management.base import BaseCommand
from demo_data.demo_dataset import remove_demo_data


class Command(BaseCommand):
    help = "Remove demo data only: delete all system-flagged demo users/institute and related data. Does not recreate. No actual user data is affected."

    def handle(self, *args, **options):
        self.stdout.write("Removing demo data...")
        try:
            remove_demo_data()
            self.stdout.write(self.style.SUCCESS("Demo data removed successfully."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            raise
