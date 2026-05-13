"""
Shared counselor table rows for institute / marketing / institute-group dashboards.
Same dict shape as InstituteDashboardView.get_context `counselor_data_list`.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from django.db.models.functions import Lower

from counselor.models import Counselor, FollowUpStatus


def build_institute_group_counselor_ui_maps(institutes_qs) -> Tuple[Dict[int, List[Dict]], List[Dict]]:
    """
    For institute-group institutes listing: map institute_id -> counselors there,
    plus flat select options for bulk/per-row assign (one Counselor row per institute admin).
    """
    ids = list(institutes_qs.values_list("id", flat=True))
    if not ids:
        return {}, []

    cmap: Dict[int, List[Dict]] = defaultdict(list)
    select_opts: List[Dict] = []
    counselors = (
        Counselor.objects.filter(counselor_admin_id__in=ids)
        .select_related("counselor_admin")
        .order_by(Lower("counselor_name"), "id")
    )
    for c in counselors:
        cmap[c.counselor_admin_id].append({"id": c.id, "name": c.counselor_name})
        admin = c.counselor_admin
        select_opts.append(
            {
                "id": c.id,
                "name": c.counselor_name,
                "institute_name": getattr(admin, "name", "") or "—",
            }
        )
    return dict(cmap), select_opts


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
            "address": counselor.counselor_address or "",
            "contact": counselor.counselor_contact_info or "",
            "education": counselor.counselor_education or "",
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
    """Narrow counselor rows by substring match on name, email, institute name, or schools label (if present)."""
    q = (query or "").strip().lower()
    if not q or not rows:
        return rows
    out: List[Dict] = []
    for r in rows:
        name = (r.get("name") or "").lower()
        email = (r.get("email") or "").lower()
        inst = (r.get("institute_name") or "").lower()
        schools = (r.get("institutes_label") or "").lower()
        if q in name or q in email or q in inst or q in schools:
            out.append(r)
    return out


def _counselor_identity_key(counselor: Counselor) -> Tuple[str, str]:
    uid = getattr(counselor, "coun_user_id", None)
    if uid:
        return ("u", str(int(uid)))
    em = (counselor.counselor_email or "").strip().lower()
    if em:
        return ("e", em)
    return ("i", str(int(counselor.id)))


def build_ig_counselor_placement_rows(institute_ids: Sequence[int]) -> List[Dict]:
    """One row per Counselor record (institute placement), with follow-up aggregates for that placement."""
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

    counselors_sorted = sorted(
        counselors,
        key=lambda c: (
            (getattr(c.counselor_admin, "name", "") or "").lower(),
            (c.counselor_name or "").lower(),
            c.id,
        ),
    )

    rows: List[Dict] = []
    for counselor in counselors_sorted:
        admin = counselor.counselor_admin
        followups = followups_by_counselor.get(counselor.id, [])
        sessions_count = len(followups)
        students_counseled_count = sum(1 for f in followups if f.follow_up_status == "completed")
        rows.append(
            {
                "counselor_record_id": counselor.id,
                "institute_name": getattr(admin, "name", "") or "—",
                "institute_slug": getattr(admin, "slug", "") or "",
                "counselor_name": counselor.counselor_name,
                "email": counselor.counselor_email or "",
                "sessions": sessions_count,
                "students_counseled": students_counseled_count,
            }
        )
    return rows


def filter_ig_placement_rows_by_query(rows: List[Dict], query: str) -> List[Dict]:
    q = (query or "").strip().lower()
    if not q or not rows:
        return rows
    out: List[Dict] = []
    for r in rows:
        parts = [
            (r.get("institute_name") or "").lower(),
            (r.get("counselor_name") or "").lower(),
            (r.get("email") or "").lower(),
        ]
        if any(q in p for p in parts):
            out.append(r)
    return out


def build_unique_counselor_identity_rows(institute_ids: Sequence[int]) -> List[Dict]:
    """
    One logical advisor per linked login user (or shared email); aggregates counts across placements.
    Canonical ``id`` is the smallest Counselor pk in the group (edit/password target).
    """
    ids = sorted({int(x) for x in institute_ids if x})
    if not ids:
        return []

    counselors = list(
        Counselor.objects.filter(counselor_admin_id__in=ids).select_related("counselor_admin")
    )
    if not counselors:
        return []

    grouped: Dict[Tuple[str, str], List[Counselor]] = defaultdict(list)
    for c in counselors:
        grouped[_counselor_identity_key(c)].append(c)

    all_counselor_ids = [c.id for c in counselors]
    followups_by_counselor: Dict[int, list] = {}
    for followup in FollowUpStatus.objects.filter(counselor_id__in=all_counselor_ids).select_related(
        "counselor"
    ):
        followups_by_counselor.setdefault(followup.counselor_id, []).append(followup)

    out: List[Dict] = []
    for _key, members in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        canon_id = min(c.id for c in members)

        def _rep_sort_key(c: Counselor):
            has_em = 1 if (c.counselor_email or "").strip() else 0
            return (-has_em, (c.counselor_name or "").lower(), c.id)

        rep = sorted(members, key=_rep_sort_key)[0]

        sessions_count = sum(len(followups_by_counselor.get(c.id, [])) for c in members)
        students_counseled_count = sum(
            sum(1 for f in followups_by_counselor.get(c.id, []) if f.follow_up_status == "completed")
            for c in members
        )

        institute_names: List[str] = []
        seen_admin: Dict[int, None] = {}
        for c in members:
            admin = c.counselor_admin
            aid = getattr(admin, "id", None)
            if aid is None or aid in seen_admin:
                continue
            seen_admin[aid] = None
            institute_names.append(getattr(admin, "name", "") or "—")
        institute_names.sort(key=lambda x: x.lower())

        created_times = [c.created for c in members if getattr(c, "created", None)]
        created_val = min(created_times) if created_times else None

        out.append(
            {
                "id": canon_id,
                "coun_admin": rep.counselor_admin,
                "name": rep.counselor_name,
                "email": rep.counselor_email,
                "address": rep.counselor_address or "",
                "contact": rep.counselor_contact_info or "",
                "education": rep.counselor_education or "",
                "sessions": sessions_count,
                "students_counseled": students_counseled_count,
                "created": created_val,
                "institutes_label": ", ".join(institute_names),
            }
        )

    out.sort(key=lambda r: ((r.get("name") or "").lower(), r["id"]))
    return out
