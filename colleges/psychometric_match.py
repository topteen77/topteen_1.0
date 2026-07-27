"""Psychometric (RIASEC) → Indian college stream / course matching.

Uses current student batteries only (not central test):
1. Class 11–12 Career Interest Inventory (post_matric TestResult)
2. Class 10 Career Interest (Results test2) if no 12th interest result

Speed rules:
- Profile resolution is local DB only.
- Courses live on a dedicated page and use one cached /filters/ call.
- College list SSR never calls upstream for psychometric previews.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import caches

logger = logging.getLogger(__name__)

PROFILE_CACHE_TTL = 120
COURSES_CACHE_TTL = 300
OFFERING_IDS_CACHE_TTL = 300


def _match_cache():
    try:
        return caches["roster"]
    except Exception:
        from django.core.cache import cache

        return cache

# Upstream stream ids from POST /colleges/filters/ (static.stream).
RIASEC_TO_STREAMS: Dict[str, List[Dict[str, Any]]] = {
    "realistic": [
        {"id": 10, "name": "Engineering"},
        {"id": 20, "name": "Vocational Courses"},
        {"id": 1, "name": "Agriculture"},
        {"id": 4, "name": "Aviation"},
    ],
    "investigative": [
        {"id": 18, "name": "Science"},
        {"id": 15, "name": "Medical"},
        {"id": 10, "name": "Engineering"},
        {"id": 17, "name": "Pharmacy"},
    ],
    "artistic": [
        {"id": 3, "name": "Arts"},
        {"id": 8, "name": "Design"},
        {"id": 1113, "name": "Animation"},
        {"id": 14, "name": "Mass Communications"},
    ],
    "social": [
        {"id": 9, "name": "Education"},
        {"id": 12, "name": "Law"},
        {"id": 16, "name": "Paramedical"},
        {"id": 15, "name": "Medical"},
    ],
    "enterprising": [
        {"id": 13, "name": "Management"},
        {"id": 5, "name": "Commerce"},
        {"id": 11, "name": "Hotel Management"},
        {"id": 14, "name": "Mass Communications"},
    ],
    "conventional": [
        {"id": 5, "name": "Commerce"},
        {"id": 13, "name": "Management"},
        {"id": 6, "name": "Computer Applications"},
        {"id": 20, "name": "Vocational Courses"},
    ],
}

_RIASEC_LABELS = {
    "realistic": "Realistic",
    "investigative": "Investigative",
    "artistic": "Artistic",
    "social": "Social",
    "enterprising": "Enterprising",
    "conventional": "Conventional",
}


_RIASEC_KEY_ALIASES = {
    "realistic": "realistic",
    "investigative": "investigative",
    "artistic": "artistic",
    "social": "social",
    "enterprising": "enterprising",
    "entrepreneurial": "enterprising",
    "conventional": "conventional",
    # Letter codes sometimes appear in older payloads.
    "r": "realistic",
    "i": "investigative",
    "a": "artistic",
    "s": "social",
    "e": "enterprising",
    "c": "conventional",
}


def _normalize_riasec_scores(raw: Any) -> Optional[Dict[str, float]]:
    """Normalize RIASEC dict keys from post-matric / class-10 payloads."""
    if not isinstance(raw, dict) or not raw:
        return None
    out: Dict[str, float] = {
        "realistic": 0.0,
        "investigative": 0.0,
        "artistic": 0.0,
        "social": 0.0,
        "enterprising": 0.0,
        "conventional": 0.0,
    }
    found = False
    for key, value in raw.items():
        key_s = str(key or "").strip()
        if key_s.startswith("_"):
            continue
        canon = _RIASEC_KEY_ALIASES.get(key_s.lower())
        if not canon:
            continue
        try:
            if isinstance(value, dict):
                score = float(
                    value.get("score", value.get("total", value.get("average", 0)))
                    or 0
                )
            else:
                score = float(value or 0)
        except (TypeError, ValueError):
            continue
        out[canon] = score
        if score > 0:
            found = True
    return out if found else None


def _scores_from_class12_career_interest(user) -> Optional[Dict[str, float]]:
    """Current class 11–12 battery: Career Interest Inventory (test id 3)."""
    from app_post_matric.models import TestResult, TestSession

    session = (
        TestSession.objects.filter(
            user_id=user.id,
            is_completed=True,
            test_id=3,
        )
        .order_by("-id")
        .only("id")
        .first()
    )
    if not session:
        session = (
            TestSession.objects.filter(
                user_id=user.id,
                is_completed=True,
                test__title__icontains="Career Interest",
            )
            .order_by("-id")
            .only("id")
            .first()
        )
    if not session:
        return None

    tr = (
        TestResult.objects.filter(session_id=session.id)
        .order_by("-id")
        .only("result_data")
        .first()
    )
    if not tr:
        return None
    return _normalize_riasec_scores(tr.result_data)


def _scores_from_class10_interest(user) -> Optional[Dict[str, float]]:
    """Class 10 battery: Career Interest (test2), then Personality (test1)."""
    from app.models import Results

    rows = list(
        Results.objects.filter(user_id=user.id, test_paper__in=["test1", "test2"])
        .only("test_paper", "scores", "results")
        .order_by("-id")[:4]
    )
    by_paper: Dict[str, Any] = {}
    for row in rows:
        paper = (row.test_paper or "").strip().lower()
        if paper and paper not in by_paper:
            by_paper[paper] = row

    t2 = by_paper.get("test2")
    if t2:
        scores = _normalize_riasec_scores(t2.scores) or _normalize_riasec_scores(
            t2.results
        )
        if scores:
            return scores

    t1 = by_paper.get("test1")
    if t1:
        scores = _normalize_riasec_scores(t1.results) or _normalize_riasec_scores(
            t1.scores
        )
        if scores:
            return scores
    return None


def _latest_riasec_scores(user) -> Optional[Dict[str, float]]:
    """RIASEC from current student batteries only (no central test).

    Priority:
    1. Class 11–12 Career Interest Inventory (post_matric)
    2. Class 10 Career Interest / Personality (Results) — for students who
       have not taken the 12th battery but have completed class-10 psych.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None

    try:
        scores = _scores_from_class12_career_interest(user)
        if scores:
            return scores
    except Exception:
        logger.debug("class-12 Career Interest RIASEC lookup failed", exc_info=True)

    try:
        scores = _scores_from_class10_interest(user)
        if scores:
            return scores
    except Exception:
        logger.debug("class-10 Results RIASEC lookup failed", exc_info=True)

    return None


def get_psychometric_match_profile(user) -> Optional[Dict[str, Any]]:
    """Local-only match profile for SSR banners (no upstream)."""
    if not user or not getattr(user, "is_authenticated", False):
        return None

    cache_key = f"indian_psych_profile:v3:{user.id}"
    try:
        cached = _match_cache().get(cache_key)
        if isinstance(cached, dict):
            return cached
        if cached is False:
            return None
    except Exception:
        pass

    scores = _latest_riasec_scores(user)
    if not scores:
        try:
            _match_cache().set(cache_key, False, PROFILE_CACHE_TTL)
        except Exception:
            pass
        return None

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_key, top_score = ranked[0]
    if top_score <= 0:
        try:
            _match_cache().set(cache_key, False, PROFILE_CACHE_TTL)
        except Exception:
            pass
        return None

    streams = list(RIASEC_TO_STREAMS.get(top_key) or [])
    if not streams:
        return None

    primary = streams[0]
    stream_options = [
        {
            "id": int(s["id"]),
            "name": s["name"],
            "filter_query": urlencode({"stream": int(s["id"])}),
        }
        for s in streams[:4]
    ]

    profile = {
        "riasec_key": top_key,
        "riasec_label": _RIASEC_LABELS.get(top_key, top_key.title()),
        "stream_id": int(primary["id"]),
        "stream_name": primary["name"],
        "filter_query": urlencode({"stream": int(primary["id"])}),
        "stream_options": stream_options,
        "headline": f"Matched for you · {_RIASEC_LABELS.get(top_key, top_key.title())}",
        "subcopy": (
            f"Based on your psychometric profile, explore {primary['name']} "
            "colleges and matched courses."
        ),
    }
    try:
        _match_cache().set(cache_key, profile, PROFILE_CACHE_TTL)
    except Exception:
        pass
    return profile


def resolve_stream_for_user(
    user, stream_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Pick active stream from profile options (or explicit query)."""
    profile = get_psychometric_match_profile(user)
    if not profile:
        return None

    options = profile.get("stream_options") or []
    if stream_id:
        for opt in options:
            if int(opt["id"]) == int(stream_id):
                return {
                    "profile": profile,
                    "stream_id": int(opt["id"]),
                    "stream_name": opt["name"],
                }
        # Allow any explicit upstream stream id even if not in top chips.
        return {
            "profile": profile,
            "stream_id": int(stream_id),
            "stream_name": f"Stream {stream_id}",
        }

    return {
        "profile": profile,
        "stream_id": int(profile["stream_id"]),
        "stream_name": profile["stream_name"],
    }


def _offering_ids_cache_key(stream_id: int) -> str:
    return f"indian_psych_offering_ids:v1:{int(stream_id)}"


def get_cached_offering_course_ids(stream_id: int) -> Optional[Set[int]]:
    try:
        cached = _match_cache().get(_offering_ids_cache_key(stream_id))
        if isinstance(cached, list):
            return {int(x) for x in cached}
        if isinstance(cached, set):
            return {int(x) for x in cached}
    except Exception:
        pass
    return None


def resolve_offering_course_ids(
    stream_id: int,
    stream_name: str,
    courses: List[Dict[str, Any]],
    *,
    max_check: int = 48,
) -> Set[int]:
    """Return filter course ids that have ≥1 college with an active courses tab.

    Optimized: one parallel pass over the stream's course list, with per-course
    and stream-level caching so later matched-course views stay cheap.
    """
    cached = get_cached_offering_course_ids(stream_id)
    if cached is not None:
        return cached

    from colleges.course_pages import has_active_course_offerings

    rows = [row for row in courses if row.get("id") and row.get("name")][: max(1, max_check)]

    def _check(row: Dict[str, Any]) -> Optional[int]:
        try:
            ok = has_active_course_offerings(
                row["name"],
                stream_name=stream_name,
                course_id=int(row["id"]),
            )
            return int(row["id"]) if ok else None
        except Exception:
            return None

    offering_ids: Set[int] = set()
    if rows:
        with ThreadPoolExecutor(max_workers=min(8, len(rows) or 1)) as pool:
            for cid in pool.map(_check, rows):
                if cid is not None:
                    offering_ids.add(cid)

    try:
        _match_cache().set(
            _offering_ids_cache_key(stream_id),
            list(offering_ids),
            OFFERING_IDS_CACHE_TTL,
        )
    except Exception:
        pass
    return offering_ids


def get_matched_courses(
    stream_id: int,
    *,
    stream_name: str = "",
    q: str = "",
    limit: int = 200,
    cache_only: bool = False,
) -> List[Dict[str, Any]]:
    """Courses for a stream via cached /filters/, kept only if colleges exist.

    When cache_only=True, return [] unless the courses list is already cached
    (so college-list SSR never waits on upstream). Offering-id filtering uses
    its own cache when available so previews stay accurate without new upstream.
    """
    stream_id = int(stream_id)
    stream_label = (stream_name or "").strip()
    q_norm = (q or "").strip().lower()
    cache_key = f"indian_psych_courses:v1:{stream_id}"
    courses: List[Dict[str, Any]] = []
    cache_backend = _match_cache()

    try:
        cached = cache_backend.get(cache_key)
        if isinstance(cached, list):
            courses = cached
    except Exception:
        cached = None

    if not isinstance(cached, list):
        if cache_only:
            return []
        try:
            from colleges.external_api import fetch_filters

            payload = fetch_filters(
                {"nationwide": True, "stream": {"id": stream_id}}
            )
            raw = (
                ((payload.get("filters") or {}).get("dynamic") or {}).get("courses")
                or []
            )
            built: List[Dict[str, Any]] = []
            for item in raw:
                cid = item.get("id")
                name = (item.get("name") or "").strip()
                if not cid or not name:
                    continue
                built.append(
                    {
                        "id": int(cid),
                        "name": name,
                        "sub_stream_id": item.get("sub_stream"),
                        "colleges_query": urlencode(
                            {"stream": stream_id, "course": int(cid)}
                        ),
                        "detail_query": urlencode(
                            {
                                "name": name,
                                "stream": stream_label or f"Stream {stream_id}",
                                "stream_id": int(stream_id),
                            }
                        ),
                    }
                )
            courses = built
            try:
                cache_backend.set(cache_key, courses, COURSES_CACHE_TTL)
            except Exception:
                pass
        except Exception:
            logger.warning("matched courses fetch failed", exc_info=True)
            courses = []

    # Ensure detail_query exists for older cache entries.
    enriched: List[Dict[str, Any]] = []
    for item in courses:
        row = dict(item)
        if not row.get("detail_query") and row.get("name"):
            row["detail_query"] = urlencode(
                {
                    "name": row["name"],
                    "stream": stream_label or f"Stream {stream_id}",
                    "stream_id": int(stream_id),
                }
            )
        elif row.get("detail_query") and "stream_id=" not in row["detail_query"]:
            # Refresh older cache entries missing stream_id.
            row["detail_query"] = urlencode(
                {
                    "name": row.get("name") or "",
                    "stream": stream_label or f"Stream {stream_id}",
                    "stream_id": int(stream_id),
                }
            )
        enriched.append(row)
    courses = enriched

    if q_norm:
        courses = [c for c in courses if q_norm in (c.get("name") or "").lower()]

    # Keep courses that have ≥1 college with an active courses tab.
    offering_ids = get_cached_offering_course_ids(stream_id)
    if offering_ids is None and not cache_only:
        offering_ids = resolve_offering_course_ids(
            stream_id, stream_label, courses, max_check=48
        )
    if offering_ids is not None:
        courses = [c for c in courses if int(c.get("id") or 0) in offering_ids]

    return courses[: max(1, min(int(limit or 200), 500))]
