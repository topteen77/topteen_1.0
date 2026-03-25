"""
Check every URL that would appear in sitemap.xml (same classes + index-rule filter)
and report paths that return HTTP 404.

Usage:
  python manage.py check_sitemap_urls
  python manage.py check_sitemap_urls --output /tmp/sitemap_404.txt
  python manage.py check_sitemap_urls --follow   # follow redirects, report final status
"""

from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.test import Client


def _location_to_request_path(location):
    """Turn sitemap location (path or path?query) into a string Client.get accepts."""
    loc = (location or "").strip()
    if not loc:
        return "/"
    if loc.startswith(("http://", "https://")):
        p = urlparse(loc)
        out = p.path or "/"
        if p.query:
            out = f"{out}?{p.query}"
        return out
    if not loc.startswith("/"):
        loc = "/" + loc
    return loc


def _iter_sitemap_paths():
    """Yield (section_name, path) for each URL that would be emitted by the sitemap."""
    from topteens.urls import sitemaps

    for section, sitemap_class in sitemaps.items():
        sm = sitemap_class()
        try:
            items = sm.items()
        except Exception as exc:
            yield (section, None, f"<items() failed: {exc}>")
            continue

        for item in items:
            try:
                loc = sm.location(item)
            except Exception as exc:
                yield (section, None, f"<location() failed for item: {exc}>")
                continue
            path = _location_to_request_path(loc)
            try:
                if sm._is_blocked_path(loc) or sm._is_blocked_path(path):
                    continue
            except Exception:
                pass
            yield (section, path, None)


class Command(BaseCommand):
    help = (
        "Request each URL included in the sitemap (per core/sitemaps + URLIndexRule filter) "
        "and list those that return 404."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="Write one 404 URL per line to this file (UTF-8).",
        )
        parser.add_argument(
            "--follow",
            action="store_true",
            help="Follow redirects; status is the final response (default: no redirects).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Stop after checking this many URLs (debug).",
        )

    def handle(self, *args, **options):
        out_path = options["output"]
        follow = options["follow"]
        limit = options["limit"]

        client = Client()
        not_found = []
        errors = []
        status_counts = {}
        total = 0

        for section, path, err in _iter_sitemap_paths():
            if err:
                errors.append((section, err))
                self.stderr.write(self.style.WARNING(f"[{section}] {err}"))
                continue
            if limit is not None and total >= limit:
                break
            total += 1
            try:
                response = client.get(path, follow=follow)
            except Exception as exc:
                errors.append((section, f"{path} -> request error: {exc}"))
                self.stderr.write(self.style.ERROR(f"{path}: {exc}"))
                continue

            code = response.status_code
            status_counts[code] = status_counts.get(code, 0) + 1
            if code == 404:
                not_found.append((section, path))

        self.stdout.write(self.style.NOTICE(f"Checked {total} sitemap URL(s)."))
        for code in sorted(status_counts.keys()):
            self.stdout.write(f"  HTTP {code}: {status_counts[code]}")

        if errors:
            self.stdout.write(self.style.WARNING(f"Issues while building list: {len(errors)}"))

        if not_found:
            self.stdout.write(self.style.ERROR(f"404 ({len(not_found)}):"))
            for section, path in not_found:
                line = f"[{section}] {path}"
                self.stdout.write(line)
            if out_path:
                with open(out_path, "w", encoding="utf-8") as f:
                    for _section, path in not_found:
                        f.write(path + "\n")
                self.stdout.write(self.style.SUCCESS(f"Wrote {len(not_found)} line(s) to {out_path}"))
        else:
            self.stdout.write(self.style.SUCCESS("No 404 responses for sitemap URLs."))
            if out_path:
                open(out_path, "w", encoding="utf-8").close()
                self.stdout.write(f"Created empty file: {out_path}")
