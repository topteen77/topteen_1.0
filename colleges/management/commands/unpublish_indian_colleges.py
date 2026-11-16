from django.core.management.base import BaseCommand

from colleges.models import College
from core import choices


class Command(BaseCommand):
    help = (
        "Unpublish local Indian colleges. KaunsaCollege is the public source for those institutes."
    )

    def handle(self, *args, **options):
        updated = College.indian_records().update(
            publish_status=choices.PublishStatus.DRAFT,
            object_status=choices.ObjectStatus.INACTIVE,
        )
        self.stdout.write(self.style.SUCCESS(f"Unpublished {updated} Indian college(s)."))
