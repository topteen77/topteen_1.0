from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.urls import NoReverseMatch, reverse

from core import choices
from counselor.models import Counselor
from institute.models import Institute


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
    try:
        qs = getattr(user, "institute_created", None)
        if qs is not None:
            return qs.last()
    except Exception:
        pass
    return None


def _resolve_counselor_for_user(user) -> Optional[Counselor]:
    try:
        return (
            Counselor.objects.select_related("counselor_admin", "coun_user")
            .filter(coun_user=user)
            .first()
        )
    except Exception:
        return None


def _nav_for_role(
    *,
    role: str,
    institute: Optional[Institute],
    counselor: Optional[Counselor],
) -> List[Dict[str, Any]]:
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
                    {
                        "label": "Session plan",
                        "dot": "#f472b6",
                        "href": _safe_reverse("counselor:CounselorDashboardSection", args=[coun_id, "session-plan"])
                        if coun_id
                        else "#",
                        "key": "plan",
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
                        "label": "Students",
                        "dot": "#f472b6",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["students"]),
                    },
                ],
            },
            {
                "title": "Analytics",
                "items": [{"label": "Career heatmap", "dot": "#34d399", "href": _safe_reverse("institute:institutegroupheatmap")}],
            },
            {
                "title": "Accounts",
                "items": [
                    {
                        "label": "Accounts",
                        "dot": "#6c7dff",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["accounts"]),
                    },
                    {
                        "label": "Payments",
                        "dot": "#34d399",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["payments"]),
                    },
                ],
            },
        ]

    if role == "marketing_group":
        return [
            {
                "title": "Reports",
                "items": [
                    {"label": "Dashboard", "dot": "#6c7dff", "href": _safe_reverse("institute:marketinggroupdashboard")},
                    {
                        "label": "Students",
                        "dot": "#f472b6",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["students"]),
                    },
                ],
            },
            {
                "title": "Analytics",
                "items": [{"label": "Career heatmap", "dot": "#34d399", "href": _safe_reverse("institute:marketinggroupheatmap")}],
            },
            {
                "title": "Accounts",
                "items": [
                    {
                        "label": "Accounts",
                        "dot": "#6c7dff",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["accounts"]),
                    },
                    {
                        "label": "Payments",
                        "dot": "#34d399",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["payments"]),
                    },
                ],
            },
        ]

    # Default: institute
    return [
        {
            "title": "Reports",
            "items": [
                {
                    "label": "Dashboard",
                    "dot": "#6c7dff",
                    "href": _safe_reverse("institute:institute_masterdashboard", args=[inst_slug]) if inst_slug else "#",
                },
                {
                    "label": "Students",
                    "dot": "#f472b6",
                    "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "students"]) if inst_slug else "#",
                },
                {
                    "label": "Counselors",
                    "dot": "#4ade80",
                    "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "counselors"]) if inst_slug else "#",
                },
                {
                    "label": "Sessions",
                    "dot": "#fb923c",
                    "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "sessions"]) if inst_slug else "#",
                },
            ],
        },
        {
            "title": "Analytics",
            "items": [
                {
                    "label": "Career heatmap",
                    "dot": "#34d399",
                    "href": _safe_reverse("institute:instituteheatmap", args=[inst_slug]) if inst_slug else "#",
                },
                {
                    "label": "Streams & capacity",
                    "dot": "#a78bfa",
                    "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "streams_capacity"])
                    if inst_slug
                    else "#",
                },
            ],
        },
        {
            "title": "Accounts",
            "items": [
                {
                    "label": "Accounts",
                    "dot": "#6c7dff",
                    "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "accounts"])
                    if inst_slug
                    else "#",
                },
                {
                    "label": "Payments",
                    "dot": "#34d399",
                    "href": _safe_reverse("institute:institutedashboard_page", args=[inst_slug, "payments"])
                    if inst_slug
                    else "#",
                },
            ],
        },
    ]


def ttv2_role_ctx(request) -> Dict[str, Any]:
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"ttv2_role_ctx": {"role": "anonymous", "user": user, "nav": {"sections": []}}}

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
        if role == "counselor":
            tagline = "Career Counsellor Dashboard v2.0"
            # Prefer counselor name; fallback to logged-in user display name.
            _cname = ""
            try:
                if counselor and getattr(counselor, "counselor_name", None):
                    _cname = str(counselor.counselor_name or "").strip()
            except Exception:
                _cname = ""
            if not _cname:
                _cname = display_name
            # Use counselor created date when available; otherwise blank.
            _jn = ""
            try:
                c_created = getattr(counselor, "created", None) if counselor else None
                if c_created:
                    _jn = c_created.strftime("%b %Y")
            except Exception:
                _jn = ""
            # Badge shows institute/school name so context isn't lost.
            _badge = "Active member"
            try:
                if institute and getattr(institute, "name", None):
                    _badge = str(institute.name or "").strip() or _badge
            except Exception:
                pass
            profile = {"name": _cname, "joined": _jn, "badge": _badge}
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
        }
    }

