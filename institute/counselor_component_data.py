"""
Shared counselor table rows for institute / marketing / institute-group dashboards.
Same dict shape as InstituteDashboardView.get_context `counselor_data_list`.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

from counselor.models import Counselor, FollowUpStatus


def build_counselor_data_list_for_institute_ids(
    institute_ids: Sequence[int],
    *,
    include_institute_name: bool = False,
) -> List[Dict]:
    """
    Counselors whose `counselor_admin_id` is in `institute_ids`, with session / counseled counts.
    """
    ids = sorted({int(x) for x in institute_ids if x})
    if not ids:
        return []

    counselors = list(
        Counselor.objects.filter(counselor_admin_id__in=ids).select_related("counselor_admin")
    )
    counselor_ids = [c.id for c in counselors]
    if not counselor_ids:
        return []

    followups_by_counselor: Dict[int, list] = {}
    for followup in FollowUpStatus.objects.filter(counselor_id__in=counselor_ids).select_related(
        "counselor"
    ):
        followups_by_counselor.setdefault(followup.counselor_id, []).append(followup)

    rows: List[Dict] = []
    for counselor in counselors:
        counselor_id = counselor.id
        followups = followups_by_counselor.get(counselor_id, [])
        sessions_count = len(followups)
        students_counseled_count = sum(1 for f in followups if f.follow_up_status == "completed")
        row = {
            "id": counselor.id,
            "coun_admin": counselor.counselor_admin,
            "name": counselor.counselor_name,
            "email": counselor.counselor_email,
            "sessions": sessions_count,
            "students_counseled": students_counseled_count,
            "created": counselor.created,
        }
        if include_institute_name and counselor.counselor_admin:
            admin = counselor.counselor_admin
            row["institute_name"] = getattr(admin, "name", "") or "—"
            row["institute_slug"] = getattr(admin, "slug", "") or ""
        rows.append(row)
    return rows


def filter_counselor_data_list_by_query(rows: List[Dict], query: str) -> List[Dict]:
    """Narrow counselor rows by substring match on name, email, or institute name (if present)."""
    q = (query or "").strip().lower()
    if not q or not rows:
        return rows
    out: List[Dict] = []
    for r in rows:
        name = (r.get("name") or "").lower()
        email = (r.get("email") or "").lower()
        inst = (r.get("institute_name") or "").lower()
        if q in name or q in email or q in inst:
            out.append(r)
    return out
