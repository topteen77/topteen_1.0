"""Indian college course detail helpers (separate course page)."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from django.core.cache import caches

logger = logging.getLogger(__name__)

STREAM_NAME_TO_ID = {
    "agriculture": 1,
    "animation": 1113,
    "architecture": 2,
    "arts": 3,
    "aviation": 4,
    "commerce": 5,
    "computer applications": 6,
    "dental": 7,
    "design": 8,
    "education": 9,
    "engineering": 10,
    "hotel management": 11,
    "law": 12,
    "management": 13,
    "mass communications": 14,
    "medical": 15,
    "paramedical": 16,
    "pharmacy": 17,
    "science": 18,
    "veterinary sciences": 19,
    "vocational courses": 20,
}

# Short labels used on college detail pages → filter catalog phrasing.
_COURSE_ALIASES = {
    "b.com": "bachelor of commerce",
    "bcom": "bachelor of commerce",
    "b.com general": "bachelor of commerce",
    "bcom general": "bachelor of commerce",
    "b.sc": "bachelor of science",
    "bsc": "bachelor of science",
    "b.a": "bachelor of arts",
    "ba": "bachelor of arts",
    "bba": "bachelor of business administration",
    "b.tech": "bachelor of technology",
    "btech": "bachelor of technology",
    "m.com": "master of commerce",
    "mcom": "master of commerce",
    "m.sc": "master of science",
    "mba": "master of business administration",
}

_STOP = {
    "of",
    "and",
    "the",
    "in",
    "with",
    "for",
    "general",
    "hons",
    "honours",
    "honors",
}

COLLEGES_CACHE_TTL = 180


def _course_cache():
    try:
        return caches["roster"]
    except Exception:
        from django.core.cache import cache

        return cache


def stream_id_from_name(stream_name: str) -> Optional[int]:
    key = (stream_name or "").strip().lower()
    if not key:
        return None
    return STREAM_NAME_TO_ID.get(key)


def _normalize_course_text(value: str) -> str:
    text = (value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[\[\]\{\}\(\)/,._\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text in _COURSE_ALIASES:
        text = _COURSE_ALIASES[text]
    # Expand leading short forms: "b com general" → bachelor of commerce …
    for short, full in _COURSE_ALIASES.items():
        short_n = re.sub(r"[.\s]+", " ", short).strip()
        if text == short_n or text.startswith(short_n + " "):
            rest = text[len(short_n) :].strip()
            text = f"{full} {rest}".strip()
            break
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: str) -> set:
    return {
        tok
        for tok in _normalize_course_text(value).split()
        if tok and tok not in _STOP and len(tok) > 1
    }


def _best_course_match(
    course_name: str, options: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Match detail-page course labels to upstream filter course names."""
    raw = (course_name or "").strip()
    if not raw or not options:
        return None

    name_l = raw.lower()
    norm = _normalize_course_text(raw)
    want = _tokens(raw)
    # Subject-like tokens matter more than generic degree words.
    subject_want = want - {
        "bachelor",
        "master",
        "arts",
        "science",
        "commerce",
        "degree",
        "diploma",
        "certificate",
        "ba",
        "bsc",
        "bcom",
        "ma",
        "msc",
        "ug",
        "pg",
    }

    exact = None
    contains = None
    best: Optional[Tuple[float, Dict[str, Any]]] = None

    for item in options:
        item_name = (item.get("name") or "").strip()
        if not item_name:
            continue
        item_l = item_name.lower()
        item_norm = _normalize_course_text(item_name)

        if item_l == name_l or item_norm == norm:
            exact = item
            break
        if name_l in item_l or item_l in name_l or norm in item_norm or item_norm in norm:
            if contains is None:
                contains = item

        have = _tokens(item_name)
        if not want or not have:
            continue
        overlap = len(want & have)
        if overlap <= 0:
            continue
        score = overlap / float(max(len(want), 1))
        # Prefer catalog rows that include the core degree tokens.
        if "bachelor" in have and "bachelor" in want:
            score += 0.1
        if "commerce" in have and "commerce" in want:
            score += 0.15
        if "science" in have and "science" in want:
            score += 0.15
        if "arts" in have and "arts" in want:
            score += 0.1
        # Strongly prefer subject overlap (e.g. Economics).
        if subject_want:
            sub_hit = len(subject_want & have)
            if sub_hit:
                score += 0.45 * (sub_hit / float(len(subject_want)))
            else:
                score -= 0.25
        if best is None or score > best[0]:
            best = (score, item)

    if exact:
        return exact
    if best and best[0] >= 0.5:
        return best[1]
    # Prefer a subject-aware best match over a weak generic contains match.
    if best and best[0] >= 0.4:
        return best[1]
    if contains and not subject_want:
        return contains
    if contains and subject_want:
        contain_tokens = _tokens(contains.get("name") or "")
        if subject_want & contain_tokens:
            return contains
    return best[1] if best and best[0] >= 0.34 else None


def _college_courses_tab_url(
    college_id: int, stream_slug: str = "", course_slug: str = ""
) -> str:
    url = f"/colleges/institute/{int(college_id)}/courses/"
    params = {}
    slug = (stream_slug or "").strip().strip("/")
    cslug = (course_slug or "").strip().strip("/")
    if slug:
        params["stream"] = slug
    if cslug:
        params["course"] = cslug
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def find_active_course_in_college(
    college_id: int,
    course_name: str,
    *,
    course_slug: str = "",
    stream_slug: str = "",
    stream_name: str = "",
    min_score: float = 0.72,
) -> Optional[Dict[str, Any]]:
    """Return match info when this college's courses tab lists the course."""
    from colleges.external_api import (
        _course_label_score,
        _iter_college_stream_courses,
        _stream_slug_candidates,
        is_courses_tab_enabled,
    )

    try:
        cid = int(college_id)
    except (TypeError, ValueError):
        return None
    if not is_courses_tab_enabled(cid):
        return None

    want_slug = (course_slug or "").strip().strip("/")
    want_name = (course_name or "").strip()
    if not want_slug and not want_name:
        return None

    rows = _iter_college_stream_courses(
        cid, _stream_slug_candidates(stream_slug, stream_name)
    )
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for item in rows:
        if not isinstance(item, dict):
            continue
        nested = item.get("course") if isinstance(item.get("course"), dict) else {}
        item_slug = (nested.get("slug") or "").strip()
        item_name = (item.get("name") or nested.get("name") or "").strip()
        item_stream = (item.get("_stream_slug") or nested.get("stream_slug") or "").strip()
        if want_slug and item_slug and item_slug == want_slug:
            return {
                "course_slug": item_slug,
                "course_name": item_name or want_name,
                "stream_slug": item_stream or stream_slug,
                "score": 1.0,
            }
        score = _course_label_score(want_name, item_name) if want_name else 0.0
        if score > best_score and item_slug:
            best_score = score
            best = {
                "course_slug": item_slug,
                "course_name": item_name or want_name,
                "stream_slug": item_stream or stream_slug,
                "score": score,
            }
    if best and best_score >= min_score:
        return best
    return None


def get_colleges_for_course(
    course_name: str,
    *,
    stream_name: str = "",
    stream_slug: str = "",
    course_slug: str = "",
    limit: int = 12,
) -> Dict[str, Any]:
    """Resolve colleges that actively list this course on their Courses tab.

    Links open the college Courses tab with stream + course selected.
    """
    name = (course_name or "").strip()
    if not name:
        return {"colleges": [], "filter_query": "", "course_filter_id": None}

    stream_id = stream_id_from_name(stream_name)
    stream_slug = (stream_slug or "").strip().strip("/")
    course_slug = (course_slug or "").strip().strip("/")
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in name.lower())[:80]
    cache_key = (
        f"indian_course_colleges:v6:{stream_id or 0}:{safe_name}:"
        f"{stream_slug or '-'}:{course_slug or '-'}:{int(limit)}"
    )
    try:
        cached = _course_cache().get(cache_key)
        # Reuse hits and confirmed empty misses.
        if isinstance(cached, dict) and "colleges" in cached:
            return cached
    except Exception:
        pass

    colleges: List[Dict[str, Any]] = []
    filter_query = urlencode({"q": name})
    course_filter_id = None
    matched_name = name
    target_limit = max(1, min(int(limit or 12), 24))
    # Pull extra upstream rows; many filter hits lack this course on courses tab.
    fetch_limit = max(target_limit * 4, 32)

    try:
        from colleges.external_api import (
            build_selected_filters,
            fetch_colleges_list,
            fetch_filters,
            fetch_college_search,
        )
        from concurrent.futures import ThreadPoolExecutor

        selected_filters: Dict[str, Any] = {"nationwide": True}
        raw_courses: List[Dict[str, Any]] = []
        if stream_id:
            selected_filters["stream"] = {"id": int(stream_id)}
            filters_payload = fetch_filters(selected_filters)
            raw_courses = (
                ((filters_payload.get("filters") or {}).get("dynamic") or {}).get(
                    "courses"
                )
                or []
            )
        match = _best_course_match(name, raw_courses)

        candidates: List[Dict[str, Any]] = []
        if match and match.get("id"):
            course_filter_id = int(match["id"])
            matched_name = (match.get("name") or name).strip()
            selected = build_selected_filters(
                stream_id=stream_id,
                course_id=course_filter_id,
                course_name=matched_name,
            )
            filter_query = urlencode(
                {"stream": stream_id, "course": course_filter_id}
            )
            list_payload = fetch_colleges_list(
                selected_filters=selected,
                page=1,
                page_size=fetch_limit,
                detail_view=True,
                sort_by="college_name",
                sort_order="asc",
            )
            rows = list_payload.get("data") or list_payload.get("results") or []
            for row in rows:
                cid = row.get("college_id")
                if not cid:
                    continue
                candidates.append(
                    {
                        "id": int(cid),
                        "name": row.get("college_name") or f"College {cid}",
                        "city": row.get("city_name") or "",
                        "state": row.get("state_name") or "",
                        "type": row.get("college_type") or "",
                    }
                )

        # Fallback: official search by course label when filter match is empty.
        if not candidates:
            subject_bits = [
                tok
                for tok in _tokens(name)
                if tok
                not in {
                    "bachelor",
                    "master",
                    "arts",
                    "science",
                    "commerce",
                    "degree",
                    "diploma",
                    "certificate",
                    "ba",
                    "bsc",
                    "bcom",
                    "ma",
                    "msc",
                    "ug",
                    "pg",
                }
            ]
            search_queries = [matched_name, name]
            if subject_bits:
                search_queries.append(" ".join(subject_bits))
                search_queries.append(f"BA {' '.join(subject_bits)}")
            seen_ids = set()
            for qtry in search_queries:
                qtry = (qtry or "").strip()
                if not qtry:
                    continue
                search_rows = fetch_college_search(qtry) or []
                if not search_rows:
                    continue
                filter_query = urlencode({"q": qtry})
                for row in search_rows:
                    cid = row.get("id") or row.get("college_id")
                    if not cid or int(cid) in seen_ids:
                        continue
                    seen_ids.add(int(cid))
                    candidates.append(
                        {
                            "id": int(cid),
                            "name": row.get("name")
                            or row.get("college_name")
                            or f"College {cid}",
                            "city": row.get("city_name") or row.get("city") or "",
                            "state": row.get("state_name") or row.get("state") or "",
                            "type": row.get("college_type") or "",
                        }
                    )
                    if len(candidates) >= fetch_limit:
                        break
                if candidates:
                    break

        # Keep only colleges that actively list this course on the courses tab.
        if candidates:
            def _match_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                found = find_active_course_in_college(
                    row.get("id"),
                    matched_name or name,
                    course_slug=course_slug,
                    stream_slug=stream_slug,
                    stream_name=stream_name,
                )
                if not found:
                    return None
                out = dict(row)
                out["course_slug"] = found.get("course_slug") or course_slug
                out["stream_slug"] = found.get("stream_slug") or stream_slug
                out["url"] = _college_courses_tab_url(
                    int(row["id"]),
                    out.get("stream_slug") or "",
                    out.get("course_slug") or "",
                )
                return out

            batch_size = 5
            for i in range(0, len(candidates), batch_size):
                chunk = candidates[i : i + batch_size]
                with ThreadPoolExecutor(max_workers=min(5, len(chunk) or 1)) as pool:
                    matched_rows = list(pool.map(_match_row, chunk))
                colleges.extend(row for row in matched_rows if row)
                if len(colleges) >= target_limit:
                    colleges = colleges[:target_limit]
                    break
    except Exception:
        logger.warning("get_colleges_for_course failed", exc_info=True)

    result = {
        "colleges": colleges,
        "filter_query": filter_query,
        "course_filter_id": course_filter_id,
        "matched_course_name": matched_name,
    }
    try:
        _course_cache().set(cache_key, result, COLLEGES_CACHE_TTL)
    except Exception:
        pass
    return result


def has_active_course_offerings(
    course_name: str,
    *,
    stream_name: str = "",
    stream_slug: str = "",
    course_id: Optional[int] = None,
) -> bool:
    """True when at least one college with an active courses tab offers this course.

    Cached per course/stream so matched-course lists can filter cheaply.
    """
    name = (course_name or "").strip()
    if not name:
        return False
    stream_id = stream_id_from_name(stream_name) or 0
    safe = "".join(ch if ch.isalnum() else "_" for ch in name.lower())[:80]
    cache_key = (
        f"indian_course_has_offering:v1:{stream_id}:"
        f"{int(course_id) if course_id else 0}:{safe}"
    )
    try:
        cached = _course_cache().get(cache_key)
        if cached is True or cached is False:
            return bool(cached)
    except Exception:
        pass

    try:
        payload = get_colleges_for_course(
            name,
            stream_name=stream_name,
            stream_slug=stream_slug,
            course_slug="",
            limit=1,
        )
        ok = bool(payload.get("colleges"))
    except Exception:
        ok = False

    try:
        _course_cache().set(cache_key, ok, COLLEGES_CACHE_TTL)
    except Exception:
        pass
    return ok
