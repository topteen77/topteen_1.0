from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from django.urls import NoReverseMatch, reverse

from core import choices
from counselor.models import Counselor
from institute.models import Institute, InstituteGroup, InstituteMarketingGroup

TTV2_PAGE_LOADER_CONFIG_KEY = "TTV2_PAGE_LOADER_ENABLED"


def _config_truthy(val: object, *, default: bool = True) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "on")


def ttv2_page_loader_enabled() -> bool:
    """Admin flag: donut % overlay while v2 dashboard AJAX pages load (Configuration)."""
    try:
        from core.models import Configuration

        # Read-only: never use Configuration.get() here — get_or_create can raise
        # IntegrityError when a soft-deleted row still holds the unique key.
        row = Configuration.objects.filter(key=TTV2_PAGE_LOADER_CONFIG_KEY).first()
        if not row:
            return True
        return _config_truthy(row.value, default=True)
    except Exception:
        return True


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


def _resolve_institute_from_request(request) -> Optional[Institute]:
    """Institute slug from /institute/<slug>/… so Pay now matches the active dashboard."""
    path = getattr(request, "path", "") or ""
    m = re.match(r"^/institute/([^/]+)/", path)
    if not m:
        return None
    slug = m.group(1)
    try:
        return Institute.objects.filter(slug=slug).first()
    except Exception:
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


def _resolve_marketing_group_for_user(user) -> Optional[InstituteMarketingGroup]:
    try:
        return InstituteMarketingGroup.objects.filter(marketing_group_admin=user).first()
    except Exception:
        return None


def _resolve_institute_group_for_user(user) -> Optional[InstituteGroup]:
    try:
        return InstituteGroup.objects.filter(institute_group_admin=user).first()
    except Exception:
        return None


def _profile_role_label(role: str) -> str:
    """Human-readable role for v2 sidebar profile card."""
    return {
        "counselor": "Counselor",
        "institute": "Institute admin",
        "institute_group": "Institute group admin",
        "marketing_group": "Marketing admin",
    }.get(role or "", "")


def _format_joined_month_year(obj) -> str:
    try:
        created = getattr(obj, "created", None)
        if created:
            return created.strftime("%b %Y")
    except Exception:
        pass
    return ""


def _nav_href_path(href: str) -> str:
    """Path portion of a nav href, normalized for comparison (no query/hash, trim slashes)."""
    if not href or str(href).strip().startswith("#"):
        return ""
    try:
        path = urlparse(str(href).strip()).path or ""
    except Exception:
        path = str(href).split("?")[0].split("#")[0]
    path = path.rstrip("/") or "/"
    return path


def _annotate_nav_active(sections: List[Dict[str, Any]], request_path: str) -> None:
    """
    Set item['active'] True for the best-matching link vs request_path (longest prefix wins).
    Mutates section dicts in place.
    """
    cur = (request_path or "").split("?")[0].split("#")[0].rstrip("/") or "/"
    candidates: List[Tuple[int, str, Dict[str, Any]]] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        items = sec.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            href = str(item.get("href") or "").strip()
            item["active"] = False
            if item.get("disabled"):
                continue
            # Quick-link items (e.g. "Add Counselor" → dash-url#ql-add-counselor)
            # should never be highlighted just because their host URL matches the
            # current path — they're actions, not navigation targets.
            if item.get("quicklink"):
                continue
            hpath = _nav_href_path(href)
            if hpath:
                candidates.append((len(hpath), hpath, item))

    best_path: Optional[str] = None
    for _ln, hpath, _it in sorted(candidates, key=lambda x: -x[0]):
        if hpath == "/":
            if cur == "/":
                best_path = "/"
                break
            continue
        if cur == hpath or cur.startswith(hpath + "/"):
            best_path = hpath
            break

    if not best_path:
        return
    for _ln, hpath, item in candidates:
        if hpath == best_path:
            item["active"] = True


def _institute_nav_gates(institute: Optional[Institute]) -> Dict[str, bool]:
    """
    Lightweight existence flags for progressive institute sidebar unlock.
    Uses short-circuiting .exists() queries only (no full counts / chart payloads).
    """
    empty = {"has_students": False, "has_counselors": False, "has_sessions": False}
    if not institute or not getattr(institute, "pk", None):
        return empty
    try:
        from django.db.models import Q

        from counselor.models import Counselor, FollowUpStatus
        from institute.models import StudentManagement

        inst_id = int(institute.pk)
        has_students = StudentManagement.objects.filter(institute_id=inst_id).exists()
        has_counselors = Counselor.objects.filter(
            Q(counselor_admin_id=inst_id) | Q(institute_placements__id=inst_id)
        ).exists()
        has_sessions = False
        if has_students or has_counselors:
            has_sessions = FollowUpStatus.objects.filter(
                Q(student__institute_id=inst_id)
                | Q(counselor__counselor_admin_id=inst_id)
                | Q(counselor__institute_placements__id=inst_id)
            ).exists()
        return {
            "has_students": bool(has_students),
            "has_counselors": bool(has_counselors),
            "has_sessions": bool(has_sessions),
        }
    except Exception:
        return empty


def _nav_item(
    *,
    label: str,
    href: str,
    unlocked: bool = True,
    lock_reason: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    """Build a nav item; locked items keep a visible label but cannot navigate."""
    item: Dict[str, Any] = {"label": label, "href": href if unlocked else "#", **extra}
    if not unlocked:
        item["disabled"] = True
        if lock_reason:
            item["title"] = lock_reason
    return item


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
                ],
            },
            {
                "title": "Courses",
                "items": [
                    {
                        "label": "My Enrolled Courses",
                        "dot": "#fb923c",
                        "href": _safe_reverse("counselor:enrolled_courses", args=[coun_id]) if coun_id else "#",
                    }
                ],
            },
        ]

    def _group_ql_href(page_url: str, hash_key: str) -> str:
        if not page_url or page_url == "#":
            return "#"
        return f"{page_url}#{hash_key}"

    if role == "institute_group":
        ig_institutes_url = _safe_reverse(
            "institute:institutegroupdashboard_page", args=["institutes"]
        )
        ig_counselors_url = _safe_reverse(
            "institute:institutegroupdashboard_page", args=["counselors"]
        )
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
                    {
                        "label": "Students",
                        "dot": "#f472b6",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["students"]),
                    },
                ],
            },
            {
                "title": "Guidance",
                "items": [
                    {
                        "label": "Session report",
                        "dot": "#fb923c",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["session_report"]),
                        "key": "sessions",
                    },
                ],
            },
            {
                "title": "Analytics",
                "items": [{"label": "Career heatmap", "dot": "#34d399", "href": _safe_reverse("institute:institutegroupheatmap")}],
            },
            {
                "title": "Quick actions",
                "items": [
                    {
                        "label": "Add Institute",
                        "icon": "bx bx-buildings",
                        "href": _group_ql_href(ig_institutes_url, "ql-add-institute"),
                        "quicklink": True,
                        "no_ajax": True,
                    },
                    {
                        "label": "Add Counselor",
                        "icon": "bx bx-user-voice",
                        "href": _group_ql_href(ig_counselors_url, "ql-add-counselor"),
                        "quicklink": True,
                        "no_ajax": True,
                    },
                ],
            },
            {
                "title": "Accounts",
                "items": [
                    {
                        "label": "Payments",
                        "dot": "#34d399",
                        "href": _safe_reverse("institute:institutegroupdashboard_page", args=["payments"]),
                    },
                ],
            },
        ]

    if role == "marketing_group":
        mktg_institutes_url = _safe_reverse(
            "institute:marketinggroupdashboard_page", args=["institutes"]
        )
        mktg_counselors_url = _safe_reverse(
            "institute:marketinggroupdashboard_page", args=["counselors"]
        )
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
                    {
                        "label": "Students",
                        "dot": "#f472b6",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["students"]),
                    },
                ],
            },
            {
                "title": "Guidance",
                "items": [
                    {
                        "label": "Session report",
                        "dot": "#fb923c",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["session_report"]),
                        "key": "sessions",
                    },
                ],
            },
            {
                "title": "Analytics",
                "items": [
                    {"label": "Career heatmap", "dot": "#34d399", "href": _safe_reverse("institute:marketinggroupheatmap")},
                    {
                        "label": "Institute credits",
                        "dot": "#22c55e",
                        "href": _safe_reverse("institute:marketinggroupdashboard_page", args=["credits"]),
                    },
                ],
            },
            {
                "title": "Quick actions",
                "items": [
                    {
                        "label": "Add Institute",
                        "icon": "bx bx-buildings",
                        "href": _group_ql_href(mktg_institutes_url, "ql-add-institute"),
                        "quicklink": True,
                        "no_ajax": True,
                    },
                    {
                        "label": "Add Counselor",
                        "icon": "bx bx-user-voice",
                        "href": _group_ql_href(mktg_counselors_url, "ql-add-counselor"),
                        "quicklink": True,
                        "no_ajax": True,
                    },
                ],
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

    # Default: institute — progressive unlock based on account data.
    dash_url = (
        _safe_reverse("institute:institute_masterdashboard", args=[inst_slug])
        if inst_slug
        else "#"
    )
    history_url = (
        _safe_reverse("institute:institutehistorylog", args=[inst_slug])
        if inst_slug
        else "#"
    )
    gates = _institute_nav_gates(institute)
    has_students = gates["has_students"]
    has_counselors = gates["has_counselors"]
    has_sessions = gates["has_sessions"]
    lock_students = "Enroll students (Class 10 / Class 12 CSV) to unlock this section."
    lock_counselors = "Add a counselor to unlock this section."
    lock_sessions = "Session reports unlock after counseling follow-ups are logged."
    lock_analytics = "Available after students are enrolled."
    lock_history = "Available after your first student upload."

    def _ql_href(hash_key: str) -> str:
        # Quick-link hash anchors live on the master dashboard. If we're already on
        # the dashboard the body's hash handler opens the modal; otherwise the
        # browser navigates to the dashboard and the role boot script opens it
        # after the partial loads.
        if not inst_slug or dash_url == "#":
            return "#"
        return f"{dash_url}#{hash_key}"

    return [
        {
            "title": "Reports",
            "items": [
                _nav_item(
                    label="Dashboard",
                    href=dash_url,
                    unlocked=True,
                    key="dashboard",
                    dot="#6c7dff",
                ),
                _nav_item(
                    label="Students",
                    href=_safe_reverse("institute:institutedashboard_page", args=[inst_slug, "students"])
                    if inst_slug
                    else "#",
                    unlocked=has_students,
                    lock_reason=lock_students,
                    key="students",
                    dot="#f472b6",
                ),
                _nav_item(
                    label="Counselors",
                    href=_safe_reverse("institute:institutedashboard_page", args=[inst_slug, "counselors"])
                    if inst_slug
                    else "#",
                    unlocked=has_counselors,
                    lock_reason=lock_counselors,
                    key="counselors",
                    dot="#4ade80",
                ),
                _nav_item(
                    label="Sessions",
                    href=_safe_reverse("institute:institutedashboard_page", args=[inst_slug, "sessions"])
                    if inst_slug
                    else "#",
                    unlocked=has_sessions,
                    lock_reason=lock_sessions,
                    key="institute_sessions",
                    dot="#fb923c",
                ),
            ],
        },
        {
            "title": "Guidance",
            "items": [
                _nav_item(
                    label="Session report",
                    href=_safe_reverse("institute:institutedashboard_page", args=[inst_slug, "session_report"])
                    if inst_slug
                    else "#",
                    unlocked=has_sessions,
                    lock_reason=lock_sessions,
                    key="sessions",
                    dot="#fb923c",
                ),
            ],
        },
        {
            "title": "Analytics",
            "items": [
                _nav_item(
                    label="Career heatmap",
                    href=_safe_reverse("institute:institutedashboard_page", args=[inst_slug, "heatmap"])
                    if inst_slug
                    else "#",
                    unlocked=has_students,
                    lock_reason=lock_analytics,
                    key="heatmap",
                    dot="#34d399",
                ),
                _nav_item(
                    label="Streams & capacity",
                    href=_safe_reverse(
                        "institute:institutedashboard_page", args=[inst_slug, "streams_capacity"]
                    )
                    if inst_slug
                    else "#",
                    unlocked=has_students,
                    lock_reason=lock_analytics,
                    key="streams_capacity",
                    dot="#a78bfa",
                ),
            ],
        },
        {
            "title": "Quick actions",
            "items": [
                {
                    "label": "Add Counselor",
                    "icon": "bx bx-user-voice",
                    "href": _ql_href("ql-add-counselor"),
                    "quicklink": True,
                    "no_ajax": True,
                    "disabled": not inst_slug,
                    "title": "" if inst_slug else "Institute not ready",
                },
                {
                    "label": "Matric-CSV Upload",
                    "icon": "bx bx-upload",
                    "href": _ql_href("ql-upload-matric"),
                    "quicklink": True,
                    "no_ajax": True,
                    "disabled": not inst_slug,
                    "title": "" if inst_slug else "Institute not ready",
                },
                {
                    "label": "Post-Matric-CSV Upload",
                    "icon": "bx bx-upload",
                    "href": _ql_href("ql-upload-postmatric"),
                    "quicklink": True,
                    "no_ajax": True,
                    "disabled": not inst_slug,
                    "title": "" if inst_slug else "Institute not ready",
                },
                _nav_item(
                    label="Uploaded History Log",
                    href=history_url,
                    unlocked=bool(inst_slug and has_students),
                    lock_reason=lock_history,
                    icon="bx bx-history",
                    quicklink=True,
                ),
            ],
        },
        {
            "title": "Billing",
            "items": [
                _nav_item(
                    label="Payments & invoices",
                    href=_safe_reverse("institute:institutedashboard_page", args=[inst_slug, "payments"])
                    if inst_slug
                    else "#",
                    unlocked=bool(inst_slug),
                    lock_reason="Institute not ready",
                    key="payments",
                    dot="#34d399",
                ),
            ],
        },
    ]


def ttv2_role_ctx(request) -> Dict[str, Any]:
    user = getattr(request, "user", None)
    page_loader_enabled = ttv2_page_loader_enabled()
    if not user or not getattr(user, "is_authenticated", False):
        return {
            "ttv2_role_ctx": {
                "role": "anonymous",
                "user": user,
                "nav": {"sections": []},
                "page_loader_enabled": page_loader_enabled,
            }
        }

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
    marketing_group = (
        _resolve_marketing_group_for_user(user) if role == "marketing_group" else None
    )
    institute_group = (
        _resolve_institute_group_for_user(user) if role == "institute_group" else None
    )
    institute = None
    if role == "counselor":
        institute = getattr(counselor, "counselor_admin", None) if counselor else None
    elif role == "institute":
        institute = _resolve_institute_from_request(request) or _resolve_institute_for_user(
            user
        )

    display_name = _display_name_for_user(user)
    sections = _nav_for_role(role=role, institute=institute, counselor=counselor)
    try:
        _annotate_nav_active(sections, getattr(request, "path", "") or "")
    except Exception:
        pass

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
            profile = {
                "name": _cname,
                "joined": _jn,
                "badge": _badge,
                "role_label": _profile_role_label(role),
            }
        elif role == "institute" and institute:
            tagline = "Institute Dashboard v2.0"
            profile = {
                "name": getattr(institute, "name", "") or "Institute",
                "joined": _format_joined_month_year(institute),
                "badge": "Active member",
                "role_label": _profile_role_label(role),
            }
        elif role == "institute_group":
            tagline = "Institute Group Dashboard v2.0"
            _gname = ""
            if institute_group:
                _gname = str(getattr(institute_group, "group_name", "") or "").strip()
            if not _gname:
                _gname = display_name
            _jn = _format_joined_month_year(institute_group) if institute_group else _format_joined_month_year(user)
            profile = {
                "name": _gname,
                "joined": _jn,
                "badge": "Active member",
                "role_label": _profile_role_label(role),
            }
        elif role == "marketing_group":
            tagline = "Marketing Dashboard v2.0"
            _gname = ""
            if marketing_group:
                _gname = str(getattr(marketing_group, "m_group_name", "") or "").strip()
            if not _gname:
                _gname = display_name
            _jn = _format_joined_month_year(marketing_group) if marketing_group else _format_joined_month_year(user)
            profile = {
                "name": _gname,
                "joined": _jn,
                "badge": "Active member",
                "role_label": _profile_role_label(role),
            }
    except Exception:
        profile = None

    permissions = {
        "can_edit_students": role == "institute",
        "can_block_students": role == "institute",
    }

    tieup_pay_cta = None
    try:
        if role == "institute" and institute:
            from institute.tieup_billing import tieup_pay_cta_for_institute

            tieup_pay_cta = tieup_pay_cta_for_institute(institute, user)
        elif role == "institute_group":
            from institute.tieup_billing import tieup_pay_cta_for_group_admin

            tieup_pay_cta = tieup_pay_cta_for_group_admin(user)
    except Exception:
        tieup_pay_cta = None

    out = {
        "ttv2_role_ctx": {
            "role": role,
            "user": user,
            "display_name": display_name,
            "institute": institute,
            "counselor": counselor,
            "marketing_group": marketing_group,
            "institute_group": institute_group,
            "tagline": tagline,
            "profile": profile,
            "nav": {"sections": sections},
            "permissions": permissions,
            "page_loader_enabled": page_loader_enabled,
        }
    }
    if tieup_pay_cta:
        out["ttv2_tieup_pay_cta"] = tieup_pay_cta
    return out

