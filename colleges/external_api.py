"""Client for the Indian colleges listing API (canamuni upstream)."""

from __future__ import annotations

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 12
ENABLED_CONTENT_STATUSES = {"COMPLETED", "COMPLETE", "SUCCESS"}
ENABLED_VALIDATION_STATES = {"approved"}


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


def _request_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
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


def _post_json(path: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    return _request_json("POST", path, payload=payload, timeout=timeout)


def _get_json(path: str, timeout: int = 30) -> Dict[str, Any]:
    return _request_json("GET", path, timeout=timeout)


def fetch_college_base_details(college_id: int) -> Dict[str, Any]:
    return _get_json(f"/colleges/college-details/?id={int(college_id)}")


def fetch_college_tab_details(college_id: int, tab_name: str) -> Dict[str, Any]:
    return _get_json(
        f"/colleges/college-details/?id={int(college_id)}&tab_name={tab_name}"
    )


def fetch_courses_fees_streams(college_id: int) -> Dict[str, Any]:
    return _get_json(f"/colleges/{int(college_id)}/courses-fees/streams/")


def fetch_courses_fees_stream(college_id: int, stream_slug: str) -> Dict[str, Any]:
    slug = (stream_slug or "").strip("/")
    return _get_json(
        f"/colleges/{int(college_id)}/courses-fees/streams/{slug}/"
    )


def resolve_detail_tab(tab: Optional[str]) -> Dict[str, str]:
    key = (tab or "admission").strip("/").lower()
    return _TAB_BY_PATH.get(key) or _TAB_BY_PATH["admission"]


def is_tab_content_enabled(tab_data: Optional[Dict[str, Any]]) -> bool:
    """Return True when upstream marks tab content as enabled/publishable."""
    if not isinstance(tab_data, dict) or tab_data.get("error"):
        return False

    markdown = (tab_data.get("markdown_content") or "").strip()
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
    """List gate: college is shown only when Admission content is enabled."""
    if not college_id:
        return False
    try:
        payload = fetch_college_tab_details(int(college_id), "admission")
        if payload.get("error"):
            return False
        return is_tab_content_enabled(payload.get("admission"))
    except Exception as e:
        logger.debug("admission status check failed for %s: %s", college_id, e)
        return False


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


def render_markdown_html(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    try:
        import markdown
        import bleach

        html = markdown.markdown(
            markdown_text,
            extensions=["extra", "sane_lists", "nl2br", "tables"],
        )
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
                "blockquote",
            }
        )
        return bleach.clean(
            html,
            tags=allowed_tags,
            attributes={
                **bleach.sanitizer.ALLOWED_ATTRIBUTES,
                "a": ["href", "title", "rel", "target"],
                "td": ["colspan", "rowspan"],
                "th": ["colspan", "rowspan"],
            },
            strip=True,
        )
    except Exception:
        # Fallback: plain text with line breaks
        from django.utils.html import escape
        from django.utils.safestring import mark_safe

        return mark_safe(escape(markdown_text).replace("\n", "<br>"))


def get_college_detail_context_from_api(
    college_id: int,
    tab: Optional[str] = None,
    stream_slug: Optional[str] = None,
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
    if not enabled_tabs:
        raise CollegeContentDisabled(
            f"College {college_id} has no enabled content tabs."
        )

    enabled_paths = {item["path"] for item in enabled_tabs}
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

    if api_tab == "inner_course":
        streams_payload = fetch_courses_fees_streams(college_id)
        if streams_payload.get("error"):
            tab_error = streams_payload.get("error")
        streams = streams_payload.get("streams") or []
        if not selected_stream and streams:
            selected_stream = streams[0].get("slug")
        if selected_stream:
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
                tab_markdown = tab_data.get("markdown_content") or ""
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
        "is_courses_tab": api_tab == "inner_course",
        "streams": streams,
        "courses": courses,
        "selected_stream": selected_stream,
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

    page = _as_int(request.GET.get("page")) or 1
    page_size = _as_int(request.GET.get("page_size")) or DEFAULT_PAGE_SIZE
    sort_order = (request.GET.get("sort_order") or "asc").lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"
    search_query = (request.GET.get("q") or "").strip()
    search_lower = search_query.lower()

    filters_payload = fetch_filters(selected_filters)
    user_applied_filters = bool(selected_filters) or bool(search_lower)

    # Facets/counts/options use enabled colleges only (Admission content enabled).
    enabled_facet_bucket = _empty_result_facet_bucket()
    enabled_seen_ids: set = set()

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

    # Always walk upstream from page 1 so totals/facets stay stable across pagination.
    # With filters: scan until exhausted (capped) for an accurate enabled total.
    # Without filters: scan a fixed upstream window so page changes don't rewrite counts.
    enabled_ordered: List[Dict[str, Any]] = []
    list_payload: Dict[str, Any] = {}
    upstream_page = 1
    upstream_exhausted = False
    upstream_has_next = False
    fetch_size = 50 if user_applied_filters else 36
    max_upstream_pages = 20 if user_applied_filters else 4

    while upstream_page <= max_upstream_pages:
        list_payload = fetch_colleges_list(
            selected_filters=selected_filters,
            page=upstream_page,
            page_size=fetch_size,
            sort_by="name",
            sort_order=sort_order,
            detail_view=True,
        )
        upstream_has_next = bool(list_payload.get("has_next"))
        enabled_items = _enabled_matching(list_payload.get("data") or [])
        for item in enabled_items:
            college_key = item.get("college_id")
            if college_key is None:
                college_key = item.get("id")
            if college_key is not None and college_key in enabled_seen_ids:
                continue
            if college_key is not None:
                enabled_seen_ids.add(college_key)
            enabled_ordered.append(item)
        if not upstream_has_next:
            upstream_exhausted = True
            break
        upstream_page += 1

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

    return {
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
