"""Institute credit balance helpers for v2 group/marketing dashboards."""
from __future__ import annotations

from typing import Any, Dict, List

from django.db.models import Count
from django.db.models.functions import Lower

from core import choices
from institute.models import Institute


def institute_credits_remaining(allocated, used) -> int:
    """Balance credits = allocated seat cap minus enrolled students."""
    return max(0, int(allocated or 0) - int(used or 0))


def institute_credits_remaining_for_institute(institute) -> int:
    """Remaining upload seats for one institute (matches roster balance display)."""
    from institute.models import StudentManagement

    try:
        used = StudentManagement.objects.filter(institute_id=institute.id).count()
    except Exception:
        used = 0
    return institute_credits_remaining(getattr(institute, "credit_counts", 0), used)


def institute_bulk_upload_block_reason(institute) -> str:
    """
    None if bulk CSV upload is allowed; otherwise a short user-facing reason.
    """
    if not institute:
        return "Institute not found."
    if getattr(institute, "is_system_demo", False):
        return (
            "Demo institutes are read-only. Choose a real school with available credits."
        )
    remaining = institute_credits_remaining_for_institute(institute)
    if remaining <= 0:
        return (
            f"No credits left for this institute ({remaining} remaining). "
            "Allocate more credits before uploading students."
        )
    return ""


def build_ttv2_quicklink_institutes(user) -> List[Dict[str, Any]]:
    """
    Institutes in scope for marketing / institute-group admins, with credit balances
    for modal dropdowns and student filters.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return []
    try:
        ut = int(getattr(user, "user_type", 0) or 0)
    except Exception:
        return []

    qs = None
    if ut == choices.UserType.MARKETINGGROUPADMIN:
        qs = Institute.objects.filter(marketing_group__marketing_group_admin=user)
    elif ut == choices.UserType.INSTITUTEGROUPADMIN:
        qs = Institute.objects.filter(institute_group__institute_group_admin=user)
    else:
        return []

    try:
        rows = list(
            qs.annotate(credits_used=Count("student_management"))
            .values(
                "id",
                "name",
                "slug",
                "credit_counts",
                "credits_used",
                "is_system_demo",
            )
            .order_by(Lower("name"))[:500]
        )
    except Exception:
        return []

    for row in rows:
        alloc = int(row.get("credit_counts") or 0)
        used = int(row.get("credits_used") or 0)
        row["credits_allocated"] = alloc
        row["credits_used"] = used
        row["credits_remaining"] = institute_credits_remaining(alloc, used)
    return rows
