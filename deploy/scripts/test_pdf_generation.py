#!/usr/bin/env python3
"""
Baseline / regression test for Class-10 combined-report PDF generation.

It exercises the REAL endpoint (app.views.class10_report_download_pdf) through
Django's test client for two cases:

  EXISTING user : a real user that already has test1/test2/test3 Results.
                  This just regenerates their own report (harmless).

  NEW user      : creates a fresh user, clones complete test data into it,
                  generates the report, then ROLLS BACK the DB transaction and
                  deletes any files it created -> no DB pollution, no leftovers.

Use it before AND after switching PDF storage to S3 to prove nothing regressed.

Usage:
  python3 deploy/scripts/test_pdf_generation.py
  python3 deploy/scripts/test_pdf_generation.py --existing-user-id 54 --source-user-id 54
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topteens.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.files.storage import default_storage  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402

from app.models import Results, TestCompletion  # noqa: E402
from core.utils import user_pdf_key  # noqa: E402

try:
    from app.graph_media_utils import graph_images_directory
except Exception:  # pragma: no cover
    graph_images_directory = None

for _h in ("testserver",):
    if _h not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append(_h)

User = get_user_model()
URL = "/psychometric/web/combined_report/{uid}/download-pdf/"


def pdf_dir(uid) -> Path:
    return Path(settings.MEDIA_ROOT) / "users_pdfs" / str(uid)


def graph_dir() -> Path:
    if graph_images_directory:
        try:
            return Path(graph_images_directory())
        except Exception:
            pass
    return Path(settings.MEDIA_ROOT) / "graph_images"


def snapshot(d: Path) -> set[str]:
    return {str(p) for p in d.glob("*")} if d.exists() else set()


def storage_pdfs(uid) -> list[str]:
    """PDF filenames stored under users_pdfs/<uid> in the active storage (S3 or local)."""
    try:
        _dirs, files = default_storage.listdir(f"users_pdfs/{uid}")
        return sorted(f for f in files if f.lower().endswith(".pdf"))
    except Exception:
        return []


def storage_delete_user_pdfs(uid) -> None:
    for f in storage_pdfs(uid):
        try:
            default_storage.delete(f"users_pdfs/{uid}/{f}")
        except Exception:
            pass


def call_report(uid) -> tuple[int, str, int, bytes]:
    c = Client()
    c.force_login(User.objects.get(id=uid))
    r = c.get(URL.format(uid=uid))
    ct = r.headers.get("Content-Type", "") if hasattr(r, "headers") else r.get("Content-Type", "")
    body = r.content
    return r.status_code, ct, len(body), body


def is_pdf_ok(status: int, ct: str, size: int, body: bytes) -> bool:
    return (
        status == 200
        and "application/pdf" in (ct or "")
        and size > 1000
        and body[:5] == b"%PDF-"
    )


def test_existing(uid: int) -> bool:
    print(f"\n[EXISTING USER {uid}] generating class report ...")
    status, ct, size, body = call_report(uid)
    valid_pdf = is_pdf_ok(status, ct, size, body)
    stored = storage_pdfs(uid)
    in_storage = len(stored) > 0
    ok = valid_pdf and in_storage
    print(f"  status={status} content_type={ct!r} bytes={size}")
    print(f"  valid_pdf={valid_pdf}  saved_to_S3={in_storage}  storage_files={stored}")
    if stored:
        print(f"  media link (proxy)  = {default_storage.url(user_pdf_key(uid, stored[-1]))}")
    if not valid_pdf:
        print(f"  RESPONSE (first 400 chars): {body[:400]!r}")
    print(f"  -> {'PASS' if ok else 'FAIL'}")
    return ok


def test_new(source_uid: int) -> bool:
    email = f"pdftest+{int(time.time())}@example.com"
    print(f"\n[NEW USER] creating {email}, cloning data from user {source_uid} ...")
    g_before = snapshot(graph_dir())
    created_uid = None
    ok = False

    class _Rollback(Exception):
        pass

    try:
        with transaction.atomic():
            new = User.objects.create_user(email=email, name="PDF Test User", password="Test@12345")
            created_uid = new.id
            src = Results.objects.filter(user_id=source_uid, test_paper__in=["test1", "test2", "test3"])
            cloned = 0
            for rr in src:
                Results.objects.create(
                    user=new,
                    test_paper=rr.test_paper,
                    scores=rr.scores,
                    results=rr.results,
                    selected_answers=rr.selected_answers,
                )
                cloned += 1
            TestCompletion.objects.create(
                user=new,
                test1_complete=True, test2_complete=True, test3_complete=True,
                numerical_complete=True, verbal_complete=True, logical_complete=True,
                emotional_complete=True, machanical_complete=True, language_complete=True,
                spatial_complete=True,
            )
            print(f"  new_user_id={created_uid} cloned_results={cloned}")

            status, ct, size, body = call_report(created_uid)
            valid_pdf = is_pdf_ok(status, ct, size, body)
            stored = storage_pdfs(created_uid)
            in_storage = len(stored) > 0
            ok = valid_pdf and in_storage
            print(f"  status={status} content_type={ct!r} bytes={size}")
            print(f"  valid_pdf={valid_pdf}  saved_to_S3={in_storage}  storage_files={stored}")
            if stored:
                print(f"  media link (proxy)  = {default_storage.url(user_pdf_key(created_uid, stored[-1]))}")
            if not valid_pdf:
                print(f"  RESPONSE (first 400 chars): {body[:400]!r}")
            # undo all DB changes
            raise _Rollback()
    except _Rollback:
        print("  DB changes rolled back (no test user/results persisted).")
    except Exception as e:  # unexpected
        import traceback
        print(f"  ERROR: {e}")
        traceback.print_exc()
        ok = False
    finally:
        # remove the S3 object(s) this test uploaded (survive the DB rollback)
        if created_uid is not None:
            storage_delete_user_pdfs(created_uid)
            d = pdf_dir(created_uid)
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        for f in (snapshot(graph_dir()) - g_before):
            try:
                Path(f).unlink()
            except OSError:
                pass
        print("  cleaned up test artifacts (S3 object + any local files/graphs).")

    print(f"  -> {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing-user-id", type=int, default=54)
    ap.add_argument("--source-user-id", type=int, default=54, help="User to clone complete test data from for the NEW-user test.")
    args = ap.parse_args()

    print("=" * 64)
    print("Class-10 report PDF generation test")
    print(f"MEDIA_ROOT = {settings.MEDIA_ROOT}")
    print("=" * 64)

    r1 = test_existing(args.existing_user_id)
    r2 = test_new(args.source_user_id)

    print("\n" + "=" * 64)
    print(f"EXISTING user : {'PASS' if r1 else 'FAIL'}")
    print(f"NEW user      : {'PASS' if r2 else 'FAIL'}")
    print("=" * 64)
    return 0 if (r1 and r2) else 1


if __name__ == "__main__":
    sys.exit(main())
