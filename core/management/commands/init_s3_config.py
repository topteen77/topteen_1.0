"""
Management command to initialize S3 upload configuration
"""
from django.core.management.base import BaseCommand
from core.models import Configuration


class Command(BaseCommand):
    help = 'Initialize S3 upload configuration key'

    def handle(self, *args, **options):
        """Create S3_UPLOAD_ENABLED configuration if it doesn't exist"""
        config, created = Configuration.objects.get_or_create(
            key='S3_UPLOAD_ENABLED',
            defaults={
                'value': 'false',
                'editable': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    'Successfully created S3_UPLOAD_ENABLED configuration (default: false)'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'S3_UPLOAD_ENABLED configuration already exists with value: {config.value}'
                )
            )
