"""
Upload images from a directory into EntranceTestPrepCategory.image by matching
filename stem (without extension) to category slug.

Usage:
  python manage.py upload_entrance_test_prep_images [--images-dir PATH] [--dry-run]

Images dir default: topteenhtml/html/Entrance Exam/images/entrance-exam
(relative to project root or absolute). Only PNG/JPG/JPEG/WEBP/GIF are processed.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from core.models import EntranceTestPrepCategory


# Filename stem (lowercase) -> category slug. Use when stem doesn't match any category slug.
STEM_TO_SLUG_OVERRIDE = {
    "scolarships-and-fellowships": "scholarships-and-fellowships",  # typo in image name
    "defence-icon": "defence-exams",
    "defence-icon-1": "defence-exams",
    "defence-icon-2": "defence-exams",
    "defence-icon-3": "defence-exams",
    "defence-icon-4": "defence-exams",
    "defence-icon-5": "defence-exams",
    "defence-hero-banner": "defence-exams",
    "govt-job-icon": "government-jobs",
    "govt-school-exam": "government-jobs",  # or a dedicated category if exists
    "india-olympiad": "olympiads",
    "polytech-exam": "engineering",  # or polytechnic if exists
    "school-adm-test": "education",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class Command(BaseCommand):
    help = (
        "Read images from a directory and assign each to the EntranceTestPrepCategory "
        "whose slug matches the filename stem (e.g. engineering.png -> category slug 'engineering')."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--images-dir",
            default="/home/itpc6/Public/django/git-repo/7nov/topteenhtml/html/Entrance Exam/images/entrance-exam",
            help=(
                "Directory containing images (e.g. entrance-exam folder). "
                "Default: topteenhtml/html/Entrance Exam/images/entrance-exam (adjust in code if needed)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be assigned; do not save.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Update category image even if it already has one. Default: skip categories that already have an image.",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        images_dir = Path(options.get("images_dir") or "").resolve()
        if not images_dir:
            images_dir = Path(settings.BASE_DIR).parent / "topteenhtml" / "html" / "Entrance Exam" / "images" / "entrance-exam"

        if not images_dir.is_dir():
            self.stderr.write(self.style.ERROR(f"Images directory not found: {images_dir}"))
            return

        dry_run = options.get("dry_run", False)
        overwrite = options.get("overwrite", False)

        # Build slug -> category (first match; categories have unique slugs)
        slug_to_category = {}
        for cat in EntranceTestPrepCategory._base_manager.all():
            if cat.slug:
                slug_to_category[cat.slug.lower()] = cat

        assigned = 0
        skipped_no_match = []
        skipped_has_image = 0

        for path in sorted(images_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            stem = path.stem
            stem_norm = stem.lower().strip()
            stem_norm = re.sub(r"\s+", "-", stem_norm)

            slug_candidate = STEM_TO_SLUG_OVERRIDE.get(stem_norm) or stem_norm
            category = slug_to_category.get(slug_candidate)

            if not category:
                skipped_no_match.append(f"{path.name} (tried slug: {slug_candidate})")
                continue

            if not overwrite and category.image:
                skipped_has_image += 1
                continue

            if dry_run:
                self.stdout.write(f"[dry-run] Would assign {path.name} -> category id={category.id} ({category.name})")
                assigned += 1
                continue

            with path.open("rb") as f:
                category.image.save(path.name, File(f), save=True)
            assigned += 1
            self.stdout.write(f"Assigned {path.name} -> {category.name} (id={category.id})")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Assigned: {assigned}"))
        if skipped_has_image:
            self.stdout.write(f"Skipped (already have image): {skipped_has_image}")
        if skipped_no_match:
            self.stdout.write(self.style.WARNING(f"No matching category for {len(skipped_no_match)} image(s):"))
            for s in skipped_no_match[:30]:
                self.stdout.write(f"  {s}")
            if len(skipped_no_match) > 30:
                self.stdout.write(f"  ... and {len(skipped_no_match) - 30} more")
