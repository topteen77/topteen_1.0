"""
Management command to initialize psychometric test site settings in Configuration.
These settings can then be managed via Django Admin > Configuration.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from core.choices import (
    CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY,
    CLASS10_APTITUDE_STREAM_MODE_COMBINED,
)
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


CLASS10_APTITUDE_REPORT_SETTINGS = [
    {
        'key': CLASS10_APTITUDE_STREAM_DISPLAY_MODE_KEY,
        'value': CLASS10_APTITUDE_STREAM_MODE_COMBINED,
        'description': 'Class 10 aptitude report stream recommendation display mode',
    },
]


class Command(BaseCommand):
    help = 'Initialize psychometric test site settings in Configuration (manageable via Admin)'

    def handle(self, *args, **options):
        for item in PSYCHOMETRIC_SETTINGS + CLASS10_APTITUDE_REPORT_SETTINGS:
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
