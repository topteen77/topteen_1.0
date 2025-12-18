from __future__ import annotations

from pathlib import Path

from django.core.files.base import File
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import ExtracurricularActivityCategory, VocationalCourseCategory


class Command(BaseCommand):
    help = "Assign the same default image to all extracurricular/vocational categories (for initial setup)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--image",
            default="/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/demo-topteens/static/images_new/blogs/blog-sample3.png",
            help="Absolute path to a PNG/JPG image to assign",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        image_path = Path(options["image"])
        if not image_path.exists():
            raise SystemExit(f"Image not found: {image_path}")

        # Read once; then save into each model field
        with image_path.open("rb") as f:
            img_bytes = f.read()

        def assign_all(qs, field_name: str):
            updated = 0
            for obj in qs:
                # Only assign if empty
                if getattr(obj, field_name):
                    continue
                from django.core.files.base import ContentFile
                cf = ContentFile(img_bytes)
                getattr(obj, field_name).save(image_path.name, cf, save=True)
                updated += 1
            return updated

        ex_updated = assign_all(ExtracurricularActivityCategory._base_manager.all(), "image")
        voc_updated = assign_all(VocationalCourseCategory._base_manager.all(), "image")

        self.stdout.write(self.style.SUCCESS(f"Seeded images. Extracurricular categories updated: {ex_updated}, Vocational categories updated: {voc_updated}"))


