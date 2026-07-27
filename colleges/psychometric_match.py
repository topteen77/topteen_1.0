"""Psychometric (RIASEC) → Indian college stream / course matching.

Speed rules:
- Profile resolution is local DB only (single query).
- Courses live on a dedicated page and use one cached /filters/ call.
- College list SSR never calls upstream for psychometric previews.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from django.core.cache import caches

logger = logging.getLogger(__name__)

PROFILE_CACHE_TTL = 120
COURSES_CACHE_TTL = 300


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


def _latest_riasec_scores(user) -> Optional[Dict[str, float]]:
    """Single-query RIASEC lookup (no N+1)."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        from users.parent_dashboard_ai import interest_scores_from_test_result
        from psychometric_tests.models import PsychometricTestResult

        ptr = (
            PsychometricTestResult.objects.filter(
                assessment__central_test_candidate__user_id=user.id
            )
            .order_by("-id")
            .only(
                "realistic",
                "investigative",
                "artistic",
                "social",
                "entrepreneurial",
                "conventional",
            )
            .first()
        )
        return interest_scores_from_test_result(ptr)
    except Exception:
        logger.debug("psychometric RIASEC lookup failed", exc_info=True)
        return None


def get_psychometric_match_profile(user) -> Optional[Dict[str, Any]]:
    """Local-only match profile for SSR banners (no upstream)."""
    if not user or not getattr(user, "is_authenticated", False):
        return None

    cache_key = f"indian_psych_profile:v1:{user.id}"
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


def get_matched_courses(
    stream_id: int,
    *,
    stream_name: str = "",
    q: str = "",
    limit: int = 200,
    cache_only: bool = False,
) -> List[Dict[str, Any]]:
    """Courses for a stream via cached /filters/ only (no college list call).

    When cache_only=True, return [] unless the courses list is already cached
    (so college-list SSR never waits on upstream).
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
                }
            )
        enriched.append(row)
    courses = enriched

    if q_norm:
        courses = [c for c in courses if q_norm in (c.get("name") or "").lower()]

    return courses[: max(1, min(int(limit or 200), 500))]
