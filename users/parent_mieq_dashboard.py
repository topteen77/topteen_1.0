"""Parent-dashboard MI / EQ cards — bulk queries + Redis (parents alias)."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from django.templatetags.static import static
from django.urls import reverse

from users.parent_dashboard_cache import (
    get_or_build_cached,
    invalidate_parent_dashboard_cache,
    parent_mieq_cache_key,
    PARENT_DASH_TTL,
)


def invalidate_parent_mieq_dashboard_cache(parent_id: int) -> None:
    """Invalidate full parent dashboard bundle (includes MI/EQ)."""
    invalidate_parent_dashboard_cache(parent_id)


def _build_mieq_payload(student_list: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
    from core.models import EQAssessmentResult, MIAssessmentResult

    user_ids = [int(s.id) for s in student_list]
    mi_done_ids = set(
        MIAssessmentResult.objects.filter(user_id__in=user_ids).values_list(
            "user_id", flat=True
        )
    )
    eq_done_ids = set(
        EQAssessmentResult.objects.filter(user_id__in=user_ids).values_list(
            "user_id", flat=True
        )
    )

    mi_detail = reverse("core:multiple_intelligences")
    eq_detail = reverse("core:emotional_intelligences")
    mi_assess = reverse("core:multiple_intelligences_assessment")
    eq_assess = reverse("core:emotional_intelligences_assessment")
    mi_icon = static("images_new/icons/multiple-intelligence.png")
    eq_icon = static("images_new/icons/emotions.png")

    out: Dict[str, List[Dict[str, Any]]] = {}
    for s in student_list:
        sid = int(s.id)
        mi_done = sid in mi_done_ids
        eq_done = sid in eq_done_ids
        out[str(sid)] = [
            {
                "kind": "mi",
                "title": "Multiple Intelligence",
                "subtitle": "Know your learning style" if mi_done else "Assessment",
                "done": mi_done,
                "action_label": "View report" if mi_done else "Start test",
                "action_url": (
                    f"{mi_assess}?student_id={sid}" if mi_done else mi_detail
                ),
                "detail_url": mi_detail,
                "icon_src": mi_icon,
                "icon_bg": "#fff4e6",
                "kind_badge": "FREE",
            },
            {
                "kind": "eq",
                "title": "Emotional Intelligence",
                "subtitle": "Know your EQ" if eq_done else "Assessment",
                "done": eq_done,
                "action_label": "View report" if eq_done else "Start test",
                "action_url": (
                    f"{eq_assess}?student_id={sid}" if eq_done else eq_detail
                ),
                "detail_url": eq_detail,
                "icon_src": eq_icon,
                "icon_bg": "#fdf2f8",
                "kind_badge": "FREE",
            },
        ]
    return out


def build_parent_mieq_by_student(
    parent,
    students: Iterable[Any],
    *,
    use_cache: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Per linked student: MI + EQ dashboard cards.

    Redis (parents alias) first; on miss, 2 DB queries for all students.
    """
    student_list = [s for s in students if getattr(s, "id", None)]
    empty: Dict[str, List[Dict[str, Any]]] = {
        str(int(s.id)): [] for s in student_list
    }
    if not parent or not student_list:
        return empty

    parent_id = int(getattr(parent, "id", 0) or 0)
    if not use_cache or not parent_id:
        return _build_mieq_payload(student_list)

    # Fixed key (no student fingerprint) so invalidate_parent_dashboard_cache can delete it.
    cache_key = parent_mieq_cache_key(parent_id)

    def _build():
        return _build_mieq_payload(student_list)

    def _ok(val: Any) -> bool:
        return isinstance(val, dict)

    payload = get_or_build_cached(
        cache_key,
        _build,
        ttl=PARENT_DASH_TTL,
        lock_key=f"{cache_key}:lock",
        validate=_ok,
    )
    if not isinstance(payload, dict):
        return empty
    return {sid: payload.get(sid, []) for sid in empty.keys()}
