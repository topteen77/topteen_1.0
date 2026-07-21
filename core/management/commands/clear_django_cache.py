from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Clear the default Django cache (Redis/locmem). Use after deploys when needed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm clear (required for non-interactive deploy scripts).",
        )

    def handle(self, *args, **options):
        if not options.get("yes"):
            self.stderr.write("Refusing to clear cache without --yes")
            return
        cache.clear()
        self.stdout.write(self.style.SUCCESS("Django cache cleared."))
