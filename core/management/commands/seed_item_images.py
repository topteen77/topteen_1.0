from __future__ import annotations

from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import ExtracurricularActivity, VocationalCourse


class Command(BaseCommand):
    help = "Assign the same default image to all extracurricular activities and vocational courses (for initial setup)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--image",
            default="/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/demo-topteens/static/images_new/blogs/blog-sample3.png",
            help="Absolute path to a PNG/JPG image to assign",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing images too (default: only fill missing images)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        image_path = Path(options["image"])
        overwrite = bool(options["overwrite"])
        if not image_path.exists():
            raise SystemExit(f"Image not found: {image_path}")

        img_bytes = image_path.read_bytes()

        def assign(qs, field_name: str):
            updated = 0
            for obj in qs:
                field = getattr(obj, field_name)
                if field and not overwrite:
                    continue
                cf = ContentFile(img_bytes)
                field.save(image_path.name, cf, save=True)
                updated += 1
            return updated

        ex = assign(ExtracurricularActivity._base_manager.all(), "image")
        vc = assign(VocationalCourse._base_manager.all(), "image")

        self.stdout.write(self.style.SUCCESS(
            f"Seeded item images. Extracurricular activities updated: {ex}, Vocational courses updated: {vc}"
        ))


