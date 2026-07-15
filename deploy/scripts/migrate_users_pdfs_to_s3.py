#!/usr/bin/env python3
"""
One-time migration: move existing on-disk users_pdfs into S3, then remove local copies.

Files are UPLOADED through the application's own storage backend (default_storage) so
the S3 key prefix, ACL and content-type match exactly what the app produces at runtime
(key: <media>/users_pdfs/<...>).

Existence/size are checked with RAW boto3 (head_object / list_objects_v2) because
default_storage.exists() is unreliable with this S3 configuration (it can return False
for objects that actually exist). A local file is deleted ONLY after boto3 confirms the
object is present on S3 with a matching byte size.

Classification per local file:
  UPLOAD          not on S3 yet             -> upload, verify (boto3), then delete local
  ALREADY_ON_S3   on S3 with same size      -> delete local (duplicate)
  SIZE_MISMATCH   on S3 with different size  -> SKIP (kept local for manual review)

DRY-RUN by default. Pass --apply to actually upload + delete.

Usage:
  python3 deploy/scripts/migrate_users_pdfs_to_s3.py            # dry-run report
  python3 deploy/scripts/migrate_users_pdfs_to_s3.py --apply    # do it
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topteens.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.files import File  # noqa: E402
from django.core.files.storage import default_storage  # noqa: E402

import boto3  # noqa: E402
from botocore.config import Config  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}TB"


def make_s3():
    return boto3.client(
        "s3",
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", "") or None,
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", "") or None,
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None) or getattr(settings, "AWS_REGION", "ap-northeast-1"),
        config=Config(connect_timeout=10, read_timeout=120, retries={"max_attempts": 3}),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local-media", default=str(ROOT / "media"), help="Local media root that physically holds the files.")
    ap.add_argument("--subdir", default="users_pdfs", help="Subfolder under media to migrate.")
    ap.add_argument("--apply", action="store_true", help="Actually upload + delete. Off by default (dry-run).")
    ap.add_argument("--progress-every", type=int, default=50)
    args = ap.parse_args()

    base = Path(args.local_media) / args.subdir
    local_media = Path(args.local_media)
    if not base.is_dir():
        print(f"Nothing to do: {base} does not exist.")
        return 0

    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "topteenc")
    s3_prefix = (getattr(settings, "AWS_LOCATION", "media") or "media").strip("/")
    s3 = make_s3()

    print("=" * 64)
    print("users_pdfs -> S3 migration")
    print(f"Local source : {base}")
    print(f"S3 target    : s3://{bucket}/{s3_prefix}/{args.subdir}/")
    print(f"Mode         : {'APPLY (upload + delete)' if args.apply else 'DRY-RUN (no changes)'}")
    print("=" * 64)

    # Ground-truth existing S3 objects (raw boto3, reliable) -> {key: size}
    print("Listing existing S3 objects ...", flush=True)
    s3map: dict[str, int] = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{s3_prefix}/{args.subdir}/"):
        for o in page.get("Contents", []) or []:
            s3map[o["Key"]] = o["Size"]
    print(f"  existing S3 objects under {s3_prefix}/{args.subdir}/: {len(s3map)}")

    files = [p for p in base.rglob("*") if p.is_file()]
    total = len(files)
    print(f"Local files to process: {total}")

    up_n = up_b = dup_n = dup_b = mm_n = fail_n = 0
    deleted_n = deleted_b = 0

    def verify_on_s3(key: str, expected: int) -> bool:
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            return head["ContentLength"] == expected
        except ClientError:
            return False

    for i, fpath in enumerate(files, 1):
        try:
            lsize = fpath.stat().st_size
        except OSError:
            continue
        name = fpath.relative_to(local_media).as_posix()   # users_pdfs/54/foo.pdf
        key = f"{s3_prefix}/{name}"                          # media/users_pdfs/54/foo.pdf

        already = key in s3map
        if already and s3map[key] != lsize:
            mm_n += 1
            continue

        if not already:
            up_n += 1
            up_b += lsize
            if args.apply:
                try:
                    with open(fpath, "rb") as fh:
                        default_storage.save(name, File(fh))
                except Exception as e:
                    print(f"  WARN upload failed, keeping local: {name}: {e}")
                    fail_n += 1
                    continue
                if not verify_on_s3(key, lsize):
                    print(f"  WARN post-upload verify failed, keeping local: {name}")
                    fail_n += 1
                    continue
                s3map[key] = lsize
        else:
            dup_n += 1
            dup_b += lsize

        # safe to delete local: confirmed on S3 with matching size
        if args.apply:
            try:
                fpath.unlink()
                deleted_n += 1
                deleted_b += lsize
            except OSError as e:
                print(f"  WARN could not delete local {name}: {e}")

        if i % args.progress_every == 0:
            print(f"  ... {i}/{total} (uploaded={up_n}, dup={dup_n}, mismatch={mm_n}, deleted={deleted_n}, failed={fail_n})", flush=True)

    if args.apply:
        for root, _dirs, _fn in os.walk(base, topdown=False):
            rp = Path(root)
            try:
                if not any(rp.iterdir()):
                    rp.rmdir()
            except OSError:
                pass

    print("-" * 64)
    print(f"UPLOAD (not on S3)     : {up_n:>6}  ({human(up_b)})")
    print(f"ALREADY_ON_S3 (dup)    : {dup_n:>6}  ({human(dup_b)})")
    print(f"SIZE_MISMATCH (kept)   : {mm_n:>6}")
    print(f"FAILED (kept local)    : {fail_n:>6}")
    print(f"LOCAL DELETED          : {deleted_n:>6}  ({human(deleted_b)})")
    print("-" * 64)
    if not args.apply:
        print("DRY-RUN only. Re-run with --apply to upload missing files and delete local copies.")
    else:
        print("Done. Future report PDFs are written straight to S3 by the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
