#!/usr/bin/env python3
"""
Media <-> S3 deduplication helper.

Purpose
-------
When USE_S3_FOR_MEDIA is on, uploaded media lives in the S3 bucket. The local
`media/` folder is often a leftover copy of the same objects, wasting disk and
duplicating what is already on S3.

This tool compares the local media folder against the S3 bucket and classifies
every local file:

  SAFE_DUPLICATE   local file whose S3 key exists AND size matches  -> can delete
  SIZE_MISMATCH    S3 key exists but size differs                   -> KEEP (review)
  MISSING_ON_S3    no matching S3 key                               -> KEEP (data!)

It is DRY-RUN by default and prints/writes a report. Nothing is deleted unless
you pass --delete, and even then ONLY files classified SAFE_DUPLICATE are removed.

Usage
-----
  # dry run (default): just report, delete nothing
  python3 deploy/scripts/media_s3_dedupe.py

  # optional stronger check: also compare MD5 for single-part objects
  python3 deploy/scripts/media_s3_dedupe.py --verify-md5

  # actually delete only the confirmed safe duplicates
  python3 deploy/scripts/media_s3_dedupe.py --delete

Credentials/config are read from the project .env (same defaults as settings.py),
and can be overridden with env vars or CLI flags.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

# --- locate project root (two levels up from this script: deploy/scripts/..) ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def load_env(env_path: Path) -> dict:
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


def main() -> int:
    ap = argparse.ArgumentParser(description="Dedupe local media against S3 (dry-run by default).")
    ap.add_argument("--media-dir", default=str(PROJECT_ROOT / "media"), help="Local media folder.")
    ap.add_argument("--prefix", default=None, help="S3 key prefix (default from S3_MEDIA_LOCATION or 'media').")
    ap.add_argument("--bucket", default=None, help="S3 bucket (default from env or 'topteenc').")
    ap.add_argument("--region", default=None, help="AWS region (default from env or 'ap-northeast-1').")
    ap.add_argument("--verify-md5", action="store_true", help="Also compare MD5 for single-part S3 objects.")
    ap.add_argument("--delete", action="store_true", help="DELETE confirmed SAFE_DUPLICATE files. Off by default.")
    ap.add_argument("--report-dir", default=str(SCRIPT_DIR / "media_dedupe_reports"), help="Where to write report files.")
    args = ap.parse_args()

    env = load_env(PROJECT_ROOT / ".env")

    def cfg(name, default):
        return os.environ.get(name) or env.get(name) or default

    bucket = args.bucket or cfg("AWS_STORAGE_BUCKET_NAME", "topteenc")
    region = args.region or cfg("AWS_REGION", "ap-northeast-1")
    prefix = args.prefix or cfg("S3_MEDIA_LOCATION", "media")
    prefix = prefix.strip("/") + "/"
    access_key = cfg("AWS_ACCESS_KEY_ID", "")
    secret_key = cfg("AWS_SECRET_ACCESS_KEY", "")

    media_dir = Path(args.media_dir).resolve()
    if not media_dir.is_dir():
        print(f"ERROR: media dir not found: {media_dir}")
        return 2

    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        print("ERROR: boto3 not installed. `pip install boto3`.")
        return 2

    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key or None,
        aws_secret_access_key=secret_key or None,
        region_name=region,
        config=Config(connect_timeout=10, read_timeout=30, retries={"max_attempts": 3}),
    )

    print(f"Bucket    : {bucket}")
    print(f"Region    : {region}")
    print(f"S3 prefix : {prefix}")
    print(f"Media dir : {media_dir}")
    print(f"Mode      : {'DELETE safe duplicates' if args.delete else 'DRY-RUN (no deletion)'}")
    print("-" * 60)

    # 1) List all S3 objects under prefix -> {key: (size, etag)}
    print("Listing S3 objects ...", flush=True)
    s3_objs: dict[str, tuple[int, str]] = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for o in page.get("Contents", []) or []:
            s3_objs[o["Key"]] = (o["Size"], o.get("ETag", "").strip('"'))
    print(f"  S3 objects under '{prefix}': {len(s3_objs)}")

    # 2) Walk local media, classify
    safe, mismatch, missing = [], [], []
    total_local = 0
    for root, _dirs, files in os.walk(media_dir):
        for fname in files:
            fpath = Path(root) / fname
            try:
                lsize = fpath.stat().st_size
            except OSError:
                continue
            total_local += 1
            rel = fpath.relative_to(media_dir).as_posix()
            key = prefix + rel
            if key not in s3_objs:
                missing.append((rel, lsize))
                continue
            ssize, setag = s3_objs[key]
            if lsize != ssize:
                mismatch.append((rel, lsize, ssize))
                continue
            if args.verify_md5 and "-" not in setag:  # skip multipart etags
                md5 = hashlib.md5()
                with open(fpath, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        md5.update(chunk)
                if md5.hexdigest() != setag:
                    mismatch.append((rel, lsize, ssize))
                    continue
            safe.append((rel, lsize))

    def total_bytes(items, idx=1):
        return sum(i[idx] for i in items)

    print("-" * 60)
    print(f"Local files scanned : {total_local}")
    print(f"SAFE_DUPLICATE      : {len(safe):>7}  ({human(total_bytes(safe))})   <- reclaimable")
    print(f"SIZE_MISMATCH       : {len(mismatch):>7}  (kept)")
    print(f"MISSING_ON_S3       : {len(missing):>7}  ({human(total_bytes(missing))})  (kept - not on S3!)")
    print("-" * 60)

    # per top-level folder breakdown of what's reclaimable vs kept-local-only
    def top(rel):
        return rel.split("/", 1)[0] if "/" in rel else "(root)"

    folders: dict[str, dict] = {}
    for rel, sz in safe:
        f = folders.setdefault(top(rel), {"safe_n": 0, "safe_b": 0, "miss_n": 0, "miss_b": 0})
        f["safe_n"] += 1
        f["safe_b"] += sz
    for rel, sz in missing:
        f = folders.setdefault(top(rel), {"safe_n": 0, "safe_b": 0, "miss_n": 0, "miss_b": 0})
        f["miss_n"] += 1
        f["miss_b"] += sz

    print("Per top-level folder (reclaimable / local-only-kept):")
    for name in sorted(folders):
        f = folders[name]
        print(f"  {name:<20} dup={f['safe_n']:>6} ({human(f['safe_b']):>9})   "
              f"local-only={f['miss_n']:>6} ({human(f['miss_b']):>9})")
    print("-" * 60)

    # 3) write reports
    rdir = Path(args.report_dir)
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "safe_duplicates.txt").write_text("\n".join(r for r, _ in safe) + ("\n" if safe else ""))
    (rdir / "size_mismatch.txt").write_text(
        "\n".join(f"{r}\tlocal={ls}\ts3={ss}" for r, ls, ss in mismatch) + ("\n" if mismatch else "")
    )
    (rdir / "missing_on_s3.txt").write_text("\n".join(r for r, _ in missing) + ("\n" if missing else ""))
    print(f"Reports written to: {rdir}")
    print("  safe_duplicates.txt  (would be deleted with --delete)")
    print("  size_mismatch.txt    (kept, review manually)")
    print("  missing_on_s3.txt    (kept, NOT on S3 - would be data loss)")

    # 4) delete only if asked, only SAFE_DUPLICATE
    if args.delete:
        print("-" * 60)
        print(f"Deleting {len(safe)} SAFE_DUPLICATE files ...", flush=True)
        deleted = 0
        freed = 0
        for rel, sz in safe:
            p = media_dir / rel
            try:
                p.unlink()
                deleted += 1
                freed += sz
            except OSError as e:
                print(f"  WARN could not delete {rel}: {e}")
        # remove now-empty directories
        for root, dirs, files in os.walk(media_dir, topdown=False):
            rp = Path(root)
            if rp == media_dir:
                continue
            try:
                if not any(rp.iterdir()):
                    rp.rmdir()
            except OSError:
                pass
        print(f"Deleted {deleted} files, freed {human(freed)}.")
        print("Local-only and size-mismatch files were preserved.")
    else:
        print("-" * 60)
        print("DRY-RUN complete. Re-run with --delete to remove SAFE_DUPLICATE files.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
