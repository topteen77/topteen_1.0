from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.urls import NoReverseMatch, reverse

from core import choices
from counselor.models import Counselor
from institute.models import Institute
from django.db.models.functions import Lower


def _safe_reverse(viewname: str, *, args: Optional[list] = None, kwargs: Optional[dict] = None) -> str:
    try:
        return reverse(viewname, args=args or [], kwargs=kwargs or {})
    except NoReverseMatch:
        return "#"
    except Exception:
        return "#"


def _display_name_for_user(user) -> str:
    for attr in ("name", "first_name", "mobile", "email"):
        try:
            val = getattr(user, attr, None)
        except Exception:
            val = None
        if val:
            return str(val)
    return "User"


def _resolve_institute_for_user(user) -> Optional[Institute]:
    # Institute dashboard users typically have institute_created relation.
    try:
        qs = getattr(user, "institute_created", None)
        if qs is not None:
            return qs.last()
    except Exception:
        pass
    return None


def _resolve_counselor_for_user(user) -> Optional[Counselor]:
    try:
        return Counselor.objects.select_related("counselor_admin", "coun_user").filter(coun_user=user).first()
    except Exception:
        return None


def _nav_for_role(
    *,
    role: str,
    institute: Optional[Institute],
    counselor: Optional[Counselor],
) -> List[Dict[str, Any]]:
    """
    Returns nav.sections: [{title, items:[{label, href, key(optional)}]}]
    Keep it intentionally small and stable; pages can extend later.
    """
    inst_slug = getattr(institute, "slug", None) if institute else None
    coun_id = getattr(counselor, "id", None) if counselor else None

    if role == "counselor":
        return [
            {
                "title": "Report",
                "items": [
                    {
                        "label": "Dashboard",
                        "dot": "#6c7dff",
                        "href": _safe_reverse("counselor:CounselorDashboardSection", args=[coun_id, "dashboard"])
                        if coun_id
                        else "#",
                        "key": "dashboard",
                    },
                    {
                        "label": "Students",
                        "dot": "#f472b6",
                        "href": _safe_reverse("counselor:CounselorDashboardSection", args=[coun_id, "students"])
                        if coun_id
                        else "#",
                        "key": "students",
                    },
                ],
            },
            {
                "title": "Analytics",
                "items": [
                    {
                        "label": "Career analytics",
                        "dot": "#fb923c",
                        "href": _safe_reverse(
                            "counselor:CounselorDashboardSection", args=[coun_id, "career-analytics"]
                        )
                        if coun_id
                        else "#",
                        "key": "career",
                    }
                ],
            },
            {
                "title": "Guidance",
                "items": [
                    {
                        "label": "Session report",
                        "dot": "#fb923c",
                        "href": _safe_reverse("counselor:CounselorDashboardSection", args=[coun_id, "session-report"])
                        if coun_id
                        else "#",
                        "key": "sessions",
                    },
                ],
            },
            {
                "title": "Courses",
                "items": [
                    {
                        "label": "My Enrolled Courses",
                        "dot": "#fb923c",
                        "href": _safe_reverse("counselor:course_learning", args=[coun_id]) if coun_id else "#",
                    }
                ],
            },
        ]

    if role == "institute_group":
        return [
            {
                "title": "Reports",
                "items": [
                    {"label": "Dashboard", "dot": "#6c7dff", "href": _safe_reverse("institute:institutegroupdashboard")},
                    {
                        "label": "Institutes",
                        "dot": "#3b82f6",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["institutes"]),
                        "key": "institutes",
                    },
                    {
                        "label": "Counselors",
                        "dot": "#0ea5e9",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["counselors"]),
                        "key": "counselors",
                    },
                    {"label": "Students", "dot": "#f472b6", "href": _safe_reverse("institute:institutegroupdashboard_page", args=["students"])},
                ],
            },
            {"title": "Analytics", "items": [{"label": "Career heatmap", "dot": "#34d399", "href": _safe_reverse("institute:institutegroupheatmap")}]},
        ]

    if role == "marketing_group":
        return [
            {
                "title": "Reports",
                "items": [
                    {"label": "Dashboard", "dot": "#6c7dff", "href": _safe_reverse("institute:marketinggroupdashboard")},
                    {
                        "label": "Institutes",
                        "dot": "#3b82f6",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["institutes"]),
                        "key": "institutes",
                    },
                    {
                        "label": "Counselors",
                        "dot": "#0ea5e9",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["counselors"]),
                        "key": "counselors",
                    },
                    {"label": "Students", "dot": "#f472b6", "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["students"])},
                ],
            },
            {"title": "Analytics", "items": [{"label": "Career heatmap", "dot": "#34d399", "href": _safe_reverse("institute:marketinggroupheatmap")}]},
        ]

    # Default: institute
    return [
        {
            "title": "Reports",
            "items": [
                {"label": "Dashboard", "dot": "#6c7dff", "href": _safe_reverse("institute:institute_masterdashboard", args=[inst_slug]) if inst_slug else "#"},
                {"label": "Students", "dot": "#f472b6", "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "students"]) if inst_slug else "#"},
                {"label": "Counselors", "dot": "#4ade80", "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "counselors"]) if inst_slug else "#"},
                {"label": "Sessions", "dot": "#fb923c", "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "sessions"]) if inst_slug else "#"},
            ],
        },
        {
            "title": "Analytics",
            "items": [
                {
                    "label": "Career heatmap",
                    "dot": "#34d399",
                    "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "heatmap"]) if inst_slug else "#",
                    "key": "heatmap",
                },
                {"label": "Streams & capacity", "dot": "#a78bfa", "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "streams_capacity"]) if inst_slug else "#"},
            ],
        },
    ]


def ttv2_role_ctx(request) -> Dict[str, Any]:
    """
    Jinja2 context processor.
    Provides `ttv2_role_ctx` for v2 dashboards to render header/sidebar/footer dynamically.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"ttv2_role_ctx": {"role": "anonymous", "user": user, "nav": {"sections": []}}}

    # Determine role from user_type
    try:
        user_type = int(getattr(user, "user_type", 0) or 0)
    except Exception:
        user_type = 0

    role = "institute"
    if user_type == choices.UserType.COUNSELOR:
        role = "counselor"
    elif user_type == choices.UserType.INSTITUTEGROUPADMIN:
        role = "institute_group"
    elif user_type == choices.UserType.MARKETINGGROUPADMIN:
        role = "marketing_group"
    elif user_type == choices.UserType.INSTITUTE:
        role = "institute"

    counselor = _resolve_counselor_for_user(user) if role == "counselor" else None
    institute = None
    if role == "counselor":
        institute = getattr(counselor, "counselor_admin", None) if counselor else None
    elif role == "institute":
        institute = _resolve_institute_for_user(user)

    display_name = _display_name_for_user(user)
    sections = _nav_for_role(role=role, institute=institute, counselor=counselor)

    profile = None
    tagline = "Dashboard v2.0"
    try:
        if role == "counselor" and institute:
            tagline = "Career Counsellor Dashboard v2.0"
            _jn = institute.created.strftime("%b %Y") if getattr(institute, "created", None) else ""
            profile = {"name": getattr(institute, "name", "") or "Institute", "joined": _jn, "badge": "Active member"}
        elif role == "institute" and institute:
            tagline = "Institute Dashboard v2.0"
            _jn = institute.created.strftime("%b %Y") if getattr(institute, "created", None) else ""
            profile = {"name": getattr(institute, "name", "") or "Institute", "joined": _jn, "badge": "Active member"}
        elif role == "institute_group":
            tagline = "Institute Group Dashboard v2.0"
        elif role == "marketing_group":
            tagline = "Marketing Dashboard v2.0"
    except Exception:
        profile = None

    permissions = {
        "can_edit_students": role == "institute",
        "can_block_students": role == "institute",
    }

    # Shared v2 modals (CSV upload / add counselor) need an institute list in shell templates.
    # Provide it globally for roles that can act across institutes.
    ttv2_quicklink_institutes: List[Dict[str, Any]] = []
    try:
        if role in ("counselor", "institute") and institute:
            ttv2_quicklink_institutes = [
                {"id": institute.id, "name": institute.name, "slug": institute.slug}
            ]
        elif role == "marketing_group":
            ttv2_quicklink_institutes = list(
                Institute.objects.filter(marketing_group__marketing_group_admin=user)
                .values("id", "name", "slug")
                .order_by(Lower("name"))[:500]
            )
        elif role == "institute_group":
            ttv2_quicklink_institutes = list(
                Institute.objects.filter(institute_group__institute_group_admin=user)
                .values("id", "name", "slug")
                .order_by(Lower("name"))[:500]
            )
    except Exception:
        ttv2_quicklink_institutes = []

    return {
        "ttv2_role_ctx": {
            "role": role,
            "user": user,
            "display_name": display_name,
            "institute": institute,
            "counselor": counselor,
            "tagline": tagline,
            "profile": profile,
            "nav": {"sections": sections},
            "permissions": permissions,
        },
        "ttv2_quicklink_institutes": ttv2_quicklink_institutes,
    }

