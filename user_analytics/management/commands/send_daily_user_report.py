from django.core.management.base import BaseCommand

from user_analytics.tasks import send_daily_new_user_report


class Command(BaseCommand):
    help = "Send daily new user report email immediately (uses production and WEBADMINEMAIL guards)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force send even when ENVIRONMENT is not production (for testing).",
        )
        parser.add_argument(
            "--to",
            type=str,
            default="",
            help="Optional recipient override (single or comma-separated emails).",
        )

    def handle(self, *args, **options):
        override_to = (options.get("to") or "").strip() or None
        result = send_daily_new_user_report(
            force_send=bool(options.get("force")),
            override_recipients=override_to,
        )
        self.stdout.write(self.style.SUCCESS("Daily user report task executed: {}".format(result)))
