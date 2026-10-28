from django.core.management.base import BaseCommand

from core.tasks import send_daily_failure_alert


class Command(BaseCommand):
    help = "Send one daily failure alert immediately (AI, email, payment, and server errors)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Send even when ENVIRONMENT is not production, and even if today's alert was already sent.",
        )
        parser.add_argument(
            "--to",
            type=str,
            default="",
            help="Optional recipient override (single or comma-separated emails).",
        )

    def handle(self, *args, **options):
        override_to = (options.get("to") or "").strip() or None
        result = send_daily_failure_alert(
            force_send=bool(options.get("force")),
            override_recipients=override_to,
        )
        self.stdout.write(self.style.SUCCESS("Daily failure alert executed: {}".format(result)))
