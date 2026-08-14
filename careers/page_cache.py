"""
Careers page cache — anonymous HTML + shared DB result payloads.

Uses the dedicated ``careers`` cache alias (Redis when available) so it still
works when default cache is DummyCache in DEBUG.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

from django.core.cache import caches
from django.db.models import Count
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

CACHE_ALIAS = "careers"
HTML_TTL = 900  # 15 minutes
RESULT_TTL = 900
LOCK_TTL = 45
VERSION_KEY = "careers:cache_version"
VERSION_TTL = 60 * 60 * 24 * 30


def _cache():
    try:
        return caches[CACHE_ALIAS]
    except Exception:
        return caches["default"]


def cache_version() -> str:
    c = _cache()
    ver = c.get(VERSION_KEY)
    if not ver:
        ver = "1"
        c.set(VERSION_KEY, ver, VERSION_TTL)
    return str(ver)


def bump_cache_version() -> str:
    """Invalidate all careers HTML/result keys by bumping a shared version."""
    c = _cache()
    try:
        current = int(c.get(VERSION_KEY) or 1)
    except (TypeError, ValueError):
        current = 1
    new_ver = str(current + 1)
    c.set(VERSION_KEY, new_ver, VERSION_TTL)
    return new_ver


def invalidate_careers_caches() -> None:
    bump_cache_version()


def _stable_query_suffix(request: HttpRequest) -> str:
    """Normalize query string for cache keys (order-independent)."""
    items: List[Tuple[str, str]] = []
    for key in sorted(request.GET.keys()):
        if key in ("student_id", "_", "utm_source", "utm_medium", "utm_campaign"):
            continue
        for val in sorted(request.GET.getlist(key)):
            items.append((key, val))
    if not items:
        return ""
    return urlencode(items)


def can_use_anon_html_cache(request: HttpRequest) -> bool:
    """Only cache shared anonymous browse HTML (no personalization)."""
    if request.method != "GET":
        return False
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        return False
    if request.GET.get("student_id"):
        return False
    if request.GET.get("mode") and request.GET.get("mode") != "view-mode":
        return False
    return True


def list_html_cache_key(request: HttpRequest, cluster_id: Optional[int] = None) -> str:
    q = _stable_query_suffix(request)
    digest = hashlib.md5(q.encode("utf-8")).hexdigest()[:16] if q else "base"
    cid = int(cluster_id) if cluster_id is not None else 0
    return f"careers:html:v{cache_version()}:list:{cid}:{digest}"


def detail_html_cache_key(career_id: int, slug: str) -> str:
    return f"careers:html:v{cache_version()}:detail:{int(career_id)}:{(slug or '')[:80]}"


def clusters_result_cache_key() -> str:
    return f"careers:result:v{cache_version()}:clusters_with_counts"


def get_cached_html(key: str) -> Optional[bytes]:
    try:
        val = _cache().get(key)
        if isinstance(val, bytes):
            return val
        if isinstance(val, str):
            return val.encode("utf-8")
    except Exception:
        logger.exception("careers cache get failed key=%s", key)
    return None


def set_cached_html(key: str, content: bytes, ttl: int = HTML_TTL) -> None:
    try:
        _cache().set(key, content, ttl)
    except Exception:
        logger.exception("careers cache set failed key=%s", key)


def cached_html_response(content: bytes, status: str = "HIT") -> HttpResponse:
    response = HttpResponse(content, content_type="text/html; charset=utf-8")
    response["X-Cache"] = status
    return response


def with_rebuild_lock(lock_key: str, build_fn):
    """
    Stampede-safe rebuild: one worker builds; others wait briefly for the key.
    ``build_fn`` must return (html_bytes_or_None, http_response).
    """
    c = _cache()
    lock_full = f"{lock_key}:lock"
    got_lock = c.add(lock_full, "1", LOCK_TTL)
    if not got_lock:
        for _ in range(40):
            time.sleep(0.25)
            # Caller re-checks HTML key; we just yield wait signal
            yield "WAIT"
        yield "PROCEED"
        return
    try:
        yield "BUILD"
    finally:
        c.delete(lock_full)


def get_or_set_clusters_with_counts() -> List[Dict[str, Any]]:
    """
    Shared cluster cards payload (landing page). Avoids heavy annotate query on every hit.
    Returns list of dicts: id, slug, name, image_url, count.
    """
    key = clusters_result_cache_key()
    c = _cache()
    cached = c.get(key)
    if isinstance(cached, list):
        return cached

    from careers.models import CareerCluster

    clusters_list = list(
        CareerCluster.objects.filter(
            career_clusters__publish_status=1,
            object_status=1,
        )
        .annotate(career_count=Count("career_clusters", distinct=True))
        .filter(career_count__gt=0)
        .distinct()
        .order_by("name")
    )
    payload = []
    for cl in clusters_list:
        try:
            image_url = cl.get_image_url()
        except Exception:
            image_url = "/static/images/career-cluster-default.png"
        payload.append(
            {
                "id": cl.id,
                "slug": cl.slug or "",
                "name": cl.name or "",
                "image_url": image_url,
                "count": int(getattr(cl, "career_count", 0) or 0),
            }
        )
    try:
        c.set(key, payload, RESULT_TTL)
    except Exception:
        logger.exception("failed to cache clusters_with_counts")
    return payload


def hydrate_clusters_with_counts(payload: Iterable[Dict[str, Any]]):
    """
    Turn cached dicts into lightweight objects for the Jinja template
    (expects item.cluster.name / .slug / .id / get_image_url and item.count).
    """

    class _ClusterObj:
        __slots__ = ("id", "slug", "name", "_image_url")

        def __init__(self, d: Dict[str, Any]):
            self.id = d.get("id")
            self.slug = d.get("slug") or ""
            self.name = d.get("name") or ""
            self._image_url = d.get("image_url") or "/static/images/career-cluster-default.png"

        def get_image_url(self):
            return self._image_url

    return [{"cluster": _ClusterObj(d), "count": int(d.get("count") or 0)} for d in payload]


def try_serve_anon_html(
    request: HttpRequest,
    cache_key: str,
) -> Optional[HttpResponse]:
    if not can_use_anon_html_cache(request):
        return None
    cached = get_cached_html(cache_key)
    if cached is not None:
        return cached_html_response(cached, "HIT")
    return None


def store_anon_html_if_eligible(
    request: HttpRequest,
    cache_key: str,
    response: HttpResponse,
) -> HttpResponse:
    if not can_use_anon_html_cache(request):
        return response
    try:
        if getattr(response, "status_code", None) == 200 and hasattr(response, "content"):
            # Stampede lock around set
            lock_key = f"{cache_key}:lock"
            c = _cache()
            # Only cache if we can set (or another worker already filled it)
            if get_cached_html(cache_key) is None:
                got = c.add(lock_key, "1", LOCK_TTL)
                if got:
                    try:
                        set_cached_html(cache_key, response.content)
                        response["X-Cache"] = "MISS"
                    finally:
                        c.delete(lock_key)
                else:
                    # Wait briefly; still return our fresh response
                    for _ in range(20):
                        time.sleep(0.1)
                        existing = get_cached_html(cache_key)
                        if existing is not None:
                            break
                    else:
                        set_cached_html(cache_key, response.content)
                    response["X-Cache"] = "MISS"
            else:
                response["X-Cache"] = "MISS"
    except Exception:
        logger.exception("failed storing careers anon HTML")
    return response
