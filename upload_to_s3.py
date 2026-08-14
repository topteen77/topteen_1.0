#!/usr/bin/env python3
"""
Single-file S3 uploader. Reads credentials from project .env.

Usage:
  python upload_to_s3.py /path/to/file.jpg
  python upload_to_s3.py /path/to/file.jpg --folder media/test
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Install deps: pip install boto3 python-dotenv")
    sys.exit(1)


def load_env() -> None:
    if not load_dotenv:
        return
    here = Path(__file__).resolve().parent
    for candidate in (here / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return
    load_dotenv()


def require_env(name: str, default: str | None = None) -> str:
    value = (os.environ.get(name) or default or "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def get_config() -> dict:
    return {
        "access_key": require_env("AWS_ACCESS_KEY_ID"),
        "secret_key": require_env("AWS_SECRET_ACCESS_KEY"),
        "region": require_env("AWS_REGION", "ap-northeast-1"),
        "bucket": require_env("AWS_STORAGE_BUCKET_NAME"),
        "media_location": (os.environ.get("S3_MEDIA_LOCATION") or "media").strip("/"),
        "access_mode": (os.environ.get("S3_MEDIA_ACCESS_MODE") or "presigned").strip().lower(),
        "cloudfront_domain": (os.environ.get("CLOUDFRONT_DOMAIN") or "").strip().strip("/"),
    }


def get_s3_client(cfg: dict):
    return boto3.client(
        "s3",
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        region_name=cfg["region"],
    )


def build_public_url(cfg: dict, s3_key: str) -> str:
    key = s3_key.lstrip("/")
    mode = cfg["access_mode"]
    if mode in ("cloudfront", "public") and cfg["cloudfront_domain"]:
        return f"https://{cfg['cloudfront_domain']}/{key}"
    return f"https://{cfg['bucket']}.s3.{cfg['region']}.amazonaws.com/{key}"


def upload_file(
    local_path: str,
    folder: str | None = None,
    make_public: bool = False,
    bucket: str | None = None,
) -> dict:
    load_env()
    cfg = get_config()
    if bucket:
        cfg["bucket"] = bucket.strip()

    path = Path(local_path).expanduser().resolve()
    if not path.is_file():
        return {"success": False, "error": f"File not found: {path}"}

    if folder is None:
        folder = cfg["media_location"]
    folder = folder.strip("/")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = path.name.replace(" ", "_")
    name, ext = os.path.splitext(safe_name)
    file_name = f"{name}_{timestamp}{ext}"
    s3_key = f"{folder}/{file_name}" if folder else file_name

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    file_size = path.stat().st_size

    extra_args = {"ContentType": content_type}
    if make_public:
        extra_args["ACL"] = "public-read"

    try:
        s3 = get_s3_client(cfg)
        with open(path, "rb") as f:
            s3.put_object(
                Bucket=cfg["bucket"],
                Key=s3_key,
                Body=f,
                **extra_args,
            )

        url = build_public_url(cfg, s3_key)
        if cfg["access_mode"] == "presigned":
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": cfg["bucket"], "Key": s3_key},
                ExpiresIn=3600,
            )

        return {
            "success": True,
            "bucket": cfg["bucket"],
            "region": cfg["region"],
            "s3_key": s3_key,
            "file_size": file_size,
            "content_type": content_type,
            "access_mode": cfg["access_mode"],
            "url": url,
        }

    except NoCredentialsError:
        return {"success": False, "error": "AWS credentials not found"}
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        return {"success": False, "error": f"S3 Error ({code}): {msg}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a file to S3")
    parser.add_argument("file", help="Local file path to upload")
    parser.add_argument(
        "--folder",
        default=None,
        help="S3 folder/prefix (default: S3_MEDIA_LOCATION from env)",
    )
    parser.add_argument(
        "--bucket",
        default=None,
        help="Override AWS_STORAGE_BUCKET_NAME (e.g. indiancolleges)",
    )
    parser.add_argument(
        "--public-acl",
        action="store_true",
        help="Set ACL public-read (often blocked; prefer CloudFront)",
    )
    args = parser.parse_args()

    result = upload_file(
        args.file,
        folder=args.folder,
        make_public=args.public_acl,
        bucket=args.bucket,
    )

    if not result["success"]:
        print("FAILED:", result["error"])
        sys.exit(1)

    print("Upload OK")
    print(f"  bucket : {result['bucket']}")
    print(f"  region : {result['region']}")
    print(f"  key    : {result['s3_key']}")
    print(f"  type   : {result['content_type']}")
    print(f"  size   : {result['file_size']} bytes")
    print(f"  mode   : {result['access_mode']}")
    print(f"  url    : {result['url']}")


if __name__ == "__main__":
    main()
