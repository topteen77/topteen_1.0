"""Client for the Indian colleges listing API (canamuni upstream)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from django.conf import settings
from django.core.cache import caches

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 12
ENABLED_CONTENT_STATUSES = {"COMPLETED", "COMPLETE", "SUCCESS"}
ENABLED_VALIDATION_STATES = {"approved"}
# Keep under typical nginx/gunicorn proxy timeouts (often 30–60s).
UPSTREAM_HTTP_TIMEOUT = int(getattr(settings, "INDIAN_COLLEGES_HTTP_TIMEOUT", 12) or 12)
UPSTREAM_CACHE_TTL = int(getattr(settings, "INDIAN_COLLEGES_CACHE_TTL", 300) or 300)
CONTEXT_CACHE_TTL = int(getattr(settings, "INDIAN_COLLEGES_CONTEXT_CACHE_TTL", 90) or 90)
ENABLED_CACHE_TTL = int(getattr(settings, "INDIAN_COLLEGES_ENABLED_CACHE_TTL", 600) or 600)
# Soft deadline so the view returns before nginx 502s the worker.
LIST_BUILD_DEADLINE_SEC = float(
    getattr(settings, "INDIAN_COLLEGES_LIST_DEADLINE_SEC", 18) or 18
)
SEARCH_RESULT_LIMIT = 48


class CollegeContentDisabled(Exception):
    """Raised when a college has no enabled/publishable detail content."""


class ApiPage:
    """Minimal paginator-compatible wrapper for the college list template."""

    def __init__(
        self,
        items: Sequence[Any],
        page: int,
        total: int,
        page_size: int,
        total_pages: int,
        has_next: bool = False,
        has_previous: bool = False,
    ):
        self.object_list = list(items)
        self.number = max(int(page or 1), 1)
        self._has_next = bool(has_next)
        self._has_previous = bool(has_previous)
        total_pages = max(int(total_pages or 1), 1)
        self.paginator = SimpleNamespace(
            count=int(total or 0),
            num_pages=total_pages,
            page_range=range(1, total_pages + 1),
        )

    def __iter__(self):
        return iter(self.object_list)

    def __len__(self):
        return len(self.object_list)

    def has_next(self):
        return self._has_next

    def has_previous(self):
        return self._has_previous

    def previous_page_number(self):
        return max(self.number - 1, 1)

    def next_page_number(self):
        return self.number + 1 if self._has_next else self.number


COLLEGE_DETAIL_TABS = (
    {"label": "Admission", "path": "admission", "api_tab": "admission"},
    {"label": "Courses and Fees", "path": "courses", "api_tab": "inner_course"},
    {"label": "Cut Off", "path": "cut-off", "api_tab": "cut_off"},
    {"label": "Placement", "path": "placement", "api_tab": "placement"},
    {"label": "Faculty", "path": "faculty", "api_tab": "faculty"},
    {"label": "Ranking", "path": "ranking", "api_tab": "ranking"},
    {"label": "Hostel", "path": "hostel", "api_tab": "hostel"},
)

_TAB_BY_PATH = {tab["path"]: tab for tab in COLLEGE_DETAIL_TABS}
_TAB_BY_API = {tab["api_tab"]: tab for tab in COLLEGE_DETAIL_TABS}
# Accept canamuni path aliases too.
_TAB_BY_PATH.update(
    {
        "inner_course": _TAB_BY_API["inner_course"],
        "cut_off": _TAB_BY_API["cut_off"],
        "courses-and-fees": _TAB_BY_API["inner_course"],
    }
)


def _api_base() -> str:
    return (getattr(settings, "INDIAN_COLLEGES_API_BASE", "") or "").rstrip("/")


def _detail_base() -> str:
    return (getattr(settings, "INDIAN_COLLEGES_DETAIL_BASE", "") or "").rstrip("/")


def _college_api_cache():
    try:
        return caches["roster"]
    except Exception:
        from django.core.cache import cache

        return cache


def _cache_key(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"indian_colleges:v2:{prefix}:{digest}"


def _request_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = UPSTREAM_HTTP_TIMEOUT) -> Dict[str, Any]:
    base = _api_base()
    if not base:
        raise RuntimeError("INDIAN_COLLEGES_API_BASE is not configured")

    url = f"{base}{path}"
    response = requests.request(
        method,
        url,
        json=payload if method.upper() != "GET" else None,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response from {url}")
    return data


def _post_json(path: str, payload: Dict[str, Any], timeout: int = UPSTREAM_HTTP_TIMEOUT) -> Dict[str, Any]:
    cache_key = _cache_key(f"post:{path}", payload)
    c = _college_api_cache()
    try:
        cached = c.get(cache_key)
        if isinstance(cached, dict):
            return cached
    except Exception:
        pass

    data = _request_json("POST", path, payload=payload, timeout=timeout)
    try:
        c.set(cache_key, data, UPSTREAM_CACHE_TTL)
    except Exception:
        pass
    return data


def _get_json(path: str, timeout: int = 30) -> Dict[str, Any]:
    return _request_json("GET", path, timeout=timeout)


def fetch_college_base_details(college_id: int) -> Dict[str, Any]:
    # Guide mentions college_id; upstream currently requires `id`.
    return _get_json(f"/colleges/college-details/?id={int(college_id)}")


def fetch_college_tab_details(college_id: int, tab_name: str) -> Dict[str, Any]:
    return _get_json(
        f"/colleges/college-details/?id={int(college_id)}&tab_name={tab_name}"
    )


def fetch_college_search(query: str) -> Optional[List[Dict[str, Any]]]:
    """POST /colleges/search/. Returns None on transport/API failure."""
    q = (query or "").strip()
    if not q:
        return []
    try:
        data = _post_json("/colleges/search/", {"query": q})
    except Exception as e:
        logger.warning("college search API failed: %s", e)
        return None
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []
    return [row for row in results if isinstance(row, dict) and row.get("id")]


def fetch_courses_fees_streams(college_id: int) -> Dict[str, Any]:
    return _get_json(f"/colleges/{int(college_id)}/courses-fees/streams/")


def fetch_courses_fees_stream(college_id: int, stream_slug: str) -> Dict[str, Any]:
    slug = (stream_slug or "").strip("/")
    return _get_json(
        f"/colleges/{int(college_id)}/courses-fees/streams/{slug}/"
    )


def fetch_course_fees_detail(college_id: int, course_slug: str) -> Dict[str, Any]:
    """GET /colleges/{id}/courses-fees/{course_slug}/ — includes markdown_content."""
    slug = (course_slug or "").strip("/")
    if not slug:
        return {"error": "Missing course slug"}
    return _get_json(f"/colleges/{int(college_id)}/courses-fees/{slug}/")


def course_name_to_slug(name: str) -> str:
    """Best-effort slug from a course title (matches canamuni-style slugs)."""
    raw = (name or "").strip().lower()
    if not raw:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug


def _normalize_course_label(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"[\[\](){}+,./&]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _course_label_score(want: str, have: str) -> float:
    a = set(_normalize_course_label(want).split())
    b = set(_normalize_course_label(have).split())
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.issubset(b) or b.issubset(a):
        return 0.88
    return len(a & b) / float(len(a | b))


def _stream_slug_candidates(stream_slug: str = "", stream_name: str = "") -> List[str]:
    out: List[str] = []
    for raw in (stream_slug, course_name_to_slug(stream_name)):
        s = (raw or "").strip().strip("/")
        if s and s not in out:
            out.append(s)
    name = (stream_name or "").strip().lower()
    extras = []
    if "educ" in name or "teach" in name:
        extras.extend(["teaching-education", "education", "teacher-education"])
    if "commerce" in name:
        extras.append("commerce")
    if "science" in name:
        extras.append("science")
    if "law" in name:
        extras.append("law")
    if "medical" in name:
        extras.append("medical")
    if "management" in name:
        extras.append("management")
    for s in extras:
        if s not in out:
            out.append(s)
    return out


def _iter_college_stream_courses(
    college_id: int, stream_candidates: List[str], *, max_streams: int = 3
) -> List[Dict[str, Any]]:
    """Return course rows from matching stream(s) for a college.

    Fetches at most `max_streams` stream course lists (related streams first).
    """
    rows: List[Dict[str, Any]] = []
    tried = set()
    preferred: List[str] = []
    fallback: List[str] = []
    for raw in stream_candidates or []:
        slug = (raw or "").strip().strip("/")
        if slug and slug not in preferred:
            preferred.append(slug)

    try:
        streams_payload = fetch_courses_fees_streams(college_id)
        if streams_payload.get("error") and not (streams_payload.get("streams") or []):
            return []
        discovered: List[str] = []
        related: List[str] = []
        for stream in streams_payload.get("streams") or []:
            if not isinstance(stream, dict):
                continue
            slug = (stream.get("slug") or "").strip()
            name = (stream.get("name") or "").strip().lower()
            if not slug:
                continue
            discovered.append(slug)
            if not preferred:
                related.append(slug)
                continue
            for want in preferred:
                want_l = want.lower()
                if (
                    want_l in slug
                    or slug in want_l
                    or want_l in name
                    or _course_label_score(want, name) >= 0.35
                ):
                    related.append(slug)
                    break
            else:
                fallback.append(slug)
        ordered: List[str] = []
        # Prefer discovered related streams first, then guessed candidates.
        for slug in related + preferred + (discovered if not preferred else fallback):
            if slug not in ordered:
                ordered.append(slug)
        preferred = ordered
    except Exception:
        pass

    for slug in preferred[: max(1, int(max_streams or 3))]:
        if not slug or slug in tried:
            continue
        tried.add(slug)
        try:
            payload = fetch_courses_fees_stream(college_id, slug)
        except Exception:
            continue
        for item in payload.get("courses") or []:
            if isinstance(item, dict):
                item = dict(item)
                item["_stream_slug"] = slug
                rows.append(item)
        if rows:
            break
    return rows


def resolve_course_fees_slug(
    college_id: int,
    *,
    course_slug: str = "",
    course_id: Optional[int] = None,
    course_name: str = "",
    stream_slug: str = "",
    stream_name: str = "",
) -> str:
    """Resolve courses-fees detail slug for a college course."""
    slug = (course_slug or "").strip().strip("/")
    if slug:
        return slug

    want_name = (course_name or "").strip()
    want_id = None
    try:
        want_id = int(course_id) if course_id is not None else None
    except (TypeError, ValueError):
        want_id = None

    rows = _iter_college_stream_courses(
        college_id, _stream_slug_candidates(stream_slug, stream_name)
    )

    def _row_meta(item: Dict[str, Any]):
        nested = item.get("course") if isinstance(item.get("course"), dict) else {}
        item_slug = (nested.get("slug") or "").strip()
        ids = []
        for raw in (nested.get("id"), item.get("id")):
            try:
                if raw is not None:
                    ids.append(int(raw))
            except (TypeError, ValueError):
                pass
        item_name = (item.get("name") or nested.get("name") or "").strip()
        return item_slug, ids, item_name

    if want_name:
        for item in rows:
            item_slug, _ids, item_name = _row_meta(item)
            if item_slug and item_name.lower() == want_name.lower():
                return item_slug

    if want_id is not None:
        for item in rows:
            item_slug, ids, _item_name = _row_meta(item)
            if item_slug and want_id in ids:
                return item_slug

    if want_name and rows:
        best = (0.0, "")
        for item in rows:
            item_slug, _ids, item_name = _row_meta(item)
            if not item_slug:
                continue
            score = _course_label_score(want_name, item_name)
            if score > best[0]:
                best = (score, item_slug)
        if best[0] >= 0.55 and best[1]:
            return best[1]

    return course_name_to_slug(course_name)


def fetch_course_overview_html(
    college_id: int,
    *,
    course_slug: str = "",
    course_id: Optional[int] = None,
    course_name: str = "",
    stream_slug: str = "",
    stream_name: str = "",
) -> Dict[str, Any]:
    """Fetch college course markdown and return rendered HTML + meta."""
    out: Dict[str, Any] = {
        "html": "",
        "course_slug": "",
        "course_name": course_name or "",
        "degree_level": "",
        "stream_name": stream_name or "",
        "stream_slug": stream_slug or "",
        "college_id": None,
        "college_name": "",
        "college_city": "",
        "college_state": "",
    }
    try:
        cid = int(college_id)
    except (TypeError, ValueError):
        return out

    slug = resolve_course_fees_slug(
        cid,
        course_slug=course_slug,
        course_id=course_id,
        course_name=course_name,
        stream_slug=stream_slug,
        stream_name=stream_name,
    )
    out["course_slug"] = slug
    if not slug:
        return out

    try:
        detail = fetch_course_fees_detail(cid, slug)
    except Exception as e:
        logger.warning(
            "course fees detail failed college=%s slug=%s: %s", cid, slug, e
        )
        # Fuzzy slug may be wrong; try best stream-course slug directly.
        rows = _iter_college_stream_courses(
            cid, _stream_slug_candidates(stream_slug, stream_name)
        )
        detail = {}
        best = (0.0, "", {})
        for item in rows:
            nested = item.get("course") if isinstance(item.get("course"), dict) else {}
            item_slug = (nested.get("slug") or "").strip()
            item_name = (item.get("name") or nested.get("name") or "").strip()
            if not item_slug:
                continue
            score = _course_label_score(course_name, item_name) if course_name else 0.0
            if score > best[0]:
                best = (score, item_slug, item)
        if best[0] >= 0.55 and best[1]:
            try:
                detail = fetch_course_fees_detail(cid, best[1])
                out["course_slug"] = best[1]
                slug = best[1]
            except Exception:
                return out
        else:
            return out

    if not isinstance(detail, dict) or detail.get("error"):
        return out

    course_block = detail.get("course") if isinstance(detail.get("course"), dict) else {}
    markdown = (
        course_block.get("markdown_content")
        or detail.get("markdown_content")
        or ""
    )
    if markdown:
        try:
            out["html"] = render_markdown_html(markdown)
        except Exception as e:
            logger.warning("course markdown render failed: %s", e)
            out["html"] = ""

    nested = course_block.get("course")
    if isinstance(nested, dict):
        out["course_name"] = nested.get("name") or out["course_name"]
        out["degree_level"] = nested.get("degree_level") or ""
        out["stream_name"] = nested.get("stream_name") or out["stream_name"]
        out["stream_slug"] = nested.get("stream_slug") or out["stream_slug"]
    elif course_block.get("name"):
        out["course_name"] = course_block.get("name") or out["course_name"]

    # Reject weak/wrong course matches (e.g. B.Ed content for a B.P.Ed page).
    if course_name and out.get("course_name"):
        if _course_label_score(course_name, out["course_name"]) < 0.72:
            return {
                "html": "",
                "course_slug": out.get("course_slug") or "",
                "course_name": course_name or "",
                "degree_level": "",
                "stream_name": stream_name or "",
                "stream_slug": stream_slug or "",
                "college_id": None,
                "college_name": "",
                "college_city": "",
                "college_state": "",
            }

    location = detail.get("location") if isinstance(detail.get("location"), dict) else {}
    out["college_name"] = (location.get("name") or "").strip()
    out["college_city"] = (location.get("city") or "").strip()
    out["college_state"] = (location.get("state") or "").strip()
    if out.get("html"):
        out["college_id"] = cid
    return out


def find_course_overview_html(
    *,
    course_name: str = "",
    course_id: Optional[int] = None,
    course_slug: str = "",
    stream_name: str = "",
    stream_slug: str = "",
    stream_id: Optional[int] = None,
    college_ids: Optional[List[int]] = None,
    max_colleges: int = 8,
) -> Dict[str, Any]:
    """Find course markdown across candidate colleges (matched-course pages).

    Many filter-matched colleges have no publishable courses-fees content.
    Try provided college ids first, then a small stream college sample.
    """
    cache_backend = _college_api_cache()
    cache_key = _cache_key(
        "course_overview_html:v3",
        {
            "course_id": course_id,
            "course_name": (course_name or "").strip().lower(),
            "stream_id": stream_id,
            "stream_slug": stream_slug,
        },
    )
    try:
        cached = cache_backend.get(cache_key)
        if isinstance(cached, dict) and cached.get("html"):
            return cached
    except Exception:
        pass

    empty = {
        "html": "",
        "course_slug": course_slug or "",
        "course_name": course_name or "",
        "degree_level": "",
        "stream_name": stream_name or "",
        "stream_slug": stream_slug or "",
        "college_id": None,
        "college_name": "",
        "college_city": "",
        "college_state": "",
    }

    seen = set()
    ordered_ids: List[int] = []
    for raw in college_ids or []:
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        ordered_ids.append(cid)

    # Broaden only when no candidate colleges were provided.
    if not ordered_ids and stream_id:
        try:
            selected = build_selected_filters(stream_id=int(stream_id))
            listing = fetch_colleges_list(
                selected_filters=selected,
                page=1,
                page_size=min(12, max(4, max_colleges * 2)),
                detail_view=True,
                sort_by="college_name",
                sort_order="asc",
            )
            for row in listing.get("data") or listing.get("results") or []:
                raw = row.get("college_id") or row.get("id")
                try:
                    cid = int(raw)
                except (TypeError, ValueError):
                    continue
                if cid in seen:
                    continue
                seen.add(cid)
                ordered_ids.append(cid)
                if len(ordered_ids) >= max_colleges:
                    break
        except Exception as e:
            logger.warning("overview stream college broaden failed: %s", e)

    # Prefer exact slug fetches on provided colleges (cheap); stop at first HTML hit.
    limit = max(1, min(int(max_colleges or 3), 4))
    for cid in ordered_ids[:limit]:
        try:
            overview = fetch_course_overview_html(
                cid,
                course_slug=course_slug,
                course_id=course_id,
                course_name=course_name,
                stream_slug=stream_slug,
                stream_name=stream_name,
            )
        except Exception as e:
            logger.warning("overview fetch failed college=%s: %s", cid, e)
            continue
        if overview.get("html"):
            try:
                cache_backend.set(cache_key, overview, UPSTREAM_CACHE_TTL)
            except Exception:
                pass
            return overview

    return empty


def resolve_detail_tab(tab: Optional[str]) -> Dict[str, str]:
    key = (tab or "admission").strip("/").lower()
    return _TAB_BY_PATH.get(key) or _TAB_BY_PATH["admission"]


def is_tab_content_enabled(tab_data: Optional[Dict[str, Any]]) -> bool:
    """Return True when upstream marks tab content as enabled/publishable."""
    if not isinstance(tab_data, dict) or tab_data.get("error"):
        return False

    markdown = extract_tab_body(tab_data)
    has_content = tab_data.get("has_content") is True
    valid_content = tab_data.get("valid_content") is True
    validation = str(tab_data.get("content_validation_state") or "").lower()
    status = str(tab_data.get("status") or "").upper()
    status_valid = str(tab_data.get("status_valid_content") or "").upper()

    status_ok = (
        valid_content
        or validation in ENABLED_VALIDATION_STATES
        or status in ENABLED_CONTENT_STATUSES
        or status_valid in ENABLED_CONTENT_STATUSES
    )
    content_ok = has_content or bool(markdown)
    return bool(status_ok and content_ok)


def is_courses_tab_enabled(college_id: int) -> bool:
    try:
        payload = fetch_courses_fees_streams(college_id)
    except Exception:
        return False
    if payload.get("error"):
        return False
    return bool(payload.get("streams"))


def is_college_content_enabled(college_id: Optional[int]) -> bool:
    """List gate: college is shown only when at least one detail tab is enabled."""
    if not college_id:
        return False
    cid = int(college_id)
    cache_key = f"indian_colleges:v3:enabled:{cid}"
    cache_backend = _college_api_cache()
    try:
        cached = cache_backend.get(cache_key)
        if cached is True or cached is False:
            return bool(cached)
    except Exception:
        pass

    enabled = False
    try:
        # Fast path: admission alone covers most publishable colleges.
        payload = fetch_college_tab_details(cid, "admission")
        if not payload.get("error") and is_tab_content_enabled(payload.get("admission")):
            enabled = True
        elif is_courses_tab_enabled(cid):
            enabled = True
        else:
            # Any other tab (placement, cutoff, etc.) counts as active content.
            tabs = get_enabled_tabs_for_college(cid, include_courses=False)
            enabled = bool(tabs)
    except Exception as e:
        logger.debug("college enabled check failed for %s: %s", college_id, e)
        enabled = False

    try:
        cache_backend.set(cache_key, enabled, ENABLED_CACHE_TTL)
    except Exception:
        pass
    return enabled


def get_enabled_tabs_for_college(
    college_id: int,
    include_courses: bool = True,
) -> List[Dict[str, str]]:
    """Probe upstream tabs and return only enabled ones (order preserved)."""
    enabled_paths = set()

    def _check(tab: Dict[str, str]) -> Optional[str]:
        api_tab = tab["api_tab"]
        if api_tab == "inner_course":
            return tab["path"] if is_courses_tab_enabled(college_id) else None
        try:
            payload = fetch_college_tab_details(college_id, api_tab)
            if payload.get("error"):
                return None
            if is_tab_content_enabled(payload.get(api_tab)):
                return tab["path"]
        except Exception as e:
            logger.debug("tab status check failed %s/%s: %s", college_id, api_tab, e)
        return None

    tabs_to_check = [
        tab
        for tab in COLLEGE_DETAIL_TABS
        if include_courses or tab["api_tab"] != "inner_course"
    ]
    with ThreadPoolExecutor(max_workers=min(8, len(tabs_to_check) or 1)) as pool:
        futures = [pool.submit(_check, tab) for tab in tabs_to_check]
        for fut in as_completed(futures):
            path = fut.result()
            if path:
                enabled_paths.add(path)

    return [tab for tab in COLLEGE_DETAIL_TABS if tab["path"] in enabled_paths]


def filter_enabled_college_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not items:
        return []

    def _enabled(item: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        return item, is_college_content_enabled(item.get("college_id"))

    with ThreadPoolExecutor(max_workers=min(10, len(items) or 1)) as pool:
        results = list(pool.map(_enabled, items))
    return [item for item, ok in results if ok]


def _content_looks_like_html(text: str) -> bool:
    """True when tab payload is already HTML (common for richer college pages)."""
    sample = (text or "").lstrip()[:1200].lower()
    if not sample:
        return False
    if sample.startswith("<!doctype") or sample.startswith("<html"):
        return True
    # Prefer markdown when classic markdown markers dominate the start.
    if re.search(r"(?m)^(#{1,6}\s|\*\*[^*]|[-*+]\s|\|.+\|)", (text or "").lstrip()[:400]):
        return False
    if sample.startswith("<"):
        return True
    return bool(
        re.search(
            r"</?(?:div|section|article|table|thead|tbody|tr|td|th|ul|ol|li|p|h[1-6]|span|br|img|figure)\b",
            sample,
        )
    )


def _content_looks_like_markdown(text: str) -> bool:
    sample = text or ""
    return bool(
        re.search(
            r"(?m)(^#{1,6}\s|\*\*[^*\n]+\*\*|__[^_\n]+__|^\s*[-*+]\s|\[[^\]]+\]\([^)]+\)|^\|.+\|)",
            sample,
        )
    )


def _sanitize_tab_html(html: str) -> str:
    """Allowlist-sanitize HTML from the upstream API."""
    try:
        import bleach
    except ImportError:
        logger.warning("bleach is not installed; returning unsanitized tab HTML")
        return html

    allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS).union(
        {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "pre",
            "code",
            "table",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "th",
            "td",
            "hr",
            "br",
            "ul",
            "ol",
            "li",
            "strong",
            "em",
            "b",
            "i",
            "u",
            "blockquote",
            "div",
            "span",
            "section",
            "article",
            "figure",
            "figcaption",
            "img",
            "caption",
            "colgroup",
            "col",
        }
    )
    return bleach.clean(
        html,
        tags=allowed_tags,
        attributes={
            **bleach.sanitizer.ALLOWED_ATTRIBUTES,
            "a": ["href", "title", "rel", "target"],
            "td": ["colspan", "rowspan", "align"],
            "th": ["colspan", "rowspan", "align"],
            "img": ["src", "alt", "title", "width", "height"],
            "div": ["class"],
            "span": ["class"],
            "table": ["class"],
            "p": ["class"],
            "h1": ["class"],
            "h2": ["class"],
            "h3": ["class"],
            "h4": ["class"],
            "section": ["class"],
            "article": ["class"],
        },
        strip=True,
    )


def _normalize_api_markdown(text: str) -> str:
    """Normalize upstream markdown so lists/tables render reliably.

    Course/college API bodies often omit the blank line before a list, e.g.:
      ... including:\\n*   Computer Application
    python-markdown then keeps the asterisks inside a paragraph (worse with nl2br).
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out: List[str] = []

    def _is_list_line(line: str) -> bool:
        return bool(re.match(r"^[ \t]*(?:[-*+]|\d+\.)[ \t]+\S", line))

    def _is_table_line(line: str) -> bool:
        s = line.strip()
        return s.startswith("|") and s.count("|") >= 2

    for line in lines:
        prev = out[-1] if out else ""
        prev_blank = not prev.strip()
        if (
            _is_list_line(line)
            and out
            and not prev_blank
            and not _is_list_line(prev)
        ):
            out.append("")
        elif (
            _is_table_line(line)
            and out
            and not prev_blank
            and not _is_table_line(prev)
        ):
            out.append("")
        out.append(line)

    text = "\n".join(out)
    # Normalize "*   item" / "1.   item" marker spacing.
    text = re.sub(r"(?m)^([ \t]*[-*+])[ \t]+", r"\1 ", text)
    text = re.sub(r"(?m)^([ \t]*\d+\.)[ \t]+", r"\1 ", text)
    return text


def _wrap_markdown_tables(html: str) -> str:
    """Wrap bare <table> nodes for horizontal scroll on small screens."""
    if not html or "<table" not in html.lower():
        return html
    try:
        parts: List[str] = []
        i = 0
        lower = html.lower()
        while True:
            start = lower.find("<table", i)
            if start < 0:
                parts.append(html[i:])
                break
            parts.append(html[i:start])
            end = lower.find("</table>", start)
            if end < 0:
                parts.append(html[start:])
                break
            end += len("</table>")
            block = html[start:end]
            already = "indian-md-table-wrap" in block or 'class="table-responsive"' in block
            # Don't wrap if already inside our wrapper (look back a bit).
            prefix = html[max(0, start - 64) : start]
            if already or "indian-md-table-wrap" in prefix:
                parts.append(block)
            else:
                parts.append(
                    f'<div class="table-responsive indian-md-table-wrap">{block}</div>'
                )
            i = end
        return "".join(parts)
    except Exception as e:
        logger.warning("table wrap failed: %s", e)
        return html


def _simple_markdown_to_html(text: str) -> str:
    """Dependency-free markdown subset for staging when `markdown` isn't installed."""
    from django.utils.html import escape

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    in_ul = False
    in_ol = False
    in_table = False
    paragraph: List[str] = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_table():
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    def flush_paragraph():
        nonlocal paragraph
        if not paragraph:
            return
        body = " ".join(paragraph).strip()
        paragraph = []
        if body:
            out.append(f"<p>{_inline_md(body)}</p>")

    def _inline_md(value: str) -> str:
        # Escape first, then restore intentional markdown emphasis/links.
        s = escape(value)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"__(.+?)__", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    def is_table_sep(line: str) -> bool:
        return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line))

    def table_cells(line: str) -> List[str]:
        raw = line.strip().strip("|")
        return [c.strip() for c in raw.split("|")]

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            close_lists()
            close_table()
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            close_lists()
            close_table()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline_md(heading.group(2))}</h{level}>")
            i += 1
            continue

        # GFM-style table: header + separator + rows
        if (
            "|" in stripped
            and i + 1 < len(lines)
            and is_table_sep(lines[i + 1])
        ):
            flush_paragraph()
            close_lists()
            close_table()
            headers = table_cells(stripped)
            out.append("<table><thead><tr>")
            for cell in headers:
                out.append(f"<th>{_inline_md(cell)}</th>")
            out.append("</tr></thead><tbody>")
            in_table = True
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = table_cells(lines[i])
                out.append("<tr>")
                for cell in cells:
                    out.append(f"<td>{_inline_md(cell)}</td>")
                out.append("</tr>")
                i += 1
            close_table()
            continue

        ul = re.match(r"^[-*+]\s+(.*)$", stripped)
        if ul:
            flush_paragraph()
            close_table()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline_md(ul.group(1))}</li>")
            i += 1
            continue

        ol = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ol:
            flush_paragraph()
            close_table()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline_md(ol.group(1))}</li>")
            i += 1
            continue

        close_lists()
        close_table()
        paragraph.append(stripped)
        i += 1

    flush_paragraph()
    close_lists()
    close_table()
    return "\n".join(out)


def _markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML; prefer python-markdown, else built-in fallback."""
    normalized = _normalize_api_markdown(markdown_text)
    try:
        import markdown
    except ImportError:
        logger.warning("python-markdown not installed; using built-in markdown fallback")
        return _simple_markdown_to_html(normalized)

    # Prefer list/table fidelity over nl2br — nl2br turns list lines into <br> text.
    extension_sets = (
        ["extra", "sane_lists", "tables"],
        ["sane_lists", "tables"],
        ["extra", "tables"],
        ["tables"],
        ["extra", "sane_lists", "nl2br", "tables"],
        [],
    )
    last_error: Optional[Exception] = None
    for extensions in extension_sets:
        try:
            return markdown.markdown(normalized, extensions=extensions)
        except Exception as e:
            last_error = e
            continue
    logger.warning("python-markdown extensions failed (%s); using built-in fallback", last_error)
    return _simple_markdown_to_html(normalized)


def _as_template_html(html: str):
    """Mark HTML safe for both Django and Jinja2 autoescape."""
    try:
        from markupsafe import Markup

        return Markup(html)
    except Exception:
        from django.utils.safestring import mark_safe

        return mark_safe(html)


def render_markdown_html(markdown_text: str) -> str:
    """Render tab body as HTML as soon as the API response is received.

    - HTML payloads are sanitized and returned.
    - Markdown payloads are converted to HTML, then sanitized.
    """
    if not markdown_text:
        return ""

    text = markdown_text.strip()
    if not text:
        return ""

    # Upstream often stores HTML in `markdown_content`. Don't run that through
    # markdown/nl2br — it breaks tables. But if it clearly is markdown, convert.
    treat_as_html = _content_looks_like_html(text) and not _content_looks_like_markdown(text)
    if treat_as_html:
        try:
            return _as_template_html(_sanitize_tab_html(text))
        except Exception as e:
            logger.warning("tab HTML sanitize failed: %s", e)
            return _as_template_html(text)

    try:
        html = _markdown_to_html(text)
    except Exception as e:
        logger.error("markdown conversion failed: %s", e)
        html = _simple_markdown_to_html(_normalize_api_markdown(text))

    html = _wrap_markdown_tables(html)

    try:
        return _as_template_html(_sanitize_tab_html(html))
    except Exception as e:
        logger.warning("post-markdown sanitize failed: %s", e)
        return _as_template_html(html)


def extract_tab_body(tab_data: Optional[Dict[str, Any]]) -> str:
    """Prefer explicit HTML fields, then markdown_content."""
    if not isinstance(tab_data, dict):
        return ""
    for key in ("html_content", "content_html", "html", "markdown_content", "content"):
        value = tab_data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def get_college_detail_context_from_api(
    college_id: int,
    tab: Optional[str] = None,
    stream_slug: Optional[str] = None,
    highlight_course_slug: Optional[str] = None,
) -> Dict[str, Any]:
    requested_tab = resolve_detail_tab(tab)
    active_tab = requested_tab
    api_tab = active_tab["api_tab"]

    base = fetch_college_base_details(college_id)
    location = base.get("location") or {}
    name = (
        location.get("name")
        or base.get("name")
        or f"College {college_id}"
    )
    city = location.get("city") or (base.get("city") or {}).get("name") or ""
    state = location.get("state") or (base.get("state") or {}).get("name") or ""
    college_type = (
        location.get("college_type")
        or (base.get("college_type") or {}).get("name")
        or ""
    )
    fees = [
        item.get("fees")
        for item in (base.get("college_avg_fee") or [])
        if isinstance(item, dict) and item.get("fees")
    ]

    enabled_tabs = get_enabled_tabs_for_college(college_id, include_courses=True)
    enabled_paths = {item["path"] for item in enabled_tabs}
    if not enabled_tabs:
        raise CollegeContentDisabled(
            f"College {college_id} has no publishable detail tabs."
        )
    if active_tab["path"] not in enabled_paths:
        # Caller can redirect to the first enabled tab.
        active_tab = enabled_tabs[0]
        api_tab = active_tab["api_tab"]

    tab_html = ""
    tab_error = None
    tab_markdown = ""
    streams = []
    courses = []
    selected_stream = (stream_slug or "").strip() or None
    highlight_slug = (highlight_course_slug or "").strip().strip("/")
    content_unavailable = False

    if api_tab == "inner_course":
        streams_payload = fetch_courses_fees_streams(college_id)
        if streams_payload.get("error"):
            tab_error = streams_payload.get("error")
        streams = streams_payload.get("streams") or []
        # If a specific course is requested, pick the stream that contains it.
        if highlight_slug and streams:
            for stream in streams:
                slug = (stream.get("slug") or "").strip()
                if not slug:
                    continue
                try:
                    probe = fetch_courses_fees_stream(college_id, slug)
                except Exception:
                    continue
                for item in probe.get("courses") or []:
                    nested = item.get("course") if isinstance(item, dict) else None
                    item_slug = ""
                    if isinstance(nested, dict):
                        item_slug = (nested.get("slug") or "").strip()
                    if item_slug == highlight_slug:
                        selected_stream = slug
                        courses = probe.get("courses") or []
                        break
                if selected_stream == slug and courses:
                    break
        if not selected_stream and streams:
            selected_stream = streams[0].get("slug")
        if selected_stream and not courses:
            try:
                course_payload = fetch_courses_fees_stream(college_id, selected_stream)
                if course_payload.get("error"):
                    tab_error = course_payload.get("error")
                courses = course_payload.get("courses") or []
            except Exception as e:
                logger.warning("courses-fees stream failed: %s", e)
                tab_error = "Unable to load courses for this stream."
    else:
        tab_payload = fetch_college_tab_details(college_id, api_tab)
        if tab_payload.get("error"):
            tab_error = tab_payload.get("error")
        else:
            tab_data = tab_payload.get(api_tab) or {}
            if isinstance(tab_data, dict) and is_tab_content_enabled(tab_data):
                tab_markdown = extract_tab_body(tab_data)
                tab_html = render_markdown_html(tab_markdown)
            else:
                tab_error = f"No enabled content for '{active_tab['label']}'."

    tabs = [
        {
            "label": item["label"],
            "path": item["path"],
            "active": item["path"] == active_tab["path"],
        }
        for item in enabled_tabs
    ]

    return {
        "use_indian_colleges_api": True,
        "college_id": int(college_id),
        "college_name": name,
        "college_city": city,
        "college_state": state,
        "college_type": college_type,
        "college_fees": fees,
        "college_location": ", ".join([p for p in ["India", state, city] if p]),
        "active_tab": active_tab["path"],
        "active_tab_label": active_tab["label"],
        "tabs": tabs,
        "tab_html": tab_html,
        "tab_markdown": tab_markdown,
        "tab_error": tab_error,
        "content_unavailable": content_unavailable,
        "is_courses_tab": api_tab == "inner_course",
        "streams": streams,
        "courses": courses,
        "selected_stream": selected_stream,
        "highlight_course_slug": highlight_slug,
        "base_details": base,
        "redirect_tab": (
            None
            if requested_tab["path"] == active_tab["path"]
            else active_tab["path"]
        ),
    }


def fetch_filters(selected_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _post_json(
        "/colleges/filters/",
        {"selected_filters": selected_filters or {}},
    )


def fetch_colleges_list(
    selected_filters: Optional[Dict[str, Any]] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    sort_by: str = "name",
    sort_order: str = "asc",
    detail_view: bool = True,
) -> Dict[str, Any]:
    return _post_json(
        "/colleges/colleges-list-view/",
        {
            "selected_filters": selected_filters or {},
            "page": int(page or 1),
            "page_size": int(page_size or DEFAULT_PAGE_SIZE),
            "detail_view": bool(detail_view),
            "sort_by": sort_by or "name",
            "sort_order": sort_order or "asc",
        },
    )


def build_selected_filters(
    state_id: Optional[int] = None,
    city_ids: Optional[Iterable[int]] = None,
    stream_id: Optional[int] = None,
    sub_stream_ids: Optional[Iterable[int]] = None,
    course_id: Optional[int] = None,
    course_name: Optional[str] = None,
    course_type_id: Optional[int] = None,
    course_type_name: Optional[str] = None,
    college_type_id: Optional[int] = None,
    college_type_name: Optional[str] = None,
    avg_fee_id: Optional[int] = None,
    course_duration_id: Optional[int] = None,
    college_category_id: Optional[int] = None,
    entrance_exam_ids: Optional[Iterable[int]] = None,
    gender_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Build upstream selected_filters payload (matches canamuni SPA shape)."""
    selected: Dict[str, Any] = {}

    if state_id:
        selected["state"] = {"id": int(state_id)}

    cities = [int(cid) for cid in (city_ids or []) if cid]
    if cities:
        selected["cities"] = [{"id": cid} for cid in cities]

    if stream_id:
        selected["stream"] = {"id": int(stream_id)}

    sub_streams = [int(sid) for sid in (sub_stream_ids or []) if sid]
    if sub_streams:
        selected["sub_streams"] = [{"id": sid} for sid in sub_streams]

    if course_id:
        item: Dict[str, Any] = {"id": int(course_id)}
        if course_name:
            item["name"] = course_name
        selected["courses"] = item

    if course_type_id:
        item = {"id": int(course_type_id)}
        if course_type_name:
            item["name"] = course_type_name
        selected["course_type"] = item

    if college_type_id:
        item = {"id": int(college_type_id)}
        if college_type_name:
            item["name"] = college_type_name
        selected["college_type"] = item

    if avg_fee_id:
        selected["college_avg_fee"] = {"id": int(avg_fee_id)}

    if course_duration_id:
        selected["course_duration"] = {"id": int(course_duration_id)}

    if college_category_id:
        selected["college_category"] = {"id": int(college_category_id)}

    exams = [int(eid) for eid in (entrance_exam_ids or []) if eid]
    if exams:
        selected["entrance_exams"] = [{"id": eid} for eid in exams]

    if gender_id:
        selected["gender"] = {"id": int(gender_id)}

    # Avoid upstream IP geolocation when the user has not chosen a state/city.
    # Without this, empty selected_filters scopes results to the caller's (server) IP.
    if not state_id and not cities:
        selected["nationwide"] = True

    return selected


def adapt_college(item: Dict[str, Any]) -> SimpleNamespace:
    fees = [fee for fee in (item.get("avg_fees_array") or []) if fee]
    state_name = item.get("state_name") or ""
    city_name = item.get("city_name") or ""
    college_id = item.get("college_id")

    return SimpleNamespace(
        college_id=college_id,
        name=item.get("college_name") or "College",
        slug=None,
        logo=None,
        rating=None,
        college_type=item.get("college_type"),
        stream_name=item.get("stream_name"),
        course_name=item.get("course_name"),
        gender_name=item.get("gender_name"),
        avg_fees=fees,
        city_name=city_name,
        state_name=state_name,
        country=SimpleNamespace(name="India"),
        state=SimpleNamespace(name=state_name),
        city=SimpleNamespace(name=city_name),
        external_url="",
        is_external=True,
    )


def list_item_from_details(college_id: int, base: Dict[str, Any]) -> Dict[str, Any]:
    """Map college-details payload into a list-row shape for facets/cards."""
    city = base.get("city") if isinstance(base.get("city"), dict) else {}
    state = base.get("state") if isinstance(base.get("state"), dict) else {}
    ctype = base.get("college_type") if isinstance(base.get("college_type"), dict) else {}
    stream = base.get("stream") if isinstance(base.get("stream"), dict) else {}
    substream = base.get("substream") if isinstance(base.get("substream"), dict) else {}
    gender = base.get("gender") if isinstance(base.get("gender"), dict) else {}
    category = base.get("category") if isinstance(base.get("category"), dict) else {}
    fees = base.get("college_avg_fee") if isinstance(base.get("college_avg_fee"), list) else []
    fee_ids = []
    avg_fees = []
    for fee in fees:
        if not isinstance(fee, dict):
            continue
        fid = _as_int(fee.get("id"))
        if fid is not None:
            fee_ids.append(fid)
        if fee.get("fees"):
            avg_fees.append(fee.get("fees"))
    exam_ids = []
    for exam in base.get("entrance_exams") or []:
        if isinstance(exam, dict):
            eid = _as_int(exam.get("id"))
            if eid is not None:
                exam_ids.append(eid)
    duration = base.get("duration") if isinstance(base.get("duration"), dict) else {}
    return {
        "college_id": int(college_id),
        "college_name": base.get("name") or "College",
        "city_id": _as_int(city.get("id")),
        "city_name": city.get("name") or "",
        "state_id": _as_int(state.get("id")),
        "state_name": state.get("name") or "",
        "college_type": ctype.get("name") or "",
        "stream_id": _as_int(stream.get("id")),
        "stream_name": stream.get("name") or "",
        "substream_id": _as_int(substream.get("id")),
        "substream_name": substream.get("name") or "",
        "gender_id": _as_int(gender.get("id")),
        "gender_name": gender.get("name") or gender.get("gender") or "",
        "category_id": _as_int(category.get("id")),
        "category_name": category.get("name") or "",
        "duration_id": _as_int(duration.get("id")),
        "duration_value": duration.get("duration") or duration.get("name") or "",
        "fee_ids": fee_ids,
        "avg_fees_array": avg_fees,
        "entrance_exam_ids": exam_ids,
        "course_id": None,
        "course_name": "",
    }


def resolve_college_type_name(selected_filters: Dict[str, Any]) -> Dict[str, Any]:
    """Upstream ignores college_type when `name` is missing — fill it from /filters/."""
    selected = dict(selected_filters or {})
    college_type = selected.get("college_type")
    if not isinstance(college_type, dict):
        return selected
    type_id = _as_int(college_type.get("id"))
    if type_id is None or college_type.get("name"):
        return selected
    try:
        payload = fetch_filters({"nationwide": True})
        options = ((payload.get("filters") or {}).get("static") or {}).get("college_type") or []
        for opt in options:
            if _as_int(opt.get("id")) == type_id and opt.get("name"):
                selected["college_type"] = {"id": type_id, "name": str(opt.get("name"))}
                break
    except Exception as e:
        logger.debug("college_type name resolve failed: %s", e)
    return selected


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_int_list(values: Sequence[Any]) -> List[int]:
    result = []
    for value in values or []:
        parsed = _as_int(value)
        if parsed is not None:
            result.append(parsed)
    return result


def _empty_result_facet_bucket() -> Dict[str, Any]:
    return {
        "state_ids": Counter(),
        "city_ids": Counter(),
        "stream_ids": Counter(),
        "substream_ids": Counter(),
        "course_ids": Counter(),
        "college_type_names": Counter(),
        "category_ids": Counter(),
        "duration_ids": Counter(),
        "fee_ids": Counter(),
        "exam_ids": Counter(),
        "gender_ids": Counter(),
    }


def accumulate_result_facets(
    bucket: Dict[str, Any],
    items: Sequence[Dict[str, Any]],
    seen_college_ids: Optional[set] = None,
) -> None:
    """Collect filter value frequencies from list-view rows."""
    for item in items or []:
        college_key = item.get("college_id")
        if college_key is None:
            college_key = item.get("id")
        if seen_college_ids is not None and college_key is not None:
            if college_key in seen_college_ids:
                continue
            seen_college_ids.add(college_key)

        sid = _as_int(item.get("state_id"))
        if sid is not None:
            bucket["state_ids"][sid] += 1
        cid = _as_int(item.get("city_id"))
        if cid is not None:
            bucket["city_ids"][cid] += 1
        stream_id = _as_int(item.get("stream_id"))
        if stream_id is not None:
            bucket["stream_ids"][stream_id] += 1
        sub_id = _as_int(item.get("substream_id"))
        if sub_id is not None:
            bucket["substream_ids"][sub_id] += 1
        course_id = _as_int(item.get("course_id"))
        if course_id is not None and course_id != 0:
            bucket["course_ids"][course_id] += 1
        college_type = (item.get("college_type") or "").strip()
        if college_type:
            bucket["college_type_names"][college_type] += 1
        cat_id = _as_int(item.get("category_id"))
        if cat_id is not None:
            bucket["category_ids"][cat_id] += 1
        duration_id = _as_int(item.get("duration_id"))
        if duration_id is not None:
            bucket["duration_ids"][duration_id] += 1
        gender_id = _as_int(item.get("gender_id"))
        if gender_id is not None:
            bucket["gender_ids"][gender_id] += 1
        for fee_id in item.get("fee_ids") or []:
            parsed = _as_int(fee_id)
            if parsed is not None:
                bucket["fee_ids"][parsed] += 1
        for exam_id in item.get("entrance_exam_ids") or []:
            parsed = _as_int(exam_id)
            if parsed is not None:
                bucket["exam_ids"][parsed] += 1


def _narrow_options_by_results(
    options: Sequence[Dict[str, Any]],
    counts: Counter,
    selected_ids: Optional[set] = None,
    match_by_name: bool = False,
    name_counts: Optional[Counter] = None,
) -> List[Dict[str, Any]]:
    """Keep options present in current results (plus currently selected)."""
    selected_ids = selected_ids or set()
    name_counts = name_counts or Counter()
    narrowed = []
    for option in options or []:
        oid = _as_int(option.get("id"))
        if oid is None:
            continue
        if match_by_name:
            label = (option.get("name") or "").strip()
            count = int(name_counts.get(label, 0))
            keep = count > 0 or oid in selected_ids
        else:
            count = int(counts.get(oid, 0))
            keep = count > 0 or oid in selected_ids
        if not keep:
            continue
        row = dict(option)
        row["_result_count"] = count
        narrowed.append(row)
    # Prefer options with results first, selected always kept above.
    narrowed.sort(key=lambda row: (0 if row.get("_result_count") else 1, -int(row.get("_result_count") or 0), str(row.get("name") or row.get("id"))))
    return narrowed


def get_college_list_context_from_api(request) -> Dict[str, Any]:
    """Build template context for /colleges/ using the Indian colleges API."""
    state_ids = _as_int_list(request.GET.getlist("state"))
    city_ids = _as_int_list(request.GET.getlist("city"))
    stream_ids = _as_int_list(request.GET.getlist("stream"))
    sub_stream_ids = _as_int_list(request.GET.getlist("sub_stream"))
    course_ids = _as_int_list(request.GET.getlist("course"))
    course_type_ids = _as_int_list(request.GET.getlist("course_type"))
    college_type_ids = _as_int_list(request.GET.getlist("college_type"))
    avg_fee_ids = _as_int_list(request.GET.getlist("avg_fee"))
    course_duration_ids = _as_int_list(request.GET.getlist("course_duration"))
    college_category_ids = _as_int_list(request.GET.getlist("college_category"))
    entrance_exam_ids = _as_int_list(request.GET.getlist("entrance_exam"))
    gender_ids = _as_int_list(request.GET.getlist("gender"))

    state_id = state_ids[0] if state_ids else None
    stream_id = stream_ids[0] if stream_ids else None
    course_id = course_ids[0] if course_ids else None
    course_type_id = course_type_ids[0] if course_type_ids else None
    college_type_id = college_type_ids[0] if college_type_ids else None
    avg_fee_id = avg_fee_ids[0] if avg_fee_ids else None
    course_duration_id = course_duration_ids[0] if course_duration_ids else None
    college_category_id = college_category_ids[0] if college_category_ids else None
    gender_id = gender_ids[0] if gender_ids else None

    # Dependent filters only make sense with their parents selected.
    if not state_id:
        city_ids = []
    if not stream_id:
        sub_stream_ids = []
        course_id = None

    selected_filters = build_selected_filters(
        state_id=state_id,
        city_ids=city_ids,
        stream_id=stream_id,
        sub_stream_ids=sub_stream_ids,
        course_id=course_id,
        course_type_id=course_type_id,
        college_type_id=college_type_id,
        avg_fee_id=avg_fee_id,
        course_duration_id=course_duration_id,
        college_category_id=college_category_id,
        entrance_exam_ids=entrance_exam_ids,
        gender_id=gender_id,
    )
    # API requires college_type.name; id-only silently drops the filter.
    if college_type_id:
        selected_filters = resolve_college_type_name(selected_filters)

    page = _as_int(request.GET.get("page")) or 1
    page_size = _as_int(request.GET.get("page_size")) or DEFAULT_PAGE_SIZE
    sort_order = (request.GET.get("sort_order") or "asc").lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"
    search_query = (request.GET.get("q") or "").strip()
    search_lower = search_query.lower()
    # nationwide=True is a default anti-geo flag, not a user filter.
    user_applied_filters = bool(search_lower) or any(
        key != "nationwide" for key in (selected_filters or {})
    )

    context_cache_key = _cache_key(
        "list_ctx",
        {
            "selected_filters": selected_filters,
            "page": page,
            "page_size": page_size,
            "sort_order": sort_order,
            "q": search_query,
        },
    )
    cache_backend = _college_api_cache()
    try:
        cached_ctx = cache_backend.get(context_cache_key)
        if isinstance(cached_ctx, dict) and cached_ctx.get("use_indian_colleges_api"):
            return cached_ctx
    except Exception:
        pass

    # Only one worker builds a cold context; others wait briefly for cache.
    lock_key = f"{context_cache_key}:lock"
    got_lock = False
    try:
        got_lock = bool(cache_backend.add(lock_key, "1", 45))
    except Exception:
        got_lock = True
    if not got_lock:
        for _ in range(40):
            time.sleep(0.25)
            try:
                cached_ctx = cache_backend.get(context_cache_key)
                if isinstance(cached_ctx, dict) and cached_ctx.get("use_indian_colleges_api"):
                    return cached_ctx
            except Exception:
                break
        # Builder still slow — fall through and build (better than hanging forever).

    started = time.monotonic()

    # Facets/counts/options use enabled colleges only (Admission content enabled).
    enabled_facet_bucket = _empty_result_facet_bucket()
    enabled_seen_ids: set = set()
    enabled_ordered: List[Dict[str, Any]] = []
    list_payload: Dict[str, Any] = {}
    filters_payload: Dict[str, Any] = {}
    used_search_api = False

    # Prefer official search API for `q` (avoids scanning alphabetical list pages).
    search_hits: Optional[List[Dict[str, Any]]] = None
    if search_query:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_filters = pool.submit(fetch_filters, selected_filters)
            fut_search = pool.submit(fetch_college_search, search_query)
            remaining = max(1.0, LIST_BUILD_DEADLINE_SEC - (time.monotonic() - started))
            try:
                filters_payload = fut_filters.result(timeout=remaining)
                search_hits = fut_search.result(timeout=remaining)
            except Exception as exc:
                fut_filters.cancel()
                fut_search.cancel()
                raise RuntimeError(
                    f"Indian colleges upstream timed out or failed: {exc}"
                ) from exc

        if search_hits is not None:
            used_search_api = True

            def _load_search_hit(hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                cid = _as_int(hit.get("id"))
                if cid is None or not is_college_content_enabled(cid):
                    return None
                try:
                    base = fetch_college_base_details(cid)
                    if base.get("error"):
                        return None
                    return list_item_from_details(cid, base)
                except Exception:
                    return None

            hits = search_hits[:SEARCH_RESULT_LIMIT]
            with ThreadPoolExecutor(max_workers=min(10, len(hits) or 1)) as pool:
                for item in pool.map(_load_search_hit, hits):
                    if not item:
                        continue
                    college_key = item.get("college_id")
                    if college_key is not None and college_key in enabled_seen_ids:
                        continue
                    if college_key is not None:
                        enabled_seen_ids.add(college_key)
                    enabled_ordered.append(item)

            # Search API is name-only — apply active sidebar filters locally.
            if state_id:
                enabled_ordered = [
                    item for item in enabled_ordered if item.get("state_id") == state_id
                ]
            if city_ids:
                city_set = set(city_ids)
                enabled_ordered = [
                    item for item in enabled_ordered if item.get("city_id") in city_set
                ]
            if stream_id:
                enabled_ordered = [
                    item for item in enabled_ordered if item.get("stream_id") == stream_id
                ]
            if college_type_id:
                type_name = (
                    (selected_filters.get("college_type") or {}).get("name") or ""
                ).strip().lower()
                if type_name:
                    enabled_ordered = [
                        item
                        for item in enabled_ordered
                        if (item.get("college_type") or "").strip().lower() == type_name
                    ]

    if not used_search_api:
        # Kick filters + first list pages in parallel (biggest latency win on cold load).
        fetch_size = 50 if user_applied_filters else 48
        # Parallel page batches keep totals useful without serial multi-second scans
        # that push nginx past ~30s and return 502 on demo under load.
        max_upstream_pages = 12 if user_applied_filters else 8
        batch_size = 4

        def _fetch_pages(page_nos: Sequence[int]) -> Dict[int, Dict[str, Any]]:
            if not page_nos:
                return {}
            with ThreadPoolExecutor(max_workers=len(page_nos)) as pool:
                futs = {
                    page_no: pool.submit(
                        fetch_colleges_list,
                        selected_filters,
                        page_no,
                        fetch_size,
                        "name",
                        sort_order,
                        True,
                    )
                    for page_no in page_nos
                }
                out: Dict[int, Dict[str, Any]] = {}
                for page_no, fut in futs.items():
                    remaining = max(
                        1.0, LIST_BUILD_DEADLINE_SEC - (time.monotonic() - started)
                    )
                    out[page_no] = fut.result(timeout=remaining)
                return out

        # Filters + first list batch in parallel.
        first_batch = list(range(1, min(batch_size, max_upstream_pages) + 1))
        with ThreadPoolExecutor(max_workers=1 + len(first_batch)) as pool:
            fut_filters = pool.submit(fetch_filters, selected_filters)
            list_futs = {
                page_no: pool.submit(
                    fetch_colleges_list,
                    selected_filters,
                    page_no,
                    fetch_size,
                    "name",
                    sort_order,
                    True,
                )
                for page_no in first_batch
            }
            remaining = max(1.0, LIST_BUILD_DEADLINE_SEC - (time.monotonic() - started))
            try:
                filters_payload = fut_filters.result(timeout=remaining)
                page_payloads = {}
                for page_no, fut in list_futs.items():
                    remaining = max(
                        1.0, LIST_BUILD_DEADLINE_SEC - (time.monotonic() - started)
                    )
                    page_payloads[page_no] = fut.result(timeout=remaining)
            except Exception as exc:
                for fut in list(list_futs.values()) + [fut_filters]:
                    fut.cancel()
                raise RuntimeError(
                    f"Indian colleges upstream timed out or failed: {exc}"
                ) from exc

        def _enabled_matching(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
            enabled_items = filter_enabled_college_items(items)
            if not search_lower:
                return enabled_items
            return [
                item
                for item in enabled_items
                if search_lower in (item.get("college_name") or "").lower()
                or search_lower in (item.get("city_name") or "").lower()
                or search_lower in (item.get("course_name") or "").lower()
            ]

        upstream_page = 0
        upstream_exhausted = False
        upstream_has_next = False

        def _ingest(payload: Dict[str, Any]) -> None:
            enabled_items = _enabled_matching(payload.get("data") or [])
            for item in enabled_items:
                college_key = item.get("college_id")
                if college_key is None:
                    college_key = item.get("id")
                if college_key is not None and college_key in enabled_seen_ids:
                    continue
                if college_key is not None:
                    enabled_seen_ids.add(college_key)
                enabled_ordered.append(item)

        def _ingest_ordered(payloads: Dict[int, Dict[str, Any]]) -> None:
            nonlocal list_payload, upstream_page, upstream_has_next, upstream_exhausted
            for page_no in sorted(payloads):
                list_payload = payloads[page_no] or {}
                upstream_page = page_no
                upstream_has_next = bool(list_payload.get("has_next"))
                _ingest(list_payload)
                if not upstream_has_next:
                    upstream_exhausted = True
                    break

        _ingest_ordered(page_payloads)

        while (
            not upstream_exhausted
            and upstream_page < max_upstream_pages
            and (time.monotonic() - started) < LIST_BUILD_DEADLINE_SEC
        ):
            next_start = upstream_page + 1
            next_end = min(max_upstream_pages, upstream_page + batch_size)
            if next_start > next_end:
                break
            try:
                _ingest_ordered(_fetch_pages(range(next_start, next_end + 1)))
            except Exception:
                break

    accumulate_result_facets(enabled_facet_bucket, enabled_ordered, None)

    start = max(page - 1, 0) * page_size
    end = start + page_size
    page_items = enabled_ordered[start:end]
    colleges = [adapt_college(item) for item in page_items]

    display_total = len(enabled_ordered)
    display_total_pages = (
        max(1, (display_total + page_size - 1) // page_size) if display_total else 1
    )
    has_next_page = end < display_total
    has_prev_page = start > 0

    # If the requested page is past what we collected, show the last available page.
    if page > 1 and not page_items and enabled_ordered:
        last_page = display_total_pages
        start = (last_page - 1) * page_size
        page_items = enabled_ordered[start : start + page_size]
        colleges = [adapt_college(item) for item in page_items]
        page = last_page
        has_next_page = False
        has_prev_page = page > 1

    page_obj = ApiPage(
        items=colleges,
        page=page,
        total=display_total,
        page_size=page_size,
        total_pages=display_total_pages,
        has_next=has_next_page,
        has_previous=has_prev_page,
    )

    static_filters = (filters_payload.get("filters") or {}).get("static") or {}
    dynamic_filters = (filters_payload.get("filters") or {}).get("dynamic") or {}

    # Selection state comes only from the request — do not adopt upstream IP/geo.
    selected_state_id = state_id
    selected_city_ids = set(city_ids)
    selected_stream_id = stream_id
    selected_sub_stream_ids = set(sub_stream_ids)
    selected_course_id = course_id
    selected_course_type_id = course_type_id
    selected_college_type_id = college_type_id
    selected_avg_fee_id = avg_fee_id
    selected_course_duration_id = course_duration_id
    selected_college_category_id = college_category_id
    selected_entrance_exam_ids = set(entrance_exam_ids)
    selected_gender_id = gender_id

    # Drop selected filter values that match zero enabled colleges.
    if any(enabled_facet_bucket.values()):
        selected_city_ids = {
            cid for cid in selected_city_ids if enabled_facet_bucket["city_ids"].get(cid, 0) > 0
        }
        selected_sub_stream_ids = {
            sid
            for sid in selected_sub_stream_ids
            if enabled_facet_bucket["substream_ids"].get(sid, 0) > 0
        }
        selected_entrance_exam_ids = {
            eid
            for eid in selected_entrance_exam_ids
            if enabled_facet_bucket["exam_ids"].get(eid, 0) > 0
        }
        if selected_stream_id and not enabled_facet_bucket["stream_ids"].get(selected_stream_id, 0):
            selected_stream_id = None
            selected_sub_stream_ids = set()
            selected_course_id = None
        if selected_course_id and not enabled_facet_bucket["course_ids"].get(selected_course_id, 0):
            selected_course_id = None
        if selected_college_type_id:
            # matched by name later in options; keep id if any college_type count exists for that option
            pass
        if selected_avg_fee_id and not enabled_facet_bucket["fee_ids"].get(selected_avg_fee_id, 0):
            selected_avg_fee_id = None
        if selected_course_duration_id and not enabled_facet_bucket["duration_ids"].get(
            selected_course_duration_id, 0
        ):
            selected_course_duration_id = None
        if selected_college_category_id and not enabled_facet_bucket["category_ids"].get(
            selected_college_category_id, 0
        ):
            selected_college_category_id = None
        if selected_gender_id and not enabled_facet_bucket["gender_ids"].get(selected_gender_id, 0):
            selected_gender_id = None
        # Keep selected_state_id even if sample missed it — state list stays full.

    def _option_label(option: Dict[str, Any]) -> str:
        # Course duration uses numeric years in `duration` (not a display name).
        if "duration" in option and option.get("duration") is not None and "name" not in option:
            try:
                years = int(option.get("duration"))
            except (TypeError, ValueError):
                years = None
            if years is not None:
                if years <= 0:
                    return "Flexible / Not specified"
                if years == 1:
                    return "1 Year"
                return f"{years} Years"

        for key in ("name", "fees", "gender", "label", "value", "title"):
            value = option.get(key)
            if value is None or value == "":
                continue
            text = str(value).replace("_", " ").strip()
            if key == "gender":
                lowered = text.lower()
                if lowered == "coed":
                    return "Co-ed"
                return text.title()
            if key == "fees":
                return text
            return text
        return str(option.get("id") or "")

    def option_rows(
        options: Sequence[Dict[str, Any]],
        selected_id: Optional[int],
        counts: Optional[Counter] = None,
    ):
        rows = []
        for option in options or []:
            oid = _as_int(option.get("id"))
            if oid is None:
                continue
            count = option.get("_result_count")
            if counts is not None:
                count = int(counts.get(oid, 0))
            rows.append(
                {
                    "id": oid,
                    "name": _option_label(option),
                    "selected": oid == selected_id,
                    "count": count,
                }
            )
        return rows

    def multi_option_rows(
        options: Sequence[Dict[str, Any]],
        selected_ids: set,
        counts: Optional[Counter] = None,
    ):
        rows = []
        for option in options or []:
            oid = _as_int(option.get("id"))
            if oid is None:
                continue
            count = option.get("_result_count")
            if counts is not None:
                count = int(counts.get(oid, 0))
            rows.append(
                {
                    "id": oid,
                    "name": _option_label(option),
                    "selected": oid in selected_ids,
                    "count": count,
                }
            )
        return rows

    # Narrow secondary sidebar options using enabled colleges only.
    # Keep the full State list so users can always switch region.
    has_result_signal = any(bucket for bucket in enabled_facet_bucket.values())

    raw_states = static_filters.get("state") or []
    raw_cities = dynamic_filters.get("cities") or []
    raw_streams = static_filters.get("stream") or []
    raw_sub_streams = dynamic_filters.get("sub_streams") or []
    raw_courses = dynamic_filters.get("courses") or []
    raw_course_types = static_filters.get("course_type") or []
    raw_college_types = static_filters.get("college_type") or []
    raw_avg_fees = static_filters.get("college_avg_fee") or []
    raw_durations = static_filters.get("course_duration") or []
    raw_categories = static_filters.get("college_category") or []
    raw_exams = static_filters.get("entrance_exams") or []
    raw_genders = static_filters.get("gender") or []

    if has_result_signal and user_applied_filters:
        raw_cities = _narrow_options_by_results(
            raw_cities, enabled_facet_bucket["city_ids"], selected_city_ids
        )
        raw_streams = _narrow_options_by_results(
            raw_streams,
            enabled_facet_bucket["stream_ids"],
            {selected_stream_id} if selected_stream_id else set(),
        )
        raw_sub_streams = _narrow_options_by_results(
            raw_sub_streams,
            enabled_facet_bucket["substream_ids"],
            selected_sub_stream_ids,
        )
        raw_courses = _narrow_options_by_results(
            raw_courses,
            enabled_facet_bucket["course_ids"],
            {selected_course_id} if selected_course_id else set(),
        )
        raw_college_types = _narrow_options_by_results(
            raw_college_types,
            Counter(),
            {selected_college_type_id} if selected_college_type_id else set(),
            match_by_name=True,
            name_counts=enabled_facet_bucket["college_type_names"],
        )
        raw_avg_fees = _narrow_options_by_results(
            raw_avg_fees,
            enabled_facet_bucket["fee_ids"],
            {selected_avg_fee_id} if selected_avg_fee_id else set(),
        )
        raw_durations = _narrow_options_by_results(
            raw_durations,
            enabled_facet_bucket["duration_ids"],
            {selected_course_duration_id} if selected_course_duration_id else set(),
        )
        raw_categories = _narrow_options_by_results(
            raw_categories,
            enabled_facet_bucket["category_ids"],
            {selected_college_category_id} if selected_college_category_id else set(),
        )
        raw_exams = _narrow_options_by_results(
            raw_exams, enabled_facet_bucket["exam_ids"], selected_entrance_exam_ids
        )
        raw_genders = _narrow_options_by_results(
            raw_genders,
            enabled_facet_bucket["gender_ids"],
            {selected_gender_id} if selected_gender_id else set(),
        )

    # Display counts from enabled colleges only (matches result cards).
    count_bucket = enabled_facet_bucket
    state_options = option_rows(raw_states, selected_state_id, count_bucket["state_ids"])
    city_options = multi_option_rows(raw_cities, selected_city_ids, count_bucket["city_ids"])
    stream_options = option_rows(raw_streams, selected_stream_id, count_bucket["stream_ids"])
    sub_stream_options = multi_option_rows(
        raw_sub_streams, selected_sub_stream_ids, count_bucket["substream_ids"]
    )
    course_options = option_rows(raw_courses, selected_course_id, count_bucket["course_ids"])
    course_type_options = option_rows(raw_course_types, selected_course_type_id)
    college_type_options = option_rows(raw_college_types, selected_college_type_id)
    avg_fee_options = option_rows(raw_avg_fees, selected_avg_fee_id, count_bucket["fee_ids"])
    course_duration_options = option_rows(
        raw_durations, selected_course_duration_id, count_bucket["duration_ids"]
    )
    college_category_options = option_rows(
        raw_categories, selected_college_category_id, count_bucket["category_ids"]
    )
    entrance_exam_options = multi_option_rows(
        raw_exams, selected_entrance_exam_ids, count_bucket["exam_ids"]
    )
    gender_options = option_rows(raw_genders, selected_gender_id, count_bucket["gender_ids"])

    for opt in college_type_options:
        opt["count"] = int(count_bucket["college_type_names"].get(opt["name"], 0) or 0)

    facets = SimpleNamespace(
        state=[(opt["name"], "", opt["selected"]) for opt in state_options],
        city=[(opt["name"], "", opt["selected"]) for opt in city_options],
        country=[],
    )

    from urllib.parse import quote, urlencode

    # Current query as ordered multi-value pairs (used for chips + pagination).
    query_pairs: List[Tuple[str, str]] = []
    if search_query:
        query_pairs.append(("q", search_query))
    if selected_state_id:
        query_pairs.append(("state", str(selected_state_id)))
    for cid in sorted(selected_city_ids):
        query_pairs.append(("city", str(cid)))
    if selected_stream_id:
        query_pairs.append(("stream", str(selected_stream_id)))
    for sid in sorted(selected_sub_stream_ids):
        query_pairs.append(("sub_stream", str(sid)))
    if selected_course_id:
        query_pairs.append(("course", str(selected_course_id)))
    if selected_course_type_id:
        query_pairs.append(("course_type", str(selected_course_type_id)))
    if selected_college_type_id:
        query_pairs.append(("college_type", str(selected_college_type_id)))
    if selected_avg_fee_id:
        query_pairs.append(("avg_fee", str(selected_avg_fee_id)))
    if selected_course_duration_id:
        query_pairs.append(("course_duration", str(selected_course_duration_id)))
    if selected_college_category_id:
        query_pairs.append(("college_category", str(selected_college_category_id)))
    for eid in sorted(selected_entrance_exam_ids):
        query_pairs.append(("entrance_exam", str(eid)))
    if selected_gender_id:
        query_pairs.append(("gender", str(selected_gender_id)))
    if sort_order != "asc":
        query_pairs.append(("sort_order", sort_order))

    # Removing some keys also clears dependent filters.
    clear_with_key = {
        "state": {"state", "city"},
        "stream": {"stream", "sub_stream", "course"},
    }

    def query_without(remove_key: str, remove_value: Optional[str] = None) -> str:
        drop_keys = clear_with_key.get(remove_key, {remove_key})
        remaining = []
        for key, value in query_pairs:
            if key in drop_keys and remove_key in ("state", "stream") and key != remove_key:
                # Dependent keys dropped entirely when parent is removed.
                continue
            if key == remove_key:
                if remove_value is None or value == str(remove_value):
                    continue
            remaining.append((key, value))
        return urlencode(remaining)

    active_filters = []
    if search_query:
        active_filters.append(
            {
                "label": search_query,
                "param": "q",
                "value": search_query,
                "kind": "search",
                "remove_url": "?" + query_without("q", search_query)
                if query_without("q", search_query)
                else "?",
            }
        )

    chip_sources = [
        ("state", state_options, False),
        ("city", city_options, True),
        ("stream", stream_options, False),
        ("sub_stream", sub_stream_options, True),
        ("course", course_options, False),
        ("course_type", course_type_options, False),
        ("college_type", college_type_options, False),
        ("avg_fee", avg_fee_options, False),
        ("course_duration", course_duration_options, False),
        ("college_category", college_category_options, False),
        ("entrance_exam", entrance_exam_options, True),
        ("gender", gender_options, False),
    ]
    for param, options, _multi in chip_sources:
        for opt in options:
            if not opt["selected"]:
                continue
            remove_qs = query_without(param, str(opt["id"]))
            active_filters.append(
                {
                    "label": opt["name"],
                    "param": param,
                    "value": opt["id"],
                    "kind": "filter",
                    "remove_url": f"?{remove_qs}" if remove_qs else "?",
                }
            )

    active_labels = [chip["label"] for chip in active_filters]
    selected_count = len(active_filters)

    result = {
        "use_indian_colleges_api": True,
        "colleges": page_obj,
        "total_results": display_total,
        "page_size": page_size,
        "search_query": search_query,
        "selected_filter_count": selected_count,
        "facets_filter": SimpleNamespace(facets=facets),
        "api_filters": {
            "state": state_options,
            "city": city_options,
            "stream": stream_options,
            "sub_stream": sub_stream_options,
            "course": course_options,
            "course_type": course_type_options,
            "college_type": college_type_options,
            "avg_fee": avg_fee_options,
            "course_duration": course_duration_options,
            "college_category": college_category_options,
            "entrance_exam": entrance_exam_options,
            "gender": gender_options,
        },
        "has_selected_state": bool(selected_state_id),
        "has_selected_stream": bool(selected_stream_id),
        "selected_filters": selected_filters,
        "location_debug": list_payload.get("location_debug") or {},
        "sort_order": sort_order,
        "query_list": active_labels,
        "active_filters": active_filters,
        "get_updated_url": urlencode(query_pairs),
        "bookmarked_college_ids": [],
        "bookmarked_college_slugs": [],
        "api_error": None,
    }
    try:
        _college_api_cache().set(context_cache_key, result, CONTEXT_CACHE_TTL)
    except Exception:
        pass
    finally:
        if got_lock:
            try:
                _college_api_cache().delete(lock_key)
            except Exception:
                pass
    return result
