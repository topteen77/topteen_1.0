"""
Shared counselor table rows for institute / marketing / institute-group dashboards.
Same dict shape as InstituteDashboardView.get_context `counselor_data_list`.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from django.db.models.functions import Lower

from django.db.models import Q

from institute.models import StudentManagement

from counselor.models import Counselor, FollowUpStatus


def _assigned_student_count_by_counselor_id(
    counselor_ids: Sequence[int], institute_ids: Sequence[int]
) -> Dict[int, int]:
    """
    Distinct StudentManagement rows per counselor in ``institute_ids`` scope where the
    student is linked via legacy FK (counselor_id) and/or M2M ``counselors``.
    """
    iids = [int(x) for x in institute_ids if x]
    cids = [int(x) for x in counselor_ids if x]
    if not iids or not cids:
        return {}
    combined: Dict[int, set] = defaultdict(set)
    base = StudentManagement.objects.filter(institute_id__in=iids)
    for sm_id, cid in base.filter(counselor_id__in=cids).values_list("id", "counselor_id"):
        if cid:
            combined[int(cid)].add(int(sm_id))
    for sm_id, cid in base.filter(counselors__id__in=cids).values_list("id", "counselors__id"):
        if cid:
            combined[int(cid)].add(int(sm_id))
    return {cid: len(sids) for cid, sids in combined.items()}


def _counselor_select_identity_tuple(counselor: Counselor) -> Tuple[str, str]:
    """Stable key for deduplicating institute-group assign dropdown rows."""
    uid = getattr(counselor, "coun_user_id", None)
    if uid:
        return ("u", str(int(uid)))
    em = (counselor.counselor_email or "").strip().lower()
    if em:
        return ("e", em)
    return ("i", str(int(counselor.pk)))


def build_institute_group_counselor_ui_maps(
    institutes_qs,
    *,
    detached_institute_group_id: int | None = None,
) -> Tuple[Dict[int, List[Dict]], List[Dict]]:
    """
    For institute-group institutes listing: map institute_id -> counselors there,
    plus flat select options for bulk/per-row assign (one Counselor row per institute admin).

    Counselors detached from every school but pending reassignment in this group are included
    in the select list (not in cmap until assigned again).
    """
    ids = list(institutes_qs.values_list("id", flat=True))
    if not ids and not detached_institute_group_id:
        return {}, []

    if ids:
        q_inst = Q(counselor_admin_id__in=ids) | Q(institute_placements__id__in=ids)
    else:
        q_inst = None
    q_det = (
        Q(
            counselor_admin__isnull=True,
            detached_from_institute_group_id=int(detached_institute_group_id),
        )
        if detached_institute_group_id
        else None
    )
    if q_inst is not None and q_det is not None:
        counselor_filter = q_inst | q_det
    elif q_inst is not None:
        counselor_filter = q_inst
    else:
        counselor_filter = q_det

    cmap: Dict[int, List[Dict]] = defaultdict(list)
    counselors = (
        Counselor.objects.filter(counselor_filter)
        .select_related("counselor_admin")
        .prefetch_related("institute_placements")
        .distinct()
        .order_by(Lower("counselor_name"), "id")
    )
    by_identity: Dict[Tuple[str, str], List[Counselor]] = defaultdict(list)
    for c in counselors:
        id_set = set(ids or [])
        placed_ids = []
        if c.counselor_admin_id and c.counselor_admin_id in id_set:
            placed_ids.append(c.counselor_admin_id)
        for ip in c.institute_placements.all():
            if ip.id in id_set and ip.id not in placed_ids:
                placed_ids.append(ip.id)
        for aid in placed_ids:
            cmap[aid].append({"id": c.id, "name": c.counselor_name})
        by_identity[_counselor_select_identity_tuple(c)].append(c)

    select_opts: List[Dict] = []
    for _ident in sorted(by_identity.keys(), key=lambda t: (t[0], t[1])):
        rows_for_id = by_identity[_ident]
        rows_for_id.sort(
            key=lambda c: (
                0 if c.counselor_admin_id else 1,
                (c.counselor_name or "").lower(),
                c.id,
            )
        )
        rep = rows_for_id[0]
        admin = rep.counselor_admin
        select_opts.append(
            {
                "id": rep.id,
                "name": rep.counselor_name,
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
    Counselors whose primary or placement school is in ``institute_ids``, with follow-up,
    counselled, and assigned-student counts (assigned = distinct students via FK and/or M2M).
    """
    ids = sorted({int(x) for x in institute_ids if x})
    if not ids:
        return []

    counselors = list(
        Counselor.objects.filter(
            Q(counselor_admin_id__in=ids) | Q(institute_placements__id__in=ids)
        )
        .select_related("counselor_admin")
        .prefetch_related("institute_placements")
        .distinct()
    )
    counselor_ids = [c.id for c in counselors]
    if not counselor_ids:
        return []

    assigned_counts = _assigned_student_count_by_counselor_id(counselor_ids, ids)

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
            "students_assigned": int(assigned_counts.get(counselor_id, 0)),
            "created": counselor.created,
        }
        if include_institute_name:
            admin = None
            if counselor.counselor_admin_id and counselor.counselor_admin_id in ids:
                admin = counselor.counselor_admin
            if admin is None:
                for inst in counselor.institute_placements.all():
                    if inst.id in ids:
                        admin = inst
                        break
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
    """One row per (counselor, institute) placement in the id set, with follow-up aggregates."""
    ids = sorted({int(x) for x in institute_ids if x})
    if not ids:
        return []
    id_set = set(ids)

    counselors = list(
        Counselor.objects.filter(
            Q(counselor_admin_id__in=ids) | Q(institute_placements__id__in=ids)
        )
        .select_related("counselor_admin")
        .prefetch_related("institute_placements")
        .distinct()
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
        followups = followups_by_counselor.get(counselor.id, [])
        sessions_count = len(followups)
        students_counseled_count = sum(1 for f in followups if f.follow_up_status == "completed")
        placed = []
        if counselor.counselor_admin_id and counselor.counselor_admin_id in id_set:
            placed.append(counselor.counselor_admin)
        for inst in counselor.institute_placements.all():
            if inst.id in id_set and all(p.id != inst.id for p in placed):
                placed.append(inst)
        sort_placed = sorted(
            placed,
            key=lambda i: ((getattr(i, "name", "") or "").lower(), i.id),
        )
        for admin in sort_placed:
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
    rows.sort(
        key=lambda r: (
            (r.get("institute_name") or "").lower(),
            (r.get("counselor_name") or "").lower(),
            r.get("counselor_record_id") or 0,
        )
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


def build_unique_counselor_identity_rows(
    institute_ids: Sequence[int],
    *,
    detached_institute_group_id: int | None = None,
) -> List[Dict]:
    """
    One logical advisor per linked login user (or shared email); aggregates counts across placements.
    Canonical ``id`` is the smallest Counselor pk in the group (edit/password target).

    Optionally includes counselors detached from all schools but scoped to ``detached_institute_group_id``.
    """
    ids = sorted({int(x) for x in institute_ids if x})
    if not ids and not detached_institute_group_id:
        return []

    parts: List[Q] = []
    if ids:
        parts.append(
            Q(counselor_admin_id__in=ids) | Q(institute_placements__id__in=ids)
        )
    if detached_institute_group_id:
        parts.append(
            Q(
                counselor_admin__isnull=True,
                detached_from_institute_group_id=int(detached_institute_group_id),
            )
        )
    if not parts:
        return []

    counselor_filter = parts[0]
    for extra in parts[1:]:
        counselor_filter |= extra

    counselors = list(
        Counselor.objects.filter(counselor_filter)
        .select_related("counselor_admin")
        .prefetch_related("institute_placements")
        .distinct()
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

        id_set = set(ids) if ids else None
        institute_names: List[str] = []
        seen_admin: Dict[int, None] = {}
        for c in members:
            admin = c.counselor_admin
            aid = getattr(admin, "id", None)
            if aid is not None and aid not in seen_admin:
                if id_set is None or aid in id_set:
                    seen_admin[aid] = None
                    institute_names.append(getattr(admin, "name", "") or "—")
            for inst in c.institute_placements.all():
                iid = inst.id
                if iid not in seen_admin:
                    if id_set is None or iid in id_set:
                        seen_admin[iid] = None
                        institute_names.append(getattr(inst, "name", "") or "—")
        institute_names.sort(key=lambda x: x.lower())
        if not institute_names:
            if any(getattr(c, "detached_from_institute_group_id", None) for c in members):
                institute_names.append("(Not assigned to a school)")

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
