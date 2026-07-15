"""Temporary timing profiler for careers cluster + career detail. Delete after use."""
import os
import re
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topteens.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.test import Client  # noqa: E402

settings.ALLOWED_HOSTS = ["*"]
settings.DEBUG = True


def sample_career_url():
    from careers.models import Career
    from core import choices
    c = (
        Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)
        .only("id", "slug")
        .first()
    )
    if not c:
        return None
    return f"/careers/career/{c.slug}-{c.id}-detail/"


def profile(label, url, runs=3):
    client = Client()
    client.get(url, HTTP_HOST="localhost")  # warm-up
    best = None
    for _ in range(runs):
        reset_queries()
        with CaptureQueriesContext(connection) as ctx:
            t0 = time.perf_counter()
            resp = client.get(url, HTTP_HOST="localhost")
            wall = (time.perf_counter() - t0) * 1000
        qs = ctx.captured_queries
        db_ms = sum(float(q["time"]) for q in qs) * 1000
        if best is None or wall < best[0]:
            best = (wall, db_ms, qs, resp.status_code)
    wall, db_ms, qs, status = best
    print(f"\n===== {label} =====")
    print(f"URL: {url}")
    print(f"status={status}  queries={len(qs)}  wall={wall:.0f}ms  db_total={db_ms:.0f}ms  render/py={wall-db_ms:.0f}ms")
    # slowest individual queries
    ranked = sorted(qs, key=lambda q: -float(q["time"]))
    print("\n-- slowest queries --")
    for q in ranked[:8]:
        print(f"  {float(q['time'])*1000:7.1f}ms  {q['sql'][:160]}")
    # duplicated normalized
    norm = {}
    for q in qs:
        key = re.sub(r"\d+", "N", q["sql"])
        key = re.sub(r"'[^']*'", "'X'", key)
        norm.setdefault(key, [0, 0.0])
        norm[key][0] += 1
        norm[key][1] += float(q["time"]) * 1000
    dups = [(k, v) for k, v in norm.items() if v[0] > 1]
    if dups:
        print("\n-- duplicated patterns (count > 1) --")
        for k, v in sorted(dups, key=lambda kv: -kv[1][1]):
            print(f"  x{v[0]}  {v[1]:.0f}ms total  {k[:140]}")


if __name__ == "__main__":
    profile("CAREERS CLUSTER", "/careers/cluster/commerce-economics-finance-25/")
    curl = sample_career_url()
    if curl:
        profile("CAREER DETAIL", curl)
    else:
        print("No published career found for detail profiling")
