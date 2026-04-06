"""
Upload local case study PDFs to S3 and attach them to a counselor Part.

Example:
  python manage.py upload_case_studies_s3 --part-id 99

Expects files named "CS 1.pdf" … "CS 100.pdf" (or cs1.pdf) under --source-dir.
Objects are stored as counselor_case_studies/part_<id>/cs1.pdf … cs100.pdf
so Part.case_study_folder_url + relative pdf_url resolves cleanly.

Requires AWS credentials (env / .env) and S3 PutObject permission.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from counselor.models import CaseStudy, Part


def _s3_public_base_url() -> str:
    base = (getattr(settings, "S3_BUCKET_BASE_URL", None) or "").strip()
    if base:
        return base.rstrip("/") + "/"
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    region = getattr(settings, "AWS_REGION", "ap-northeast-1")
    return f"https://{bucket}.s3.{region}.amazonaws.com/"


def _local_pdf_for_index(source_dir: Path, index: int) -> Path | None:
    candidates = [
        source_dir / f"CS {index}.pdf",
        source_dir / f"cs{index}.pdf",
        source_dir / f"CS{index}.pdf",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


class Command(BaseCommand):
    help = "Upload case study PDFs to S3 and create CaseStudy rows for a Part."

    def add_arguments(self, parser):
        parser.add_argument(
            "--part-id",
            type=int,
            required=True,
            help="Counselor Part primary key (e.g. 99).",
        )
        parser.add_argument(
            "--source-dir",
            type=str,
            default="",
            help="Folder containing PDFs (default: <BASE_DIR>/case_studies).",
        )
        parser.add_argument(
            "--from",
            dest="from_n",
            type=int,
            default=1,
            help="First index (default 1).",
        )
        parser.add_argument(
            "--to",
            dest="to_n",
            type=int,
            default=100,
            help="Last index (default 100).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions without uploading or changing the database.",
        )
        parser.add_argument(
            "--no-replace",
            action="store_true",
            help="Do not delete existing CaseStudy rows for this part before creating.",
        )

    def handle(self, *args, **options):
        part_id: int = options["part_id"]
        dry_run: bool = options["dry_run"]
        replace: bool = not options["no_replace"]

        base = Path(settings.BASE_DIR)
        raw_dir = (options["source_dir"] or "").strip()
        if raw_dir:
            source_dir = Path(raw_dir).expanduser()
        else:
            # Path("") is "." — do not use cwd as default
            source_dir = base / "case_studies"
        if not source_dir.is_dir():
            raise CommandError(f"Source directory does not exist: {source_dir}")

        part = Part.objects.filter(pk=part_id).first()
        if not part:
            raise CommandError(f"Part id={part_id} not found.")

        key_prefix = f"counselor_case_studies/part_{part_id}"
        folder_url = f"{_s3_public_base_url().rstrip('/')}/{key_prefix}/"

        access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "") or ""
        secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "") or ""
        region = getattr(settings, "AWS_REGION", "ap-northeast-1")
        bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")

        if not bucket:
            raise CommandError("AWS_STORAGE_BUCKET_NAME is not set.")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no uploads or DB writes."))

        if not dry_run:
            if not access_key or not secret_key:
                raise CommandError(
                    "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set for upload."
                )
            client = boto3.client(
                "s3",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
        else:
            client = None

        from_n = options["from_n"]
        to_n = options["to_n"]
        uploads: list[tuple[int, Path, str]] = []

        for i in range(from_n, to_n + 1):
            local = _local_pdf_for_index(source_dir, i)
            if not local:
                self.stdout.write(self.style.WARNING(f"Missing file for index {i}, skipped."))
                continue
            s3_name = f"cs{i}.pdf"
            s3_key = f"{key_prefix}/{s3_name}"
            uploads.append((i, local, s3_key))

        if not uploads:
            raise CommandError("No PDF files found to upload.")

        for i, local_path, s3_key in uploads:
            self.stdout.write(f"  {local_path.name} -> s3://{bucket}/{s3_key}")
            if dry_run or not client:
                continue
            body = local_path.read_bytes()
            content_type = mimetypes.guess_type(str(local_path))[0] or "application/pdf"
            try:
                client.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=body,
                    ContentType=content_type,
                    ACL="public-read",
                )
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code == "AccessControlListNotSupported":
                    client.put_object(
                        Bucket=bucket,
                        Key=s3_key,
                        Body=body,
                        ContentType=content_type,
                    )
                else:
                    raise CommandError(f"S3 upload failed for {s3_key}: {e}") from e

        self.stdout.write(self.style.SUCCESS(f"Folder URL for Part {part_id}: {folder_url}"))

        if dry_run:
            self.stdout.write(
                f"Would set case_study_folder_url and create {len(uploads)} CaseStudy row(s)."
            )
            return

        part.case_study_folder_url = folder_url
        part.save(update_fields=["case_study_folder_url"])

        if replace:
            deleted, _ = CaseStudy.objects.filter(part_id=part_id).delete()
            if deleted:
                self.stdout.write(f"Removed existing case study rows ({deleted}).")

        CaseStudy.objects.bulk_create(
            [
                CaseStudy(
                    part_id=part_id,
                    title=f"Case study {i}",
                    pdf_url=f"cs{i}.pdf",
                    sort_order=i,
                )
                for i, _, __ in uploads
            ]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Part {part_id}: case_study_folder_url set; {len(uploads)} CaseStudy rows created."
            )
        )
