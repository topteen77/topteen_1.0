"""
Management command to initialize psychometric test site settings in Configuration.
These settings can then be managed via Django Admin > Configuration.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Configuration


PSYCHOMETRIC_SETTINGS = [
    {
        'key': 'ENABLE_ANSWERING_CAREFULLY_WIDGET',
        'value': str(getattr(settings, 'ENABLE_ANSWERING_CAREFULLY_WIDGET', True)).lower(),
        'description': 'Show "Answering Carefully" / "Rushing Through" widget on test pages (true/false)',
    },
    {
        'key': 'ENABLE_AUTO_FORWARD',
        'value': str(getattr(settings, 'ENABLE_AUTO_FORWARD', True)).lower(),
        'description': 'Auto-advance to next question when user selects an answer (true/false)',
    },
]


class Command(BaseCommand):
    help = 'Initialize psychometric test site settings in Configuration (manageable via Admin)'

    def handle(self, *args, **options):
        for item in PSYCHOMETRIC_SETTINGS:
            config, created = Configuration.objects.get_or_create(
                key=item['key'],
                defaults={
                    'value': item['value'],
                    'editable': True,
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {item['key']} = {item['value']} ({item['description']})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"{item['key']} already exists (value: {config.value})"
                    )
                )
