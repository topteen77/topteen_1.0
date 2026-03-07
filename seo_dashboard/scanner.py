"""
Crawl the site to collect open URLs. Used by the Scan button in the SEO dashboard.
Next scan adds only new URLs; no duplicates (stored in core.ScannedURL).
"""
import re
from urllib.parse import urljoin, urlparse


# Path prefixes to skip (not useful for SEO or may cause side effects)
SKIP_PREFIXES = (
    "/admin/",
    "/seo-dashboard/",
    "/user-analytics/",
    "/api/",
    "/static/",
    "/media/",
    "/oauth/",
    "/__debug__/",
)

# Max URLs to collect per scan and max depth to follow
MAX_URLS = 1000
MAX_DEPTH = 4


def _normalize_path(path):
    """Return path without leading/trailing slash, empty string for root."""
    if not path or not isinstance(path, str):
        return ""
    path = path.strip().split("?")[0].split("#")[0]
    path = path.strip("/")
    return path[:500] if len(path) > 500 else path


def _extract_links(html_content, base_path):
    """Extract same-site href paths from HTML content."""
    if not html_content or not isinstance(html_content, (str, bytes)):
        return set()
    if isinstance(html_content, bytes):
        try:
            html_content = html_content.decode("utf-8", errors="ignore")
        except Exception:
            return set()
    # Simple regex for href="..."; avoid script/style
    pattern = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    paths = set()
    for match in pattern.finditer(html_content):
        href = match.group(1).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        # Resolve relative to base
        if href.startswith("/"):
            path = href
        else:
            base = "/" + base_path + "/" if base_path else "/"
            path = urljoin(base, href)
        parsed = urlparse(path)
        path = parsed.path
        if not path or path.startswith(SKIP_PREFIXES):
            continue
        norm = _normalize_path(path)
        if norm:
            paths.add(norm)
    return paths


# Seed paths to crawl even if root fails or has no links (path without leading slash)
SEED_PATHS = [
    "",
    "blogs/",
    "careers/",
    "colleges/",
    "about-us/",
    "terms-and-condition/",
    "privacy-policy/",
    "contact-us/",
    "career-planning/",
    "searchand-explore/",
    "all-faq/",
    "ebooks/",
    "skilllabcourse/",
    "psychometrictest/",
    "testprep/",
]


def run_site_scan():
    """
    Crawl the site using Django test client; collect all open (2xx/3xx) URL paths.
    Returns (added_count, total_found, seen_count, errors).
    - added_count: number of new ScannedURL rows created
    - total_found: total URLs that returned 2xx/3xx in this run
    - seen_count: number already in DB (updated last_seen_at)
    - errors: list of error strings (optional)
    """
    from django.test import Client
    from core.models import ScannedURL
    from django.utils import timezone

    client = Client()
    # Start with seed paths so we discover URLs even if root fails
    to_visit = list(SEED_PATHS)
    visited = set()
    open_paths = set()
    errors = []
    depth_map = {p: 0 for p in to_visit}

    while to_visit and len(visited) < MAX_URLS:
        path = to_visit.pop(0)
        if path in visited:
            continue
        visited.add(path)
        depth = depth_map.get(path, 0)
        if depth > MAX_DEPTH:
            continue
        request_path = "/" + path if path else "/"
        if any(request_path.startswith(p) for p in SKIP_PREFIXES):
            continue
        try:
            response = client.get(request_path, follow=True)
        except Exception as e:
            errors.append("{}: {}".format(request_path, str(e)))
            continue
        if response.status_code in (200, 301, 302):
            open_paths.add(path)
            if hasattr(response, "content") and response.content:
                new_paths = _extract_links(response.content, path)
                for np in new_paths:
                    if np in visited or np in to_visit:
                        continue
                    if any(("/" + np).startswith(p) for p in SKIP_PREFIXES):
                        continue
                    if len(visited) + len(to_visit) >= MAX_URLS:
                        break
                    to_visit.append(np)
                    depth_map[np] = depth + 1
        # else: 404, 500, etc. - don't add to open_paths

    # Persist: add new, update last_seen for existing
    added_count = 0
    seen_count = 0
    now = timezone.now()
    for url_path in open_paths:
        obj, created = ScannedURL.objects.get_or_create(
            url_path=url_path,
            defaults={"last_seen_at": now},
        )
        if created:
            added_count += 1
        else:
            seen_count += 1
            ScannedURL.objects.filter(pk=obj.pk).update(last_seen_at=now)

    return added_count, len(open_paths), seen_count, errors
