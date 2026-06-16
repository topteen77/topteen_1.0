import os

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from skilllab.models import InternationalOnlineCourse


class Command(BaseCommand):
    help = "Upload international course images/logos from local MEDIA_ROOT to S3"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be uploaded without making changes",
        )

    def _s3_client(self):
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    def _s3_key(self, name):
        location = getattr(settings, "S3_MEDIA_LOCATION", "media")
        return f"{location.rstrip('/')}/{name}" if location else name

    def _on_s3(self, s3_client, name):
        try:
            s3_client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=self._s3_key(name))
            return True
        except ClientError:
            return False

    def _upload_field(self, course, field_name, s3_client, dry_run=False):
        field = getattr(course, field_name)
        if not field or not field.name:
            return "skipped"

        name = field.name
        if self._on_s3(s3_client, name):
            return "already_on_s3"

        local_path = os.path.join(settings.MEDIA_ROOT, name)
        if not os.path.exists(local_path):
            return "missing_local"

        if dry_run:
            return "would_upload"

        with open(local_path, "rb") as handle:
            field.save(os.path.basename(name), File(handle), save=False)
        course.save(update_fields=[field_name, "modified"])

        if self._on_s3(s3_client, course.pk and getattr(course, field_name).name or name):
            try:
                os.remove(local_path)
            except OSError:
                pass
            return "uploaded"

        return "upload_failed"

    def handle(self, *args, **options):
        if not getattr(settings, "USE_S3_FOR_MEDIA", False):
            self.stdout.write(self.style.WARNING("USE_S3_FOR_MEDIA is disabled; nothing to do."))
            return

        dry_run = options["dry_run"]
        s3_client = self._s3_client()
        stats = {"uploaded": 0, "already_on_s3": 0, "missing_local": 0, "skipped": 0, "failed": 0}

        for course in InternationalOnlineCourse.objects.complete().iterator():
            for field_name in ("image", "logo"):
                result = self._upload_field(course, field_name, s3_client, dry_run=dry_run)
                if result not in stats:
                    result = "failed"
                stats[result] += 1
                label = f"pk={course.pk} {field_name}: {result}"
                if result == "uploaded":
                    self.stdout.write(self.style.SUCCESS(label))
                elif result in ("missing_local", "upload_failed", "failed"):
                    self.stdout.write(self.style.WARNING(label))
                elif dry_run and result == "would_upload":
                    self.stdout.write(label)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done{' (dry run)' if dry_run else ''}: "
                f"uploaded={stats['uploaded']}, already_on_s3={stats['already_on_s3']}, "
                f"missing_local={stats['missing_local']}, skipped={stats['skipped']}, failed={stats['failed']}"
            )
        )
