from datetime import datetime, timedelta
import json
from django.shortcuts import render, redirect
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.generic import TemplateView,View
from counselor.models import Counselor, FollowUpStatus
from counselor.views import (
    get_students_by_role,
    apply_student_filters,
    get_class_and_sections_by_role,
    get_class_counts,
    get_results_data_for_students,
    get_unique_streams_by_role,
    build_students_analytics_payload,
)
from users.models import User, UserProfile
from core import choices
from psychometric_tests.models import PsychometricTestResult,CentralTestCandidate
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from core.utils import build_html_head, expand_eq_band_percentile
from django.contrib import messages
from .task import send_new_student_credential,institute_deletion_request,create_student_and_send_mail,send_institute_mail
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from institute.decorators import change_counselor_password_only, institute_user_only,institute_authenticated_user_only,institute_block_student_only,institute_update_delete_student_only,institute_change_student_password_only,institute_profile_update_delete, marketing_group_user_only,only_superuser,institute_group_user_only,superuser_or_marketing_institute_create
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.views import View
from institute.task import update_student_data,create_institute_log,send_institute_group_mail
from institute.models import Institute,StudentManagement,InstituteAccountDeletion,ClassAndSection,InstituteLog,get_global_remain_credits,InstituteGroup,InstituteMarketingGroup
from django.conf import settings
from django.http import HttpResponse
from institute.filters import StudentFilter
from institute.counselor_component_data import build_institute_group_counselor_ui_maps
from django.db import transaction
from django.db.models import Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Lower
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.views.decorators.http import require_GET
from app.models import Results, TestCompletion
from institute.utils import get_heatmap_data_for_group, get_heatmap_data_for_institute, get_empty_heatmap_data
# Dashboard template switch (v1/v2)
from core.models import Configuration
from core.ttv2_partial_request import request_wants_ttv2_dashboard_body_partial
# Create your views here.

def _ttv2_dbg(payload: dict):
    """DEBUG MODE: NDJSON log (session 80bb70). Avoid PII."""
    try:
        payload = payload or {}
        payload.setdefault("sessionId", "80bb70")
        payload.setdefault("timestamp", int(timezone.now().timestamp() * 1000))
        payload.setdefault("runId", payload.get("runId") or "pre-fix")
        with open(
            "/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/.cursor/debug-80bb70.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _sm_primary_psychometric_tests_complete_exists():
    """
    StudentManagement filter: linked student finished app psychometric battery
    (test1 + test2 + test3 on TestCompletion).
    """
    return Exists(
        TestCompletion.objects.filter(
            user_id=OuterRef("student_id"),
            test1_complete=True,
            test2_complete=True,
            test3_complete=True,
        )
    )


def _ttv2_week_start_from_request(request):
    """
    Parse ?ttv2_week_start=YYYY-MM-DD (Monday) into a date, or None.
    Used by template-v2 analytics to show a selected week range.
    """
    raw = (request.GET.get("ttv2_week_start") or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except Exception:
        return None


def _ttv2_date_range_from_request(request):
    """
    Parse ?ttv2_date_start=YYYY-MM-DD&ttv2_date_end=YYYY-MM-DD, or fallback to week start.
    Returns tuple(date_start, date_end) where either can be None.
    """
    raw_start = (request.GET.get("ttv2_date_start") or "").strip()
    raw_end = (request.GET.get("ttv2_date_end") or "").strip()
    if raw_start and raw_end:
        try:
            ds = datetime.strptime(raw_start, "%Y-%m-%d").date()
            de = datetime.strptime(raw_end, "%Y-%m-%d").date()
            return ds, de
        except Exception:
            return None, None
    wk = _ttv2_week_start_from_request(request)
    if wk:
        return wk, wk + timedelta(days=6)
    return None, None


def _followup_for_institute_counselors_q(institute):
    """Follow-ups logged by counselors placed at this institute (primary or group placement)."""
    return Q(counselor__counselor_admin=institute) | Q(
        counselor__institute_placements=institute
    )


def _counselor_group_assigned_institute_ids(counselor, group_institute_ids):
    """Institute ids in this group where counselor has primary or additional placement."""
    gset = {int(x) for x in group_institute_ids}
    if not gset:
        return set()
    out = set()
    cid = counselor.counselor_admin_id
    if cid and cid in gset:
        out.add(cid)
    for iid in counselor.institute_placements.filter(pk__in=gset).values_list(
        "pk", flat=True
    ):
        out.add(int(iid))
    return out


def _counselor_belongs_to_institute_group_admin(counselor, group_admin_user):
    inst = counselor.counselor_admin
    if inst and inst.institute_group_id:
        ig = inst.institute_group
        if getattr(ig, "institute_group_admin_id", None) == group_admin_user.id:
            return True
    for inst in counselor.institute_placements.select_related("institute_group").all():
        ig = getattr(inst, "institute_group", None)
        if ig and getattr(ig, "institute_group_admin_id", None) == group_admin_user.id:
            return True
    dg = getattr(counselor, "detached_from_institute_group", None)
    return bool(
        dg and getattr(dg, "institute_group_admin_id", None) == group_admin_user.id
    )


def _counselor_profile_editable_by_user(user, counselor):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    inst = counselor.counselor_admin
    if inst:
        if user == inst.created_by:
            return True
        ig = inst.institute_group
        if ig and ig.institute_group_admin_id == user.id:
            return True
    for inst in counselor.institute_placements.all():
        if user == inst.created_by:
            return True
        ig = getattr(inst, "institute_group", None)
        if ig and ig.institute_group_admin_id == user.id:
            return True
    dg = getattr(counselor, "detached_from_institute_group", None)
    if dg and dg.institute_group_admin_id == user.id:
        return True
    return False


def _canonical_counselor_row(source_coun):
    if source_coun.coun_user_id:
        row = (
            Counselor.objects.filter(coun_user_id=source_coun.coun_user_id)
            .order_by("id")
            .first()
        )
        if row:
            return row
    email = (source_coun.counselor_email or "").strip()
    if email:
        row = (
            Counselor.objects.filter(counselor_email__iexact=email)
            .order_by("id")
            .first()
        )
        if row:
            return row
    return source_coun


def _ensure_counselor_clone_for_institute(source_coun, target_institute):
    """
    Ensure the counselor identity from source_coun is available at target_institute
    without creating duplicate Counselor rows: use counselor_admin plus institute_placements.
    """
    canon = _canonical_counselor_row(source_coun)
    if canon.counselor_admin_id == target_institute.id:
        return canon
    if canon.institute_placements.filter(pk=target_institute.pk).exists():
        return canon
    if canon.counselor_admin_id is None:
        canon.counselor_admin = target_institute
        canon.detached_from_institute_group = None
        canon.save(
            update_fields=["counselor_admin", "detached_from_institute_group"]
        )
        return canon
    canon.institute_placements.add(target_institute)
    return canon


def _search_suggest_limit(request, default=20, cap=40):
    try:
        n = int(request.GET.get("limit", default))
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, cap))


def _normalize_class_and_section_value(value):
    value = (value or "").strip()
    return value or None


def _resolve_class_and_section(class_section, stream=None):
    """
    Reuse the first matching ClassAndSection when legacy duplicate rows already
    exist, instead of letting get_or_create() raise MultipleObjectsReturned.
    """
    class_section = _normalize_class_and_section_value(class_section)
    stream = _normalize_class_and_section_value(stream)

    if not class_section:
        return None, False

    base_qs = ClassAndSection.objects.filter(class_and_section=class_section).order_by("id")

    if stream:
        existing = base_qs.filter(stream=stream).first()
        if existing:
            return existing, False
        return ClassAndSection.objects.create(class_and_section=class_section, stream=stream), True

    existing = base_qs.filter(Q(stream__isnull=True) | Q(stream="")).first()
    if existing:
        return existing, False

    existing = base_qs.first()
    if existing:
        return existing, False

    return ClassAndSection.objects.create(class_and_section=class_section), True


@require_GET
def marketing_search_suggest(request):
    """JSON autocomplete for marketing-scoped institute filters (min 3 chars)."""
    if not request.user.is_authenticated:
        return JsonResponse({"suggestions": []}, status=401)
    if request.user.user_type != choices.UserType.MARKETINGGROUPADMIN:
        return JsonResponse({"suggestions": []}, status=403)
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"suggestions": []})
    q_lower = q.lower()
    kind = (request.GET.get("kind") or "").strip().lower()
    lim = _search_suggest_limit(request)
    base = Institute.objects.filter(marketing_group__marketing_group_admin=request.user)
    suggestions = []
    if kind == "institute_name":
        names = (
            base.exclude(name__isnull=True)
            .exclude(name="")
            .annotate(_name_lc=Lower("name"))
            .filter(_name_lc__contains=q_lower)
            .values_list("name", flat=True)
            .distinct()[: lim * 2]
        )
        seen = set()
        for n in names:
            t = (n or "").strip()
            if not t:
                continue
            k = t.lower()
            if k in seen:
                continue
            seen.add(k)
            suggestions.append(t)
            if len(suggestions) >= lim:
                break
    elif kind == "location":
        loc_seen = set()
        for addr in (
            base.exclude(address__isnull=True)
            .exclude(address="")
            .annotate(_addr_lc=Lower("address"))
            .filter(_addr_lc__contains=q_lower)
            .values_list("address", flat=True)
            .distinct()[: lim * 2]
        ):
            t = (addr or "").strip()
            if not t:
                continue
            k = t.lower()
            if k in loc_seen:
                continue
            loc_seen.add(k)
            suggestions.append(t)
            if len(suggestions) >= lim:
                break
    elif kind == "counselor":
        iids = base.values_list("id", flat=True)
        cq = (
            Counselor.objects.filter(counselor_admin_id__in=iids)
            .annotate(
                _cn_lc=Lower("counselor_name"),
                _ce_lc=Lower("counselor_email"),
            )
            .filter(Q(_cn_lc__contains=q_lower) | Q(_ce_lc__contains=q_lower))
            .order_by("counselor_name")[: lim * 2]
        )
        seen = set()
        for c in cq:
            label = (c.counselor_name or "").strip()
            em = (c.counselor_email or "").strip()
            if em and em.lower() not in label.lower():
                label = f"{label} ({em})" if label else em
            if not label:
                continue
            lk = label.lower()
            if lk in seen:
                continue
            seen.add(lk)
            suggestions.append(label)
            if len(suggestions) >= lim:
                break
    return JsonResponse({"suggestions": suggestions})


@require_GET
def institute_group_search_suggest(request):
    """JSON autocomplete for institute-group-scoped filters (min 3 chars)."""
    if not request.user.is_authenticated:
        return JsonResponse({"suggestions": []}, status=401)
    if request.user.user_type != choices.UserType.INSTITUTEGROUPADMIN:
        return JsonResponse({"suggestions": []}, status=403)
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"suggestions": []})
    q_lower = q.lower()
    kind = (request.GET.get("kind") or "").strip().lower()
    lim = _search_suggest_limit(request)
    base = Institute.objects.filter(institute_group__institute_group_admin=request.user)
    suggestions = []
    if kind == "institute_name":
        seen = set()
        for n in (
            base.exclude(name__isnull=True)
            .exclude(name="")
            .annotate(_name_lc=Lower("name"))
            .filter(_name_lc__contains=q_lower)
            .values_list("name", flat=True)
            .distinct()[: lim * 2]
        ):
            t = (n or "").strip()
            if not t:
                continue
            k = t.lower()
            if k in seen:
                continue
            seen.add(k)
            suggestions.append(t)
            if len(suggestions) >= lim:
                break
    elif kind == "location":
        loc_seen = set()
        for addr in (
            base.exclude(address__isnull=True)
            .exclude(address="")
            .annotate(_addr_lc=Lower("address"))
            .filter(_addr_lc__contains=q_lower)
            .values_list("address", flat=True)
            .distinct()[: lim * 2]
        ):
            t = (addr or "").strip()
            if not t:
                continue
            k = t.lower()
            if k in loc_seen:
                continue
            loc_seen.add(k)
            suggestions.append(t)
            if len(suggestions) >= lim:
                break
    elif kind == "counselor":
        iids = base.values_list("id", flat=True)
        cq = (
            Counselor.objects.filter(counselor_admin_id__in=iids)
            .annotate(
                _cn_lc=Lower("counselor_name"),
                _ce_lc=Lower("counselor_email"),
            )
            .filter(Q(_cn_lc__contains=q_lower) | Q(_ce_lc__contains=q_lower))
            .order_by("counselor_name")[: lim * 2]
        )
        seen = set()
        for c in cq:
            label = (c.counselor_name or "").strip()
            em = (c.counselor_email or "").strip()
            if em and em.lower() not in label.lower():
                label = f"{label} ({em})" if label else em
            if not label:
                continue
            lk = label.lower()
            if lk in seen:
                continue
            seen.add(lk)
            suggestions.append(label)
            if len(suggestions) >= lim:
                break
    return JsonResponse({"suggestions": suggestions})


@require_GET
def admin_institute_search_suggest(request):
    """Superuser-only institute name suggest for admin dashboard search."""
    if not request.user.is_authenticated:
        return JsonResponse({"suggestions": []}, status=401)
    if not request.user.is_superuser:
        return JsonResponse({"suggestions": []}, status=403)
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"suggestions": []})
    q_lower = q.lower()
    lim = _search_suggest_limit(request)
    qs = (
        Institute.objects.select_related("created_by")
        .annotate(
            _iname_lc=Lower("name"),
            _cb_email_lc=Lower("created_by__email"),
            _cb_name_lc=Lower("created_by__name"),
        )
        .filter(
            Q(_iname_lc__contains=q_lower)
            | Q(_cb_email_lc__contains=q_lower)
            | Q(_cb_name_lc__contains=q_lower)
        )
        .order_by("name")[: lim * 2]
    )
    seen = set()
    suggestions = []
    for inst in qs:
        t = (inst.name or "").strip()
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        suggestions.append(t)
        if len(suggestions) >= lim:
            break
    return JsonResponse({"suggestions": suggestions})


@require_GET
def institute_student_name_suggest(request, slug):
    """Suggest student display strings for the institute student name filter (min 3 chars)."""
    institute = get_object_or_404(Institute, slug=slug)
    if not user_manages_institute_for_api(request.user, institute):
        return JsonResponse({"suggestions": []}, status=403)
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"suggestions": []})
    q_lower = q.lower()
    lim = _search_suggest_limit(request)
    sms = (
        StudentManagement.objects.filter(institute=institute)
        .select_related("student", "class_and_section")
        .annotate(
            _sn_lc=Lower("student__name"),
            _se_lc=Lower("student__email"),
            _su_lc=Lower("student__username"),
            _sc_lc=Lower("class_and_section__class_and_section"),
        )
        .filter(
            Q(_sn_lc__contains=q_lower)
            | Q(_se_lc__contains=q_lower)
            | Q(_su_lc__contains=q_lower)
            | Q(_sc_lc__contains=q_lower)
        )[: lim * 3]
    )
    seen = set()
    suggestions = []
    for sm in sms:
        u = sm.student
        if not u:
            continue
        name = (getattr(u, "name", None) or "").strip()
        email = (getattr(u, "email", None) or "").strip()
        label = name or email or (getattr(u, "username", None) or "").strip()
        if name and email and name.lower() != email.lower():
            label = f"{name} ({email})"
        if not label:
            continue
        lk = label.lower()
        if lk in seen:
            continue
        seen.add(lk)
        suggestions.append(label)
        if len(suggestions) >= lim:
            break
    return JsonResponse({"suggestions": suggestions})


def build_ttv2_quicklink_institutes(user):
    """Institutes in admin scope with allocated / used / remaining credits."""
    from core.ttv2_institute_credits import build_ttv2_quicklink_institutes as _build

    return _build(user)


def user_manages_institute_for_api(user, institute):
    """
    True if the user may read institute/student API payloads for this institute.
    Scopes marketing, institute-group, school, and counselor roles to their own institutes.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if institute.created_by_id == user.id:
        return True
    if institute.institute_group_id and institute.institute_group.institute_group_admin_id == user.id:
        return True
    if institute.marketing_group_id and institute.marketing_group.marketing_group_admin_id == user.id:
        return True
    if Counselor.qs_for_institute(institute).filter(coun_user=user).exists():
        return True
    return False


def _normalize_csv_mobile_digits(raw):
    """Strip non-digits and normalize common Indian prefixes for validation."""
    import re

    if raw is None:
        return ""
    digits = re.sub(r"\D+", "", str(raw).strip())
    if len(digits) >= 12 and digits.startswith("91"):
        digits = digits[-10:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    elif len(digits) > 10:
        digits = digits[-10:]
    return digits


def _csv_indian_mobile_ok(norm: str) -> bool:
    import re

    return bool(re.match(r"^[6789]\d{9}$", norm))


def user_can_bulk_upload_students_for_institute(request, institute) -> bool:
    """CSV bulk-upload permission aligned with roster/API institute scope."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_manages_institute_for_api(request.user, institute)


def _institute_logo_url_safe(institute) -> str:
    try:
        if institute and getattr(institute, "logo", None):
            return institute.logo.url or ""
    except Exception:
        pass
    return ""
    """
    Augment results_data for student roster (list + cards). Shared across roles.
    """
    try:
        from colleges.models import CollegeShortlist
        from core.models import MIAssessmentResult, EQAssessmentResult

        uids = []
        for sm in (ctx.get("students") or []):
            try:
                if sm and getattr(sm, "student_id", None):
                    uids.append(int(sm.student_id))
            except Exception:
                continue
        uids = list({x for x in uids if x})
        abroad_uids = set()
        if uids:
            qs = (
                CollegeShortlist.objects.filter(user_id__in=uids)
                .select_related("college", "college__country")
            )
            for cs in qs:
                try:
                    c = cs.college
                    country = getattr(c, "country", None) if c else None
                    name = (getattr(country, "name", "") or "").strip().lower()
                    short = (getattr(country, "short_name", "") or "").strip().lower()
                    if country and name and name != "india" and short != "in":
                        abroad_uids.add(int(cs.user_id))
                except Exception:
                    continue
        mi_uids = set()
        eq_uids = set()
        try:
            if uids:
                mi_uids = set(
                    MIAssessmentResult.objects.filter(user_id__in=uids)
                    .values_list("user_id", flat=True)
                    .distinct()
                )
                eq_uids = set(
                    EQAssessmentResult.objects.filter(user_id__in=uids)
                    .values_list("user_id", flat=True)
                    .distinct()
                )
        except Exception:
            mi_uids, eq_uids = set(), set()
        results_data = ctx.get("results_data") or {}
        for sm in (ctx.get("students") or []):
            try:
                uid = int(sm.student_id) if sm and sm.student_id else None
            except Exception:
                uid = None
            if not uid:
                continue
            student_user = getattr(sm, "student", None) if sm else None
            rd = results_data.get(uid) or (results_data.get(student_user) if student_user else None) or {}
            try:
                cas = getattr(sm, "class_and_section", None)
                rd.setdefault("track", (getattr(cas, "stream", "") or "").strip() or "")
            except Exception:
                rd.setdefault("track", "")
            rd.setdefault("match_pct", rd.get("match_pct") or "")
            rd.setdefault("risk_score", rd.get("risk_score") or "")

            td = rd.get("test_details") if isinstance(rd, dict) else {}
            if not isinstance(td, dict):
                td = {}

            def _attempted(v):
                try:
                    s = (str(v or "")).strip().lower()
                except Exception:
                    s = ""
                return bool(v is True or s in ("1", "true", "yes", "y", "completed", "complete", "done", "attempted"))

            # Primary source: dedicated MI/EQ assessment rows.
            mi_attempted = True if uid in mi_uids else False
            eq_attempted = True if uid in eq_uids else False

            # Fallback source: older payloads may store explicit MI/EQ keys directly.
            # Do not infer MI/EQ from other psychometric tests like personality/test1.
            if not mi_attempted:
                mi_attempted = any([
                    _attempted(td.get("mi_assessment")),
                    _attempted(td.get("multiple_intelligence_assessment")),
                ])
            if not eq_attempted:
                eq_attempted = any([
                    _attempted(td.get("eq_assessment")),
                    _attempted(td.get("emotional_intelligence_assessment")),
                ])

            rd["mi_attempted"] = mi_attempted
            rd["eq_attempted"] = eq_attempted
            rd["mi_report_url"] = (
                "%s?inline=1" % reverse("core:mi_report_pdf_user", args=[uid]) if mi_attempted else ""
            )
            rd["eq_report_url"] = (
                "%s?inline=1" % reverse("core:eq_report_pdf_user", args=[uid]) if eq_attempted else ""
            )
            rd["abroad_exploring"] = True if uid in abroad_uids else False
            results_data[uid] = rd
            if student_user:
                results_data[student_user] = rd
        ctx["results_data"] = results_data
    except Exception:
        pass


def _render_ttv2_tieup_payments_partial(request, ctx):
    """AJAX fragment for tie-up payments status tabs (no full dashboard reload)."""
    if (ctx.get("ttv2_page") or "").strip().lower() != "payments":
        return None
    if (request.GET.get("ttv2_payments_partial") or "").strip() != "1":
        return None
    if ctx.get("is_group_view"):
        template = "template_v2/institute/pages/institute_tieup_payment_history.html"
    elif "/marketing_group_dashboard/" in (request.path or ""):
        template = "template_v2/institute/pages/marketing_group_tieup_payments.html"
    else:
        template = "template_v2/institute/pages/institute_tieup_payment_history.html"
    return render(request, template, ctx)


def _resolve_dashboard_institute_from_request(request):
    """Institute from ?institute_slug= when the user may access it (marketing / group)."""
    raw = (request.GET.get("institute_slug") or "").strip()
    if not raw:
        return None
    inst = Institute.objects.filter(slug=raw).first()
    if inst and user_manages_institute_for_api(request.user, inst):
        return inst
    return None


def scoped_student_management_for_dashboard(request):
    """
    Role-scoped StudentManagement queryset for marketing / institute-group dashboards.
    Optional GET institute_slug=... narrows to one institute when the user may access it.
    """
    inst = _resolve_dashboard_institute_from_request(request)
    if inst:
        return get_students_by_role(request.user, counselor=None, institute=inst)
    if request.user.user_type == choices.UserType.INSTITUTEGROUPADMIN:
        return student_management_for_institute_group_admin(request.user)
    return get_students_by_role(request.user, counselor=None, institute=None)


def _ttv2_marketing_counselor_followups_response(request, group_admin):
    """
    JSON rows for marketing counselors drill-down modal (scoped follow-ups or roster).
    GET: counselor_id, counselor_activity=followups|completed|assigned
    """
    raw_id = (request.GET.get("counselor_id") or "").strip()
    activity = (request.GET.get("counselor_activity") or "").strip().lower()
    if not raw_id.isdigit() or activity not in ("followups", "completed", "assigned"):
        return JsonResponse({"ok": False, "error": "invalid_params"}, status=400)
    cid = int(raw_id)

    scoped_inst = Institute.objects.filter(marketing_group__marketing_group_admin=group_admin)
    scoped_ids = list(scoped_inst.values_list("id", flat=True))
    if not scoped_ids:
        return JsonResponse(
            {
                "ok": True,
                "counselor_name": "",
                "institute_name": "",
                "rows": [],
            }
        )

    counselor = (
        Counselor.objects.filter(
            Q(counselor_admin_id__in=scoped_ids) | Q(institute_placements__id__in=scoped_ids),
            id=cid,
        )
        .select_related("counselor_admin")
        .prefetch_related("institute_placements")
        .distinct()
        .first()
    )
    if not counselor:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    id_set = set(scoped_ids)
    inst_name = "—"
    admin = None
    if counselor.counselor_admin_id and counselor.counselor_admin_id in id_set:
        admin = counselor.counselor_admin
    if admin is None:
        for inst in counselor.institute_placements.all():
            if inst.id in id_set:
                admin = inst
                break
    if admin is not None:
        inst_name = getattr(admin, "name", "") or "—"

    if activity == "assigned":
        sms = (
            StudentManagement.objects.filter(institute_id__in=scoped_ids)
            .filter(Q(counselor_id=cid) | Q(counselors__id=cid))
            .select_related("student", "class_and_section")
            .prefetch_related("counselors")
            .distinct()
            .order_by("-created")[:400]
        )
        rows = []
        for i, sm in enumerate(sms, start=1):
            stu = getattr(sm, "student", None)
            name = (getattr(stu, "name", None) or "").strip() or "—"
            cas = getattr(sm, "class_and_section", None)
            cls_txt = (getattr(cas, "class_and_section", None) or "").strip() if cas else ""
            stream = (getattr(cas, "stream", None) or "").strip() if cas else ""
            class_parts = [x for x in [cls_txt, stream] if x]
            class_str = " · ".join(class_parts) if class_parts else "—"
            is_primary = getattr(sm, "counselor_id", None) == cid
            in_m2m = any(c.id == cid for c in sm.counselors.all())
            if is_primary and in_m2m:
                kind = "Primary advisor · Roster"
            elif is_primary:
                kind = "Primary advisor"
            elif in_m2m:
                kind = "Roster advisor"
            else:
                kind = "Assigned"
            try:
                dt = timezone.localtime(sm.created)
                when = dt.strftime("%d %b %Y, %H:%M")
            except Exception:
                when = ""
            rows.append(
                {
                    "sno": i,
                    "name": name,
                    "class": class_str,
                    "kind": kind,
                    "when": when,
                }
            )
        return JsonResponse(
            {
                "ok": True,
                "counselor_name": (counselor.counselor_name or "").strip() or f"Counselor {cid}",
                "institute_name": inst_name,
                "rows": rows,
            }
        )

    fu = (
        FollowUpStatus.objects.filter(
            counselor_id=cid,
            student__institute_id__in=scoped_ids,
            student_id__isnull=False,
        )
        .select_related("student", "student__student", "student__class_and_section")
    )
    if activity == "completed":
        fu = fu.filter(follow_up_status__iexact="completed")
    fu = fu.order_by("-created")[:400]

    mode_labels = dict(FollowUpStatus.MODE_CHOICES)
    status_labels = dict(FollowUpStatus.STATUS_CHOICES)

    rows = []
    for i, f in enumerate(fu, start=1):
        sm = f.student
        stu = getattr(sm, "student", None) if sm else None
        name = (getattr(stu, "name", None) or "").strip() or "—"
        cas = getattr(sm, "class_and_section", None) if sm else None
        cls_txt = (getattr(cas, "class_and_section", None) or "").strip() if cas else ""
        stream = (getattr(cas, "stream", None) or "").strip() if cas else ""
        class_parts = [x for x in [cls_txt, stream] if x]
        class_str = " · ".join(class_parts) if class_parts else "—"
        mode_raw = (getattr(f, "mode_of_follow_up", None) or "").strip()
        stat_raw = (getattr(f, "follow_up_status", None) or "").strip()
        mode_disp = mode_labels.get(mode_raw, mode_raw.title() if mode_raw else "—")
        stat_disp = status_labels.get(stat_raw, stat_raw.title() if stat_raw else "—")
        kind = f"{mode_disp} · {stat_disp}"
        try:
            dt = timezone.localtime(f.created)
            when = dt.strftime("%d %b %Y, %H:%M")
        except Exception:
            when = ""

        rows.append(
            {
                "sno": i,
                "name": name,
                "class": class_str,
                "kind": kind,
                "when": when,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "counselor_name": (counselor.counselor_name or "").strip() or f"Counselor {cid}",
            "institute_name": inst_name,
            "rows": rows,
        }
    )


def apply_student_table_display_enrichment(request, ctx):
    """
    Normalize roster AJAX context for shared student table / card templates.

    Counselor dashboards pass remark and follow-up POST URLs from counselor.views.
    Institute and group/marketing rosters mostly rely on ``table_config``; this
    hook remains for shared defaults and future role-specific URLs.
    """
    if not isinstance(ctx, dict):
        return


def _ttv2_counselor_dropdown_row(
    c_id, counselor_nm=None, institute_id=None, institute_nm_suffix=None
):
    """
    Serialize one counselor `<option>` for Jinja/HTML.

    Prefer ``counselor_label`` instead of relying on dict key ``name`` with
    ``{{ c.name }}`` (ambiguous with Django models such as Institute that expose
    a real ``name`` field).

    Multi-school views may pass ``institute_nm_suffix`` for disambiguation
    ("Advisor — School" reads counselor-first).
    """
    cid = int(c_id)
    label = ((counselor_nm or "").strip()) or f"Counselor {cid}"
    suf = (institute_nm_suffix or "").strip() if institute_nm_suffix is not None else ""
    if suf and suf != "—":
        label = f"{label} — {suf}"
    row = {"id": cid, "counselor_label": label}
    if institute_id is not None:
        row["institute_id"] = int(institute_id)
    return row


def _ttv2_counselor_options_by_institute_id(page_list):
    """Dropdown options for assigning counselors on roster rows (group / multi-school views)."""
    ids = {getattr(sm, "institute_id", None) for sm in page_list}
    ids.discard(None)
    if not ids:
        return {}
    id_list = [int(x) for x in ids]
    id_set = set(id_list)
    out = {}
    counselors = (
        Counselor.objects.filter(
            Q(counselor_admin_id__in=id_list)
            | Q(institute_placements__id__in=id_list)
        )
        .prefetch_related("institute_placements")
        .distinct()
        .only("id", "counselor_name", "counselor_admin_id")
        .order_by(Lower("counselor_name"))
    )
    for row in counselors:
        placed = set()
        if row.counselor_admin_id and row.counselor_admin_id in id_set:
            placed.add(int(row.counselor_admin_id))
        for inst in row.institute_placements.all():
            if inst.id in id_set:
                placed.add(int(inst.id))
        for iid in placed:
            bucket = out.setdefault(str(iid), [])
            if any(int(x.get("id", 0)) == int(row.id) for x in bucket):
                continue
            bucket.append(
                _ttv2_counselor_dropdown_row(
                    row.id, getattr(row, "counselor_name", None)
                )
            )
    return out


def _ttv2_fill_institute_group_session_report_ctx(
    request, group_admin, ctx, ig_institutes_qs
):
    """
    Session report for institute-group admins: follow-ups for students in any school
    in the group (not scoped to a single institute row).
    """
    from django.db import models as _models
    from django.db.models.functions import Coalesce, TruncDate

    from counselor.models import Counselor as _Counselor

    ctx["ttv2_session_report_subtitle"] = (
        "Showing counselor follow-ups for students across your institute group."
    )

    _sm_ig = student_management_for_institute_group_admin(group_admin)
    sm_ids = list(_sm_ig.values_list("id", flat=True))

    raw_from = (request.GET.get("from") or "").strip()
    raw_to = (request.GET.get("to") or "").strip()
    raw_coun = (request.GET.get("counselor") or "").strip()
    raw_mode = (request.GET.get("mode") or "").strip()
    raw_status = (request.GET.get("status") or "").strip()
    raw_class = (request.GET.get("class") or "").strip()
    date_from = None
    date_to = None
    try:
        if raw_from:
            date_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
    except Exception:
        date_from = None
    try:
        if raw_to:
            date_to = datetime.strptime(raw_to, "%Y-%m-%d").date()
    except Exception:
        date_to = None

    iids = list(ig_institutes_qs.values_list("id", flat=True))
    try:
        ctx["ttv2_session_report_counselors"] = list(
            _Counselor.objects.filter(
                Q(counselor_admin_id__in=iids)
                | Q(institute_placements__id__in=iids)
            )
            .distinct()
            .order_by("counselor_name")
            .values("id", name=F("counselor_name"))
        )
    except Exception:
        ctx["ttv2_session_report_counselors"] = []

    rows = []
    if sm_ids:
        try:
            qs = (
                FollowUpStatus.objects.filter(student_id__in=sm_ids)
                .select_related("counselor", "student", "student__student")
                .annotate(
                    _sess_day=Coalesce(
                        "last_follow_up_date",
                        TruncDate("created"),
                        output_field=_models.DateField(),
                    )
                )
            )
            if date_from:
                qs = qs.filter(_sess_day__gte=date_from)
            if date_to:
                qs = qs.filter(_sess_day__lte=date_to)
            if raw_coun:
                try:
                    qs = qs.filter(counselor_id=int(raw_coun))
                except Exception:
                    pass
            if raw_mode:
                qs = qs.filter(mode_of_follow_up__iexact=raw_mode)
            if raw_status:
                qs = qs.filter(follow_up_status__iexact=raw_status)
            if raw_class:
                try:
                    qs = qs.filter(student__class_and_section_id=int(raw_class))
                except Exception:
                    pass
            qs = qs.order_by("-_sess_day", "-created")[:200]
            for fu in qs:
                sm = getattr(fu, "student", None)
                u = getattr(sm, "student", None) if sm else None
                rows.append(
                    {
                        "when": getattr(fu, "last_follow_up_date", None).strftime("%Y-%m-%d")
                        if getattr(fu, "last_follow_up_date", None)
                        else (
                            getattr(fu, "created", None).strftime("%Y-%m-%d")
                            if getattr(fu, "created", None)
                            else "-"
                        ),
                        "counselor": getattr(getattr(fu, "counselor", None), "counselor_name", None)
                        or "-",
                        "student": getattr(u, "name", None)
                        or getattr(u, "email", None)
                        or (getattr(sm, "student_name", None) if sm else None)
                        or "-",
                        "mode": getattr(fu, "mode_of_follow_up", None) or "-",
                        "status": getattr(fu, "follow_up_status", None) or "-",
                        "next": getattr(fu, "next_follow_up_date", None).strftime("%Y-%m-%d")
                        if getattr(fu, "next_follow_up_date", None)
                        else "-",
                    }
                )
        except Exception:
            rows = []

    ctx["ttv2_sessions_is_dummy"] = False
    ctx["ttv2_sessions"] = rows
    ctx["ttv2_session_report_rows"] = rows
    ctx["ttv2_sessions_filters"] = {
        "from": raw_from,
        "to": raw_to,
        "counselor": raw_coun,
        "mode": raw_mode,
        "status": raw_status,
        "class": raw_class,
    }

    try:
        _ttv2_fill_session_report_rich_from_student_scope(
            request,
            ctx,
            _sm_ig.select_related("student", "class_and_section", "institute"),
        )
    except Exception:
        ctx.setdefault("ttv2_sessions_kpis", {})
        ctx.setdefault("ttv2_sessions_mtd_rows", [])
        ctx.setdefault("ttv2_sessions_students", [])
        ctx.setdefault("ttv2_sessions_month_label", "")
        ctx.setdefault("ttv2_sessions_weekly_note", "—")
        ctx.setdefault("ttv2_sessions_next_actions", [])


def _ttv2_fill_session_report_rich_from_student_scope(request, ctx, sm_qs):
    """
    KPI + month-to-date + student cards for session report, scoped by StudentManagement queryset
    (institute group, marketing group, or any multi-school scope). Matches InstituteDashboardView
    session_report rich block but uses follow-ups for students in sm_qs only.
    """
    import calendar

    from django.db import models as _models
    from django.db.models import Count, Q
    from django.db.models.functions import Coalesce, TruncDate

    if sm_qs is None:
        raise ValueError("sm_qs required")

    sm_ids = list(sm_qs.values_list("id", flat=True))
    total_students = int(len(sm_ids))

    today = timezone.localdate()
    week_start = _ttv2_week_start_from_request(request) or (today - timedelta(days=today.weekday()))
    week_end = week_start + timedelta(days=6)

    fu_base = FollowUpStatus.objects.filter(student_id__in=sm_ids).annotate(
        _sess_day=Coalesce(
            "last_follow_up_date",
            TruncDate("created"),
            output_field=_models.DateField(),
        )
    )

    fu_week = fu_base.filter(_sess_day__gte=week_start, _sess_day__lte=week_end)
    sessions_week = int(fu_week.count())
    completed_week = int(fu_week.filter(follow_up_status="completed").count())
    unique_students_week = int(fu_week.values("student_id").distinct().count())
    completion_rate = int(round((100.0 * completed_week / sessions_week), 0)) if sessions_week else 0

    upcoming = 0
    try:
        upcoming = int(
            FollowUpStatus.objects.filter(
                student_id__in=sm_ids,
                next_follow_up_date__isnull=False,
                next_follow_up_date__gte=today,
            )
            .values("student_id")
            .distinct()
            .count()
        )
    except Exception:
        upcoming = 0

    ctx["ttv2_sessions_kpis"] = {
        "sessions_week": sessions_week,
        "unique_students_week": unique_students_week,
        "completed_week": completed_week,
        "completion_rate_week": completion_rate,
        "upcoming_followups": upcoming,
    }

    month_ref = week_start or today
    month_first = month_ref.replace(day=1)
    month_last = month_ref.replace(day=calendar.monthrange(month_ref.year, month_ref.month)[1])
    month_end = (
        min(today, month_last)
        if (month_ref.year == today.year and month_ref.month == today.month)
        else month_last
    )

    def _month_week_ranges(start_d, end_d):
        out = []
        cur = start_d
        idx = 1
        while cur <= end_d:
            nxt = min(end_d, cur + timedelta(days=6))
            out.append((idx, cur, nxt))
            idx += 1
            cur = nxt + timedelta(days=1)
        return out

    month_weeks = _month_week_ranges(month_first, month_end)
    fu_month = fu_base.filter(_sess_day__gte=month_first, _sess_day__lte=month_end)

    try:
        clarity_gap = float((ctx.get("ttv2_analytics") or {}).get("kpi", {}).get("clarity_gap", 0) or 0)
    except Exception:
        clarity_gap = 0.0
    try:
        test_completion = int((ctx.get("ttv2_analytics") or {}).get("kpi", {}).get("psych_pct", 0) or 0)
    except Exception:
        test_completion = 0

    mtd_rows = []
    for widx, ws, we in month_weeks:
        try:
            qs_w = fu_month.filter(_sess_day__gte=ws, _sess_day__lte=we)
            sessions_cnt = int(qs_w.count())
            students_reached = int(qs_w.values("student_id").distinct().count())
        except Exception:
            sessions_cnt = 0
            students_reached = 0
        mtd_rows.append(
            {
                "week": f"Week {widx}",
                "period": f"{ws:%b} {ws.day}–{we.day}",
                "week_start": ws.isoformat(),
                "sessions": sessions_cnt,
                "students_reached": f"{students_reached}/{total_students}" if total_students else f"{students_reached}/0",
                "test_completion": test_completion,
                "clarity_gap": clarity_gap,
                "paths": 0,
                "milestone": "—",
                "rating": 0,
                "is_current": bool(ws <= week_start <= we),
            }
        )
    ctx["ttv2_sessions_month_label"] = f"{month_first:%B} {month_first.year}"
    ctx["ttv2_sessions_mtd_rows"] = mtd_rows
    ctx["ttv2_sessions_weekly_note"] = "—"
    ctx["ttv2_sessions_next_actions"] = []

    try:
        totals = {
            int(r["student_id"]): {"total": int(r["n"] or 0), "done": int(r["done"] or 0)}
            for r in fu_base.values("student_id").annotate(
                n=Count("id"),
                done=Count("id", filter=Q(follow_up_status="completed")),
            )
        }
        week_map = {
            int(r["student_id"]): {"week_total": int(r["n"] or 0), "week_done": int(r["done"] or 0)}
            for r in fu_week.values("student_id").annotate(
                n=Count("id"),
                done=Count("id", filter=Q(follow_up_status="completed")),
            )
        }
    except Exception:
        totals, week_map = {}, {}

    previews = {}
    try:
        recent_fu = list(fu_base.select_related("counselor").order_by("-_sess_day", "-created")[:400])

        def _fmt(d):
            try:
                return d.strftime("%a %d %b %Y") if d else ""
            except Exception:
                return ""

        for fu in recent_fu:
            sid = int(getattr(fu, "student_id", 0) or 0)
            if not sid:
                continue
            arr = previews.setdefault(sid, [])
            if len(arr) >= 2:
                continue
            arr.append(
                {
                    "when": _fmt(getattr(fu, "_sess_day", None)) or "—",
                    "counselor": (getattr(getattr(fu, "counselor", None), "counselor_name", None) or ""),
                    "mode": (getattr(fu, "mode_of_follow_up", None) or "—"),
                    "status": (getattr(fu, "follow_up_status", None) or "—"),
                    "next": _fmt(getattr(fu, "next_follow_up_date", None)) or "",
                    "message": (getattr(fu, "message", None) or "").strip(),
                }
            )
    except Exception:
        previews = {}

    top_ids = sorted(
        list(week_map.keys()),
        key=lambda x: int(week_map.get(x, {}).get("week_total", 0)),
        reverse=True,
    )[:12]
    if not top_ids:
        top_ids = sorted(
            list(totals.keys()),
            key=lambda x: int(totals.get(x, {}).get("total", 0)),
            reverse=True,
        )[:12]

    sm_by_id = {int(sm.id): sm for sm in sm_qs.filter(id__in=top_ids)}
    out_students = []
    for sm_id in top_ids:
        sm = sm_by_id.get(int(sm_id))
        if not sm:
            continue
        u = getattr(sm, "student", None)
        name = (getattr(u, "name", "") or "").strip() or f"Student {sm_id}"
        cas = getattr(sm, "class_and_section", None)
        meta = ""
        try:
            cls = (getattr(cas, "class_and_section", "") or "").strip()
            st = (getattr(cas, "stream", "") or "").strip()
            inst_name = (getattr(getattr(sm, "institute", None), "name", "") or "").strip()
            meta = " · ".join([x for x in [cls, st, inst_name] if x])
        except Exception:
            meta = ""
        t = totals.get(int(sm_id), {})
        w = week_map.get(int(sm_id), {})
        out_students.append(
            {
                "student_id": int(sm_id),
                "student": name,
                "meta": meta,
                "total": int(t.get("total", 0) or 0),
                "done": int(t.get("done", 0) or 0),
                "week_total": int(w.get("week_total", 0) or 0),
                "week_done": int(w.get("week_done", 0) or 0),
                "preview": previews.get(int(sm_id), []),
            }
        )
    ctx["ttv2_sessions_students"] = out_students


def _ttv2_fill_marketing_group_session_report_ctx(request, ctx):
    """Session report for marketing-group admins: table filters + rich KPIs (same as institute group)."""
    from django.db import models as _models
    from django.db.models.functions import Coalesce, TruncDate

    from counselor.models import Counselor as _Counselor

    group_admin = request.user
    ctx["ttv2_session_report_subtitle"] = (
        "Showing counselor follow-ups for students across your marketing network."
    )
    sm_mkt = StudentManagement.objects.filter(
        institute__marketing_group__marketing_group_admin=group_admin
    )
    sm_ids = list(sm_mkt.values_list("id", flat=True))

    raw_from = (request.GET.get("from") or "").strip()
    raw_to = (request.GET.get("to") or "").strip()
    raw_coun = (request.GET.get("counselor") or "").strip()
    raw_mode = (request.GET.get("mode") or "").strip()
    raw_status = (request.GET.get("status") or "").strip()
    raw_class = (request.GET.get("class") or "").strip()
    date_from = None
    date_to = None
    try:
        if raw_from:
            date_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
    except Exception:
        date_from = None
    try:
        if raw_to:
            date_to = datetime.strptime(raw_to, "%Y-%m-%d").date()
    except Exception:
        date_to = None

    mkt_iids = list(
        Institute.objects.filter(marketing_group__marketing_group_admin=group_admin).values_list(
            "id", flat=True
        )
    )
    try:
        ctx["ttv2_session_report_counselors"] = list(
            _Counselor.objects.filter(
                Q(counselor_admin_id__in=mkt_iids) | Q(institute_placements__id__in=mkt_iids)
            )
            .distinct()
            .order_by("counselor_name")
            .values("id", name=F("counselor_name"))
        )
    except Exception:
        ctx["ttv2_session_report_counselors"] = []

    rows = []
    if sm_ids:
        try:
            qs = (
                FollowUpStatus.objects.filter(student_id__in=sm_ids)
                .select_related("counselor", "student", "student__student")
                .annotate(
                    _sess_day=Coalesce(
                        "last_follow_up_date",
                        TruncDate("created"),
                        output_field=_models.DateField(),
                    )
                )
            )
            if date_from:
                qs = qs.filter(_sess_day__gte=date_from)
            if date_to:
                qs = qs.filter(_sess_day__lte=date_to)
            if raw_coun:
                try:
                    qs = qs.filter(counselor_id=int(raw_coun))
                except Exception:
                    pass
            if raw_mode:
                qs = qs.filter(mode_of_follow_up__iexact=raw_mode)
            if raw_status:
                qs = qs.filter(follow_up_status__iexact=raw_status)
            if raw_class:
                try:
                    qs = qs.filter(student__class_and_section_id=int(raw_class))
                except Exception:
                    pass
            qs = qs.order_by("-_sess_day", "-created")[:200]
            for fu in qs:
                sm = getattr(fu, "student", None)
                u = getattr(sm, "student", None) if sm else None
                rows.append(
                    {
                        "when": getattr(fu, "last_follow_up_date", None).strftime("%Y-%m-%d")
                        if getattr(fu, "last_follow_up_date", None)
                        else (
                            getattr(fu, "created", None).strftime("%Y-%m-%d")
                            if getattr(fu, "created", None)
                            else "-"
                        ),
                        "counselor": getattr(getattr(fu, "counselor", None), "counselor_name", None)
                        or "-",
                        "student": getattr(u, "name", None)
                        or getattr(u, "email", None)
                        or (getattr(sm, "student_name", None) if sm else None)
                        or "-",
                        "mode": getattr(fu, "mode_of_follow_up", None) or "-",
                        "status": getattr(fu, "follow_up_status", None) or "-",
                        "next": getattr(fu, "next_follow_up_date", None).strftime("%Y-%m-%d")
                        if getattr(fu, "next_follow_up_date", None)
                        else "-",
                    }
                )
        except Exception:
            rows = []

    ctx["ttv2_sessions_is_dummy"] = False
    ctx["ttv2_sessions"] = rows
    ctx["ttv2_session_report_rows"] = rows
    ctx["ttv2_sessions_filters"] = {
        "from": raw_from,
        "to": raw_to,
        "counselor": raw_coun,
        "mode": raw_mode,
        "status": raw_status,
        "class": raw_class,
    }

    try:
        _ttv2_fill_session_report_rich_from_student_scope(
            request,
            ctx,
            sm_mkt.select_related("student", "class_and_section", "institute"),
        )
    except Exception:
        ctx.setdefault("ttv2_sessions_kpis", {})
        ctx.setdefault("ttv2_sessions_mtd_rows", [])
        ctx.setdefault("ttv2_sessions_students", [])
        ctx.setdefault("ttv2_sessions_month_label", "")
        ctx.setdefault("ttv2_sessions_weekly_note", "—")
        ctx.setdefault("ttv2_sessions_next_actions", [])


def _ttv2_json_weekly_sessions_for_student_scope(request, sm_qs):
    """Weekly session chart JSON (same shape as institute dashboard ?data_type=sessions)."""
    from django.db import models as _models
    from django.db.models import Count
    from django.db.models.functions import Coalesce, TruncDate

    try:
        sm_qs = sm_qs.select_related("student")
        sm_ids = list(sm_qs.values_list("id", flat=True))
        if not sm_ids:
            return JsonResponse({"sessions_data": []})

        group = (request.GET.get("group") or "").strip().lower()
        wk = _ttv2_week_start_from_request(request) or timezone.localdate()
        week_start = wk - timedelta(days=wk.weekday())
        week_end = week_start + timedelta(days=6)
        days = [week_start + timedelta(days=i) for i in range(7)]
        day_keys = [d.isoformat() for d in days]

        base_qs = (
            FollowUpStatus.objects.filter(student_id__in=sm_ids)
            .annotate(
                _sess_day=Coalesce(
                    "last_follow_up_date",
                    TruncDate("created"),
                    output_field=_models.DateField(),
                )
            )
            .filter(_sess_day__gte=week_start, _sess_day__lte=week_end)
        )

        if group == "student":
            top_n = 8
            try:
                top_ids = list(
                    base_qs.values("student_id")
                    .annotate(n=Count("id"))
                    .order_by("-n")[:top_n]
                )
                top_ids = [int(r["student_id"]) for r in top_ids if r.get("student_id")]
            except Exception:
                top_ids = []

            name_map = {}
            try:
                for sm in sm_qs.filter(id__in=top_ids):
                    u = getattr(sm, "student", None)
                    name_map[int(sm.id)] = (getattr(u, "name", "") or "").strip() or f"Student {sm.id}"
            except Exception:
                for sid in top_ids:
                    name_map[int(sid)] = f"Student {sid}"

            counts = {}
            try:
                for r in (
                    base_qs.filter(student_id__in=top_ids)
                    .values("student_id", "_sess_day")
                    .annotate(n=Count("id"))
                ):
                    sid = int(r.get("student_id") or 0)
                    d = r.get("_sess_day")
                    if not sid or not d:
                        continue
                    counts[(sid, d.isoformat())] = int(r.get("n") or 0)
            except Exception:
                counts = {}

            out = []
            for sid in top_ids:
                series = [{"day": dk, "session_count": int(counts.get((int(sid), dk), 0))} for dk in day_keys]
                out.append(
                    {
                        "series_id": int(sid),
                        "series_name": name_map.get(int(sid)) or f"Student {sid}",
                        "sessions": series,
                    }
                )
            return JsonResponse({"sessions_data": out})

        top_n = 8
        try:
            top_c = list(
                base_qs.values("counselor_id").annotate(n=Count("id")).order_by("-n")[:top_n]
            )
            top_cids = [int(r["counselor_id"]) for r in top_c if r.get("counselor_id")]
        except Exception:
            top_cids = []

        name_map = {}
        try:
            for c in Counselor.objects.filter(id__in=top_cids).only("id", "counselor_name"):
                name_map[int(c.id)] = (getattr(c, "counselor_name", "") or "").strip() or f"Counselor {c.id}"
        except Exception:
            for cid in top_cids:
                name_map[int(cid)] = f"Counselor {cid}"

        counts = {}
        try:
            for r in (
                base_qs.filter(counselor_id__in=top_cids)
                .values("counselor_id", "_sess_day")
                .annotate(n=Count("id"))
            ):
                cid = int(r.get("counselor_id") or 0)
                d = r.get("_sess_day")
                if not cid or not d:
                    continue
                counts[(cid, d.isoformat())] = int(r.get("n") or 0)
        except Exception:
            counts = {}

        out = []
        for cid in top_cids:
            series = [{"day": dk, "session_count": int(counts.get((int(cid), dk), 0))} for dk in day_keys]
            out.append(
                {
                    "counselor_id": int(cid),
                    "counselor_name": name_map.get(int(cid)) or f"Counselor {cid}",
                    "sessions": series,
                }
            )
        return JsonResponse({"sessions_data": out})
    except Exception:
        return JsonResponse({"sessions_data": []})


def student_management_for_institute_group_admin(user):
    """
    All StudentManagement rows for institutes tied to institute groups owned by ``user``.
    Matches institute listing / Count('student_management') semantics for group admins.
    """
    return StudentManagement.objects.filter(
        institute_id__in=Institute.objects.filter(
            institute_group__institute_group_admin=user
        ).values_list("id", flat=True)
    ).select_related("student", "class_and_section", "institute")


def _ttv2_session_history_student_response(request, student_scope):
    """
    JSON: full follow-up history for a single student timeline.
    Works for institute, marketing-group, and institute-group dashboards.
    """
    raw_sid = (request.GET.get("student_id") or "").strip()
    try:
        sm_id = int(raw_sid)
    except Exception:
        sm_id = 0
    if not sm_id:
        return JsonResponse({"ok": False, "items": []})

    try:
        if hasattr(student_scope, "filter"):
            sm = student_scope.select_related("institute").filter(id=sm_id).first()
        else:
            sm = next((row for row in student_scope if int(getattr(row, "id", 0) or 0) == sm_id), None)
    except Exception:
        sm = None
    if not sm:
        return JsonResponse({"ok": False, "items": []})

    from django.db.models.functions import TruncDate
    from django.db import models as _models

    def _fmt(d):
        try:
            return d.strftime("%a %d %b %Y") if d else ""
        except Exception:
            return ""

    inst = getattr(sm, "institute", None)
    if inst is None:
        fu_qs = FollowUpStatus.objects.none()
    else:
        fu_qs = (
            FollowUpStatus.objects.filter(student_id=sm_id)
            .filter(_followup_for_institute_counselors_q(inst))
            .select_related("counselor")
            .annotate(
                _sess_day=Coalesce(
                    "last_follow_up_date",
                    TruncDate("created"),
                    output_field=_models.DateField(),
                )
            )
            .order_by("-_sess_day", "-created")[:500]
        )
    items = []
    for fu in fu_qs:
        try:
            items.append(
                {
                    "when": _fmt(getattr(fu, "_sess_day", None)) or "—",
                    "counselor": (
                        getattr(getattr(fu, "counselor", None), "counselor_name", None) or "—"
                    ),
                    "mode": (getattr(fu, "mode_of_follow_up", None) or "—"),
                    "status": (getattr(fu, "follow_up_status", None) or "—"),
                    "next": _fmt(getattr(fu, "next_follow_up_date", None)) or "",
                    "message": (getattr(fu, "message", None) or "").strip(),
                }
            )
        except Exception:
            continue
    return JsonResponse({"ok": True, "student_id": sm_id, "items": items})


def _dashboard_template(v1_path: str, v2_path: str) -> str:
    """
    Global dashboard template switch controlled by core.Configuration key DASHBOARD_TEMPLATE_VERSION.
    Defaults to v1 for safety.
    """
    try:
        v = (Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1").strip()
    except Exception:
        v = "v1"
    return v2_path if v == "v2" else v1_path


def _dashboard_primary_template_name(view) -> str:
    """
    Several dashboard views override get_template_names() but still render() with self.template_name.
    Use this helper so the admin v1/v2 switch actually affects those manual render() paths.
    """
    try:
        names = view.get_template_names()
        if names:
            return names[0]
    except Exception:
        pass
    return view.template_name

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class AdminDashboardView(TemplateView):
    # template_name="topteenfrontend/user/admin_dashboard.html"
    # template_name="topteenfrontend/user/app/Admin_Dashboard.html"
    template_name="template20/institute/admin_dashboard.html"

    def html_head(self):
        name='Admin Dashboard'
        return build_html_head(title=name, description=name)
    
    def get_student_test_sreams(self, user):
        try:
            # Fetch the test result for the specific user
            test3_result = Results.objects.filter(user=user, test_paper='test3').first()
            if not test3_result:
                return None
            personality_res = test3_result.results

            scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
            # Get the count of successful tests
            results = Results.objects.filter(user=user)
            success_count = sum(1 for result in results if result.is_test_successful)

            # If there are results, get the latest result
            if results.exists():
                latest_result = results.last()
                return {
                    "streams": scores,  # Include the scores
                    "test_success": success_count > 0,
                    "test_link": latest_result.get_test_report_or_test_link(user) if latest_result else None,
                    "success_count": success_count
                }

        except Results.DoesNotExist:
            pass
        except Exception as e:
            print(f"An error occurred: {e}")

        return None
    
    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        # Extract unique streams and counts
        unique_streams = list(stream_counts.keys())
        counts = list(stream_counts.values())
        return stream_counts

    def get_context(self,request,*args,**kwargs):
        search=request.GET.get("institute")
        # if search:
            # institutes=Institute.objects.filter(name__icontains=search)| Institute.objects.filter(created_by__email__icontains=search)
            
            # institutes = (
            #     Institute.objects.filter(name__icontains=search)
            #     | Institute.objects.filter(created_by__email__icontains=search)
            # ).annotate(student_count=Count('student_management'))
        # else:
            # institutes=Institute.objects.all().order_by('-created')
        
        institutes = Institute.objects.all().order_by('-created').annotate(student_count=Count('student_management'))
        counselors_linked_to_institute = Counselor.objects.filter(counselor_admin__isnull=False)
        independent_counselors = Counselor.objects.filter(counselor_admin__isnull=True)


        institute_data = [
            {
                'address': institute.name,  # Assuming the address field exists
                'student_count': institute.student_count
            }
            for institute in institutes
        ]

        all_inst_student = StudentManagement.objects.all().order_by('-id')
        ptr_count1=[r1 for r1 in all_inst_student if r1.get_test_result()]

        results_data = {}
        for stu in all_inst_student:
            student_result = self.get_student_test_sreams(stu.student)
            if student_result:  # Only include results that were found
                results_data[stu.student] = student_result
        
        # If you want to create a list of results instead of a dictionary
        test_results = list(results_data.values())
        streams = self.get_stream(test_results) if test_results else {}

        
        pages=Paginator(institutes,4)
        pages1=Paginator(all_inst_student,10)

        page_number=request.GET.get('page')
        page_number1=request.GET.get('page')

        ctx={}
        ctx["html_head"] = self.html_head()
        ctx["Total_institutes"]=institutes
        
        ctx['results_data']=results_data
        ctx["institutes"]=pages.get_page(page_number)
        ctx["students"]=pages1.get_page(page_number1)

        ctx['total_stus']= institute_data
        ctx["institute_users"] = User.objects.filter(user_type=choices.UserType.INSTITUTE)
        # old code not in use - start
        # Marketing users list for admin dashboard
        # old code not in use - end
        ctx["marketing_users"] = User.objects.filter(user_type=choices.UserType.MARKETINGGROUPADMIN).order_by('-created')
        ctx["active_marketing_users"] = User.objects.filter(user_type=choices.UserType.MARKETINGGROUPADMIN, user_status=choices.UserStatus.UNBLOCK)
        ctx["inactive_marketing_users"] = User.objects.filter(user_type=choices.UserType.MARKETINGGROUPADMIN, user_status=choices.UserStatus.BLOCK)
        ctx["Total_students"] = StudentManagement.objects.all()
        ctx['counselors'] = Counselor.objects.all()
        ctx['counselors_linked_to_institute'] = counselors_linked_to_institute
        ctx['independent_counselors'] = independent_counselors
        ctx["global_credits"]=settings.CREDIT_LIMIT
        ctx["remaining_credits"]=get_global_remain_credits()
        ctx["institute_groups"]=InstituteGroup.objects.all()
        ctx['streams'] = streams
        ctx['test_result_count'] = ptr_count1
        return ctx
    
    def get(self,request,*args,**kwargs):
        return render(request,self.template_name,self.get_context(request,*args,**kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(superuser_or_marketing_institute_create,name='dispatch')
class InstituteCreateView(TemplateView):
    template_name = 'template20/institute/marketing_group_dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # Redirect to marketing dashboard if accessed via GET
        return HttpResponseRedirect(reverse('institute:marketinggroupdashboard'))
    
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        phone10 = r'^\d{10}$'
        def _norm_phone(val: str) -> str:
            try:
                return re.sub(r"\D+", "", (val or "").strip())
            except Exception:
                return ""

        ins_email = (request.POST.get("institute_email") or "").strip()
        name = (request.POST.get("institute_name") or "").strip()
        address = (request.POST.get("institute_address") or "").strip()
        contact = _norm_phone(request.POST.get("institute_contact"))
        admin_contact = _norm_phone(request.POST.get("institute_admin"))
        institute_group_id = request.POST.get("institute_group")
        logo = request.FILES.get("institute_logo")
        referer = request.META.get('HTTP_REFERER') or reverse('institute:marketinggroupdashboard')

        ins_em = re.match(evalid, ins_email) if ins_email else None

        if ins_email and User.objects.filter(email__iexact=ins_email).exists():
            messages.error(
                request,
                "This email is already registered. An institute with this login may already exist.",
            )
            return HttpResponseRedirect(referer)

        if name and address and Institute.objects.filter(name__iexact=name, address__iexact=address).exists():
            messages.error(
                request,
                "An institute with this name and address already exists.",
            )
            return HttpResponseRedirect(referer)

        from institute.tieup_billing import parse_exam_credits_qty_from_post

        credit_counts, credits_err = parse_exam_credits_qty_from_post(request.POST)
        if credits_err:
            messages.error(request, credits_err)
            return HttpResponseRedirect(referer)

        if contact and not re.match(phone10, contact):
            messages.error(request, "Contact number must be exactly 10 digits.")
            return HttpResponseRedirect(referer)
        if admin_contact and not re.match(phone10, admin_contact):
            messages.error(request, "Admin contact number must be exactly 10 digits.")
            return HttpResponseRedirect(referer)

        max_credits = get_global_remain_credits()
        if ins_em and name and address and contact and admin_contact and logo and 0 <= credit_counts <= max_credits:
            raw_ig = (institute_group_id or "").strip()
            ins_group = None
            if request.user.user_type == choices.UserType.INSTITUTEGROUPADMIN:
                owned_ig = InstituteGroup.objects.filter(
                    institute_group_admin=request.user
                ).order_by("id")
                if raw_ig.isdigit():
                    ins_group = get_object_or_404(InstituteGroup, id=int(raw_ig))
                    if not owned_ig.filter(pk=ins_group.pk).exists():
                        messages.error(request, "Invalid institute group selection.")
                        return HttpResponseRedirect(referer)
                elif owned_ig.count() == 1:
                    ins_group = owned_ig.first()
                elif owned_ig.count() > 1:
                    messages.error(request, "Please select an institute group.")
                    return HttpResponseRedirect(referer)
                else:
                    messages.error(
                        request,
                        "Your account has no institute group assigned. Contact support.",
                    )
                    return HttpResponseRedirect(referer)
            else:
                if raw_ig.isdigit():
                    ins_group = get_object_or_404(InstituteGroup, id=int(raw_ig))

            # Attach institute to this user's marketing group (create one if missing — common for new admins)
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=request.user
            ).order_by('id').first()
            if request.user.user_type == choices.UserType.MARKETINGGROUPADMIN and not marketing_group:
                label = (request.user.name or request.user.email or '').strip()
                if not label:
                    label = f"Marketing group {request.user.pk}"
                marketing_group = InstituteMarketingGroup.objects.create(
                    m_group_name=label[:250],
                    marketing_group_admin=request.user,
                )

            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':ins_email,'password':password,'user_type':choices.UserType.INSTITUTE}
            ins_user=User.create_user(**user_dict)
            from institute.models import institute_status_for_creator

            initial_status = institute_status_for_creator(request.user)
            ins = Institute(
                name=name,
                created_by=ins_user,
                logo=logo,
                address=address,
                contact_info=contact,
                administrator_contact=admin_contact,
                credit_counts=credit_counts,
                institute_group=ins_group,
                marketing_group=marketing_group,
                institute_status=initial_status,
            )
            ins.save()
            from institute.psychometric_packages import (
                apply_institute_psychometric_settings_from_post,
                sync_institute_packages_from_post,
            )

            apply_institute_psychometric_settings_from_post(ins, request.POST, save=True)
            sync_institute_packages_from_post(ins, request.POST)
            from institute.tieup_billing import (
                create_tieup_order,
                tieup_lines_for_institute_create,
            )

            tieup_lines = tieup_lines_for_institute_create(request.POST, credit_counts)
            if tieup_lines:
                coupon_code = (request.POST.get("tieup_coupon_code") or "").strip()
                try:
                    create_tieup_order(
                        ins,
                        request.user,
                        tieup_lines,
                        coupon_code=coupon_code or None,
                    )
                except ValueError as e:
                    messages.warning(
                        request,
                        f"Institute created but tie-up billing failed: {e}",
                    )
            elif credit_counts > 0:
                from institute.tieup_billing import ensure_pending_tieup_order_for_institute

                ensure_pending_tieup_order_for_institute(ins, request.user)
            send_institute_mail.delay(ins.created_by.email, password)
            if initial_status == choices.InstituteStatus.APPROVED:
                messages.success(request, "Institute created and approved.")
            else:
                messages.success(request, "Institute created.")
        else:
            if credit_counts > max_credits:
                messages.error(request, "No remaining credits for this allocation.")
            elif not logo:
                messages.error(request, "Institute logo is required.")
            elif not ins_em:
                messages.error(request, "Enter a valid institute email address.")
            elif not (name and address and contact and admin_contact):
                messages.error(request, "Please fill all required institute fields.")
            else:
                messages.error(request, "Something went wrong. Please check the form and try again.")
        return HttpResponseRedirect(referer)

# manish
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_authenticated_user_only,name='dispatch')
class CounselorCreateView(TemplateView):
    
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        phone10 = r'^\d{10}$'
        def _norm_phone(val: str) -> str:
            try:
                return re.sub(r"\D+", "", (val or "").strip())
            except Exception:
                return ""

        coun_email=request.POST.get("counselor_email")
        name= request.POST.get("counselor_name")
        address=request.POST.get("counselor_address")
        contact=_norm_phone(request.POST.get("counselor_contact_info"))
        education = request.POST.get("counselor_education") if request.POST.get("c_education") == "Any other" else request.POST.get("c_education")
        gender_str=request.POST.get("counselor_gender", "")  # Get gender as string
        counselor_admin=request.POST.get("counselor_admin")
        ins_em=re.match(evalid,coun_email)

        slug=kwargs.get("slug")
        # Convert gender string to integer value
        # GenderChoices: UNKNOWN=10, MALE=20, FEMALE=30
        if gender_str:
            gender_str = gender_str.strip().lower()
            if gender_str in ['m', 'male', '20']:
                gender = choices.GenderChoices.MALE  # 20
            elif gender_str in ['f', 'female', '30']:
                gender = choices.GenderChoices.FEMALE  # 30
            else:
                gender = choices.GenderChoices.UNKNOWN  # 10
        else:
            gender = choices.GenderChoices.UNKNOWN  # Default to UNKNOWN if not provided
        
        # Validate required fields: email, name, address, contact, education
        # Gender is optional, so we don't require it
        if contact and not re.match(phone10, contact):
            messages.error(request, "Contact number must be exactly 10 digits.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        if ins_em and name and address and contact and education:
            if ins_em:
                current_institute=get_object_or_404(Institute,slug=slug)
            else:
                current_institute = None
            
            # Check if user already exists
            if User.objects.filter(email=coun_email).exists():
                messages.error(request,"{} Already Exist !!".format(coun_email))
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':coun_email,'password':password,'user_type':choices.UserType.COUNSELOR}
            coun_user=User.create_user(**user_dict)
            coun=Counselor(counselor_name=name,coun_user = coun_user,counselor_email=coun_email,counselor_address=address,counselor_contact_info=contact,counselor_education=education,counselor_gender=gender,counselor_admin=current_institute)
            coun.save()
            send_institute_mail.delay(coun.coun_user.email,password)
            messages.success(request, "Counselor Created Successfully")
        else:
            if User.objects.filter(email=coun_email).exists():
                messages.error(request,"{} Already Exist !!".format(coun_email))
            else:
                missing_fields = []
                if not ins_em:
                    missing_fields.append("valid email")
                if not name:
                    missing_fields.append("name")
                if not address:
                    missing_fields.append("address")
                if not contact:
                    missing_fields.append("contact info")
                if not education:
                    missing_fields.append("education")
                messages.error(request,"Please fill all required fields: {}".format(", ".join(missing_fields)))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class InstituteGroupCreateView(TemplateView):
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        group_email=request.POST.get("group_email")
        name= request.POST.get("group_name")
        group_em=re.match(evalid,group_email)
        if group_em and name :
            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':group_email,'password':password,'user_type':choices.UserType.INSTITUTEGROUPADMIN}
            group_user=User.create_user(**user_dict)
            ins_grp=InstituteGroup(group_name=name,institute_group_admin=group_user)
            ins_grp.save()
            send_institute_group_mail.delay(ins_grp.group_name,ins_grp.institute_group_admin.email,password)
            messages.success(request, "Institute Group Created")
        else:
            if User.objects.filter(email=group_email).exists():
                messages.error(request,"{} Already Exist !!".format(group_email))
            else:
                messages.error(request,"Something Went Wrong !!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class MarketingGroupDashboardView(TemplateView):
    # template_name="topteenfrontend/user/institute_group_dashboard.html"
    template_name="template20/institute/marketing_group_dashboard.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/marketing_group_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]

    def html_head(self):
        name='Institute Group Dashboard'
        return build_html_head(title=name, description=name)
    
    def get_student_test_sreams(self, user):
        try:
            # Get all results for the user
            results = Results.objects.filter(user=user)
            
            if not results.exists():
                return None
            
            # Try to get test3 result first (personality test)
            test3_result = None
            try:
                test3_result = Results.objects.get(user=user, test_paper='test3')
            except Results.DoesNotExist:
                pass
            
            # If test3 exists, use it for personality data
            if test3_result:
                personality_res = test3_result.results
                sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
            else:
                # If no test3, try to get any available test result
                latest_result = results.last()
                if latest_result.results:
                    sreams_scores = {label.split("_")[0].upper(): value for label, value in latest_result.results.items()}
                else:
                    sreams_scores = {}

            return {
                "streams": sreams_scores,  # Include the scores
            }

        except Exception as e:
            print(f"An error occurred in get_student_test_sreams: {e}")
            return None
    
    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}        

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        return stream_counts
    
    def get_institute_group_info(self, group_admin, search_params=None, load_full_data=False):
        # Scope by marketing_group.admin user (not .first() on InstituteMarketingGroup) so each
        # marketing admin only sees institutes tied to groups they own — even with multiple groups.
        institutes = Institute.objects.filter(
            marketing_group__marketing_group_admin=group_admin
        )

        # Hierarchy: marketing → (institute group →) institute. Filter list by scope.
        list_mode = ''
        if search_params:
            list_mode = (search_params.get('list_mode') or '').strip().lower()
        if list_mode == 'direct':
            institutes = institutes.filter(institute_group__isnull=True)
        elif list_mode == 'group':
            institutes = institutes.filter(institute_group__isnull=False)
        
        # Apply filters if provided
        if search_params:
            # Institute name search
            if search_params.get('institute'):
                institutes = institutes.filter(
                    name__icontains=search_params['institute']
                )
            
            # Location exact match
            if search_params.get('location'):
                institutes = institutes.filter(
                    address__iexact=search_params['location']
                )
            
            # Location search
            if search_params.get('location_search'):
                institutes = institutes.filter(
                    address__icontains=search_params['location_search']
                )
            group_id_raw = (search_params.get('institute_group_id') or '').strip()
            if group_id_raw.isdigit():
                institutes = institutes.filter(institute_group_id=int(group_id_raw))

            status_key = (search_params.get('status') or '').strip().lower()
            status_map = {
                'pending': choices.InstituteStatus.PENDING,
                'approved': choices.InstituteStatus.APPROVED,
                'rejected': choices.InstituteStatus.REJECTED,
            }
            if status_key in status_map:
                institutes = institutes.filter(institute_status=status_map[status_key])

        group_count_sq = (
            Institute.objects.filter(institute_group_id=OuterRef("institute_group_id"))
            .values("institute_group_id")
            .annotate(c=Count("id"))
            .values("c")[:1]
        )
        # Annotate with student count + institute-group institute count.
        institutes = institutes.annotate(
            student_count=Count('student_management'),
            group_institute_count=Coalesce(
                Subquery(group_count_sq, output_field=IntegerField()),
                Value(0),
            ),
        ).select_related("institute_group", "created_by")

        # Get unique locations for dropdown
        locations = institutes.values_list('address', flat=True).distinct()
        
        # Prepare institute data (only if loading full data)
        institute_data = []
        if load_full_data:
            institute_data = [
                {
                    'address': institute.address,
                    'student_count': institute.student_count
                }
                for institute in institutes[:100]  # Limit to 100 for performance
            ]
        
        # Only load full student data if requested (for charts/stats)
        if load_full_data:
            # Use select_related to optimize queries
            tstudents = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).select_related('student', 'institute')[:1000]  # Limit to 1000 students
            
            # Optimize test results query - use prefetch_related
            results_data = {}
            # Get all students first
            student_users = [stu.student for stu in tstudents]
            
            # Batch query for test results
            test_results_queryset = Results.objects.filter(
                user__in=student_users,
                test_paper='test3'
            ).select_related('user')[:500]  # Limit results
            
            # Create a mapping of user to result
            results_map = {result.user: result for result in test_results_queryset}
            
            # Process only students with results
            test_results = []
            for stu in tstudents[:500]:  # Limit processing
                if stu.student in results_map:
                    result = results_map[stu.student]
                    if result.results:
                        personality_res = result.results
                        sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                        test_results.append({"streams": sreams_scores})
            
            streams = self.get_stream(test_results) if test_results else {}
        else:
            # Lightweight mode - just counts
            tstudents = StudentManagement.objects.none()  # Empty queryset
            streams = {}
        
        grouped_rows = []
        if list_mode == "group":
            grouped_rows = list(
                institutes.filter(institute_group__isnull=False)
                .values(
                    "institute_group_id",
                    "institute_group__group_name",
                )
                .annotate(
                    institute_count=Count("id", distinct=True),
                    student_count=Count("student_management"),
                    total_credits=Coalesce(Sum("credit_counts"), Value(0)),
                )
                .order_by(Lower("institute_group__group_name"))
            )
            for row in grouped_rows:
                row["group_name"] = row.pop("institute_group__group_name", "") or "Unnamed group"

        return {
            "institutes": institutes,
            "group_rows": grouped_rows,
            "student_count": StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).count() if not load_full_data else tstudents.count(),
            "counselor_count": Counselor.objects.filter(
                counselor_admin__marketing_group__marketing_group_admin=group_admin
            ).count(),
            "institute_data": institute_data,
            "tstudents": tstudents,
            "streams": streams,
            "locations": locations  # Add locations for dropdown
        }

    def update_institute_streams(request, institutes):
        # Ensure that the user is allowed to update this institute
        
        pass
    
    def get_context(self, request, *args, **kwargs):
        ctx = {}
        from core.assessment_access import packages_enabled
        from institute.psychometric_packages import build_marketing_psychometric_form_ctx

        ctx["psychometric_packages_enabled"] = packages_enabled()
        ctx.update(build_marketing_psychometric_form_ctx())
        ctx["html_head"] = self.html_head()
        
        # Get search parameters
        _raw_status = (request.GET.get('status') or '').strip().lower()
        _status = _raw_status if _raw_status in ('pending', 'approved', 'rejected', '') else ''
        _raw_list_mode = (request.GET.get('list_mode') or '').strip().lower()
        _list_mode = _raw_list_mode if _raw_list_mode in ('all', 'direct', 'group') else 'all'
        search_params = {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip(),
            'institute_group_id': request.GET.get('institute_group_id', '').strip(),
            'status': _status,
            'list_mode': _list_mode,
        }
        
        # Check what data is being requested
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')  # 'institutes', 'stats', 'charts', 'seat_capacity'
        # Template v2 loads this HTML via fetch(XHR) + ?ttv2_partial=1 — must use full dashboard context
        # (otherwise we hit the "default AJAX" branch and omit ttv2_analytics / counselor_data_list).
        is_v2_shell_partial = (
            is_ajax
            and request.GET.get("ttv2_partial") == "1"
            and data_type not in ("institutes", "stats", "charts")
        )

        # For initial page load, use lightweight mode
        if (not is_ajax) or is_v2_shell_partial:
            # Lightweight initial load — scope all institute metrics to this user's marketing admin
            group_admin = request.user
            _scoped = Institute.objects.filter(
                marketing_group__marketing_group_admin=group_admin
            )
            from core.ttv2_dashboard_analytics import build_ttv2_analytics, empty_ttv2_analytics
            from institute.counselor_component_data import (
                build_counselor_data_list_for_institute_ids,
                filter_counselor_data_list_by_query,
            )

            _sm_mkt = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            )
            # v2 quick-links: used by modal dropdowns (add counselor / bulk upload)
            try:
                ctx["ttv2_quicklink_institutes"] = build_ttv2_quicklink_institutes(group_admin)
            except Exception:
                ctx["ttv2_quicklink_institutes"] = []
            _dr_start, _dr_end = _ttv2_date_range_from_request(request)
            try:
                ctx["ttv2_analytics"] = build_ttv2_analytics(
                    "marketing_group",
                    student_management_qs=_sm_mkt,
                    week_start=_ttv2_week_start_from_request(request),
                    date_start=_dr_start,
                    date_end=_dr_end,
                )
            except Exception:
                ctx["ttv2_analytics"] = empty_ttv2_analytics()
            _mkt_counselor_iids = list(_scoped.values_list("id", flat=True))
            ctx["counselor_data_list"] = build_counselor_data_list_for_institute_ids(
                _mkt_counselor_iids, include_institute_name=True
            )
            _mkt_cq = (request.GET.get("counselor_q") or "").strip()
            ctx["counselor_q"] = _mkt_cq
            if _mkt_cq:
                ctx["counselor_data_list"] = filter_counselor_data_list_by_query(
                    ctx["counselor_data_list"], _mkt_cq
                )
            _mktg_new_days = 14
            _recent_cutoff = timezone.now() - timedelta(days=_mktg_new_days)
            _status_labels = dict(choices.InstituteStatus.CHOICES)

            def _mktg_institute_preview_rows(qs, limit):
                rows = []
                for o in qs.select_related('institute_group')[:limit]:
                    rows.append({
                        'id': o.id,
                        'name': o.name,
                        'slug': o.slug,
                        'created': o.created,
                        'institute_status': o.institute_status,
                        'status_label': _status_labels.get(o.institute_status, ''),
                        'via_group': o.institute_group_id is not None,
                        'group_name': (
                            o.institute_group.group_name if o.institute_group_id else ''
                        ),
                    })
                return rows

            _recent_inst = _scoped.filter(created__gte=_recent_cutoff).order_by('-created')
            _pending_inst = _scoped.filter(
                institute_status=choices.InstituteStatus.PENDING,
            ).order_by('-created')
            _recent_counselors = (
                Counselor.objects.filter(
                    counselor_admin__marketing_group__marketing_group_admin=group_admin,
                    created__gte=_recent_cutoff,
                )
                .select_related('counselor_admin')
                .order_by('-created')
            )
            ctx.update({
                'mktg_new_activity_days': _mktg_new_days,
                'mktg_new_institutes_count': _recent_inst.count(),
                'mktg_new_institutes_preview': _mktg_institute_preview_rows(_recent_inst, 6),
                'mktg_pending_institutes_preview': _mktg_institute_preview_rows(
                    _pending_inst, 8
                ),
                'mktg_new_counselors_count': _recent_counselors.count(),
                'mktg_new_counselors_preview': [
                    {
                        'id': c.id,
                        'name': c.counselor_name,
                        'email': c.counselor_email or '',
                        'created': c.created,
                        'institute_name': (
                            c.counselor_admin.name if c.counselor_admin_id else ''
                        ),
                        'institute_slug': (
                            c.counselor_admin.slug if c.counselor_admin_id else ''
                        ),
                    }
                    for c in _recent_counselors[:6]
                ],
                'total_institute_count': _scoped.count(),
                'pending_institute_count': _scoped.filter(
                    institute_status=choices.InstituteStatus.PENDING,
                ).count(),
                'total_stu_count': None,  # Will load via AJAX
                'counselors_count': None,  # Will load via AJAX
                'institutes': [],
                'total_students_count': None,
                'test_result_count': None,
                'streams': {},
                'locations': list(
                    _scoped.values_list('address', flat=True).distinct()[:50]
                ),
                'institute_names': list(
                    _scoped.values_list('name', flat=True).distinct()[:200]
                ),
                'search_params': search_params,
                "institute_group": InstituteGroup.objects.all(),
                "institute_types": choices.InstituteType.CHOICES,
                'institutes_paginations': None,
            })
        elif data_type == 'institutes':
            # AJAX request for institute table
            group_admin = request.user
            info = self.get_institute_group_info(group_admin, search_params, load_full_data=False)
            list_mode = (search_params.get('list_mode') or '').strip().lower()
            institutes_list = info['group_rows'] if list_mode == 'group' else info['institutes']
            
            # Get per_page parameter from request, default to 10
            per_page = request.GET.get('per_page', '10')
            
            # Handle pagination
            if per_page == 'all':
                # Show all records without pagination
                ctx['institutes_paginations'] = None
                ctx['institutes_list_all'] = list(institutes_list)
            else:
                try:
                    per_page_int = int(per_page)
                    # Limit to valid options: 10, 100
                    if per_page_int not in [10, 100]:
                        per_page_int = 10
                except (ValueError, TypeError):
                    per_page_int = 10
                
                pages = Paginator(institutes_list, per_page_int)
                page_number = request.GET.get('page', 1)
                try:
                    ctx['institutes_paginations'] = pages.get_page(page_number)
                except:
                    ctx['institutes_paginations'] = pages.get_page(1)
            
            ctx['search_params'] = search_params
            ctx['institutes_is_group_mode'] = (list_mode == 'group')
            ctx['per_page'] = per_page
            from urllib.parse import urlencode
            _qs = {}
            for _k in ('institute', 'location', 'location_search', 'institute_group_id', 'status', 'list_mode'):
                _v = (search_params.get(_k) or '').strip()
                if _v and not (_k == 'list_mode' and _v == 'all'):
                    _qs[_k] = _v
            if per_page:
                _qs['per_page'] = str(per_page)
            ctx['institute_table_query_string'] = urlencode(_qs)
        elif data_type == 'stats':
            # AJAX request for statistics
            group_admin = request.user
            institutes_in_group = Institute.objects.filter(
                marketing_group__marketing_group_admin=group_admin
            ).annotate(_used=Count("student_management"))
            cred_rows = list(institutes_in_group.values("credit_counts", "_used"))
            credits_allocated_total = sum(int(r["credit_counts"] or 0) for r in cred_rows)
            credits_used_total = sum(int(r["_used"] or 0) for r in cred_rows)
            credits_remaining_total = sum(
                max(0, int(r["credit_counts"] or 0) - int(r["_used"] or 0)) for r in cred_rows
            )
            ctx.update({
                'total_stu_count': StudentManagement.objects.filter(
                    institute__marketing_group__marketing_group_admin=group_admin
                ).count(),
                'counselors_count': Counselor.objects.filter(
                    counselor_admin__marketing_group__marketing_group_admin=group_admin
                ).count(),
                'credits_allocated_total': credits_allocated_total,
                'credits_used_total': credits_used_total,
                'credits_remaining_total': credits_remaining_total,
                'total_events': 0,  # Placeholder - add actual events count if available
            })
        elif data_type == 'charts':
            # AJAX request for charts data - OPTIMIZED for performance
            group_admin = request.user
            _mscope = Institute.objects.filter(
                marketing_group__marketing_group_admin=group_admin
            )
            # OPTIMIZED: Get institute data for location chart (only address and student_count)
            institute_data = list(
                _mscope.values('address')
                .annotate(student_count=Count('student_management'))
                .order_by('-student_count')[:20]
            )
            seat_capacity_institutes = list(
                _mscope.values('id', 'slug', 'name', 'address', 'pcm', 'cbm', 'comm', 'hme', 'hmb')
                .order_by('name')[:100]
            )
            total_students_count = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).count()
            _psych_done = _sm_primary_psychometric_tests_complete_exists()
            test_result_count = (
                StudentManagement.objects.filter(
                    institute__marketing_group__marketing_group_admin=group_admin,
                    student_id__isnull=False,
                )
                .filter(_psych_done)
                .count()
            )
            sample_students = (
                StudentManagement.objects.filter(
                    institute__marketing_group__marketing_group_admin=group_admin,
                    student_id__isnull=False,
                )
                .filter(_psych_done)
                .select_related("student")[:200]
            )
            student_users = [stu.student for stu in sample_students]
            test_results_queryset = Results.objects.filter(
                user__in=student_users,
                test_paper='test3'
            ).select_related('user')[:200]
            results_map = {result.user: result for result in test_results_queryset}
            test_results = []
            for stu in sample_students:
                if stu.student in results_map:
                    result = results_map[stu.student]
                    if result.results:
                        personality_res = result.results
                        sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                        test_results.append({"streams": sreams_scores})
            streams_data = self.get_stream(test_results) if test_results else {}
            streams_chart_data = []
            if streams_data:
                sorted_streams = sorted(streams_data.items(), key=lambda x: x[1], reverse=True)[:15]
                for stream, count in sorted_streams:
                    streams_chart_data.append({
                        'stream': stream,
                        'count': count
                    })
            ctx.update({
                'institutes': institute_data,
                'total_students_count': total_students_count,
                'test_result_count': test_result_count,
                'streams': streams_data,
                'streams_chart_data': streams_chart_data,
                'seat_capacity_institutes': seat_capacity_institutes,
            })
        elif is_ajax and not data_type and request.GET.get("ttv2_partial") != "1":
            # Default AJAX — institute table only (not Template v2 partial fetch)
            group_admin = request.user
            info = self.get_institute_group_info(group_admin, search_params, load_full_data=False)
            list_mode = (search_params.get('list_mode') or '').strip().lower()
            institutes_list = info['group_rows'] if list_mode == 'group' else info['institutes']
            pages = Paginator(institutes_list, 10)
            page_number = request.GET.get('page', 1)
            ctx['institutes_paginations'] = pages.get_page(page_number)
            ctx['search_params'] = search_params
            ctx['institutes_is_group_mode'] = (list_mode == 'group')
            ctx['per_page'] = '10'
            from urllib.parse import urlencode
            _qs = {}
            for _k in ('institute', 'location', 'location_search', 'institute_group_id', 'status', 'list_mode'):
                _v = (search_params.get(_k) or '').strip()
                if _v and not (_k == 'list_mode' and _v == 'all'):
                    _qs[_k] = _v
            _qs['per_page'] = '10'
            ctx['institute_table_query_string'] = urlencode(_qs)
        # v2 shell: separate page mode (dashboard/students/assessments/...) from URL
        ctx["ttv2_page"] = (kwargs.get("page") or "dashboard").strip().lower()
        if ctx["ttv2_page"] == "session_report":
            _ttv2_fill_marketing_group_session_report_ctx(request, ctx)
        if ctx["ttv2_page"] == "students":
            sm_scope = scoped_student_management_for_dashboard(request)
            ctx["total_students_count"] = sm_scope.count()
            ctx["class_and_sections"] = get_class_and_sections_by_role(
                request.user, sm_scope
            )
            ctx["unique_streams"] = get_unique_streams_by_role(request.user, sm_scope)
        if ctx["ttv2_page"] == "credits":
            group_admin = request.user
            _scoped_cr = (
                Institute.objects.filter(marketing_group__marketing_group_admin=group_admin)
                .annotate(_used=Count("student_management"))
                .order_by(Lower("name"))
            )
            mktg_rows = []
            tot_a = tot_u = tot_r = 0
            for inst in _scoped_cr:
                alloc = int(inst.credit_counts or 0)
                used = int(inst._used or 0)
                rem = max(0, alloc - used)
                tot_a += alloc
                tot_u += used
                tot_r += rem
                mktg_rows.append(
                    {
                        "id": inst.id,
                        "name": inst.name,
                        "slug": inst.slug,
                        "allocated": alloc,
                        "used": used,
                        "remaining": rem,
                    }
                )
            ctx["mktg_credits_rows"] = mktg_rows
            ctx["mktg_credits_totals"] = {
                "allocated": tot_a,
                "used": tot_u,
                "remaining": tot_r,
            }
        if ctx["ttv2_page"] == "payments":
            from institute.tieup_billing import build_marketing_payments_rows

            status_filter = (request.GET.get("status") or "").strip().lower() or None
            institute_filter = (request.GET.get("institute") or "").strip()
            institutes_qs = Institute.objects.filter(
                marketing_group__marketing_group_admin=request.user
            ).order_by("name")
            ctx["ttv2_tieup_payments"] = build_marketing_payments_rows(
                request.user,
                status_filter,
                institute_slug=institute_filter or None,
            )
            ctx["ttv2_payments_status_filter"] = status_filter or ""
            ctx["ttv2_payments_institute_filter"] = institute_filter
            ctx["tieup_payment_institutes"] = list(
                institutes_qs.values("id", "name", "slug")
            )
            ctx["mark_received_url"] = reverse("institute:marketing_tieup_mark_received")
            ctx["coupon_create_url"] = reverse("institute:marketing_tieup_coupon_create")
            ctx["mktg_coupon_institutes"] = ctx["tieup_payment_institutes"]
            ctx["tieup_coupon_institutes"] = ctx["tieup_payment_institutes"]
            ctx["show_tieup_coupon_create"] = True
            ctx["show_tieup_mark_received"] = True
            ctx["is_marketing_view"] = True
            from institute.tieup_billing import get_tieup_pay_coupon_context
            from institute.models import InstituteTieUpOrder

            all_available = []
            all_used = []
            for inst in institutes_qs:
                order = (
                    InstituteTieUpOrder.objects.filter(
                        institute=inst, status=choices.TieUpOrderStatus.ACTIVE
                    )
                    .prefetch_related("line_items")
                    .order_by("-created")
                    .first()
                )
                pending_objs = []
                if order:
                    pending_objs = [
                        li
                        for li in order.line_items.all()
                        if li.payment_status == choices.TieUpPaymentStatus.PENDING
                    ]
                cctx = get_tieup_pay_coupon_context(inst, pending_objs)
                for row in cctx.get("coupons_available", []):
                    item = dict(row)
                    item["institute_name"] = inst.name
                    item["institute_slug"] = inst.slug
                    all_available.append(item)
                for row in cctx.get("coupons_used", []):
                    item = dict(row)
                    item["institute_name"] = inst.name
                    item["institute_slug"] = inst.slug
                    all_used.append(item)
            ctx["coupons_available"] = all_available
            ctx["coupons_used"] = all_used
        if ctx["ttv2_page"] == "accounts":
            from institute.accounts_analytics import build_marketing_accounts_ctx

            ctx["ttv2_accounts"] = build_marketing_accounts_ctx(request.user, request)

        return ctx
    
    def get(self, request, *args, **kwargs):
        from django.template.loader import render_to_string
        from django.http import JsonResponse, HttpResponse
        
        # Check if this is an AJAX request for specific data
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')
        
        if is_ajax and data_type == 'students_analytics':
            group_admin = request.user
            qs = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            )
            return JsonResponse(
                build_students_analytics_payload(qs, week_start=_ttv2_week_start_from_request(request))
            )
        if is_ajax and data_type == "counselor_followups":
            return _ttv2_marketing_counselor_followups_response(request, request.user)
        if is_ajax and data_type == 'institutes':
            # Return institute table partial
            context = self.get_context(request, *args, **kwargs)
            html = render_to_string('template20/institute/marketing_institutes_table.html', context, request=request)
            return HttpResponse(html)
        if is_ajax and data_type == "session_history_student":
            return _ttv2_session_history_student_response(
                request,
                scoped_student_management_for_dashboard(request),
            )
        if is_ajax and data_type == "sessions":
            group_admin = request.user
            return _ttv2_json_weekly_sessions_for_student_scope(
                request,
                StudentManagement.objects.filter(
                    institute__marketing_group__marketing_group_admin=group_admin
                ),
            )
        if is_ajax and data_type == "students":
            from institute.student_table_helpers import (
                get_student_action_urls,
                get_student_table_config,
            )

            stu_qs = (
                scoped_student_management_for_dashboard(request)
                .select_related("student", "class_and_section", "institute", "counselor")
                .prefetch_related("counselors")
            )
            scoped_institute = _resolve_dashboard_institute_from_request(request)
            iv = InstituteDashboardView()
            ctx = iv.get_student_table_context_ajax(
                request,
                *args,
                stu_manage=stu_qs,
                institute=scoped_institute,
                **kwargs,
            )
            ctx["table_config"] = get_student_table_config("marketing")
            ctx["action_urls"] = get_student_action_urls("marketing")
            ctx["students"] = ctx.get("total_students")
            apply_student_table_display_enrichment(request, ctx)
            ctx["ttv2_students_role"] = "marketing_group"
            display = (request.GET.get("display") or "").strip().lower()
            if display == "cards":
                return render(
                    request,
                    "template_v2/institute/pages/student_roster_cards.html",
                    ctx,
                )
            return render(request, "template20/shared/students_table.html", ctx)
        elif is_ajax and data_type in ['stats', 'charts']:
            # Return JSON data for stats or charts
            context = self.get_context(request, *args, **kwargs)
            # Convert QuerySets to counts/lists for JSON serialization
            json_data = {}
            for key, value in context.items():
                # Skip non-serializable items
                if key in ['html_head', 'request', 'search_params']:
                    continue
                if hasattr(value, 'count') and not isinstance(value, (str, dict, list)):
                    json_data[key] = value.count()
                elif isinstance(value, (list, tuple)):
                    # Handle lists of dicts (like institute_data)
                    json_data[key] = value
                elif isinstance(value, dict):
                    json_data[key] = value
                elif hasattr(value, '__iter__') and not isinstance(value, (str, dict, list)):
                    try:
                        json_data[key] = list(value)[:100]  # Limit to 100 items
                    except:
                        json_data[key] = []
                elif value is None:
                    json_data[key] = None
                else:
                    # For simple types (int, str, bool, etc.)
                    try:
                        json_data[key] = value
                    except:
                        pass
            return JsonResponse(json_data)
        else:
            # Regular page load (support v2 partial for AJAX shell boot)
            ctx = self.get_context(request, *args, **kwargs)
            payments_partial = _render_ttv2_tieup_payments_partial(request, ctx)
            if payments_partial is not None:
                return payments_partial
            try:
                template_version = (
                    Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
                ).strip()
            except Exception:
                template_version = "v1"
            if template_version == "v2" and request_wants_ttv2_dashboard_body_partial(request):
                return render(request, "template_v2/dashboard_unified_body.html", ctx)
            return render(request, _dashboard_primary_template_name(self), ctx)
    
    def get_search_parameters(self, request):
        """Extract and validate search parameters from request"""
        _raw_status = (request.GET.get('status') or '').strip().lower()
        _status = _raw_status if _raw_status in ('pending', 'approved', 'rejected', '') else ''
        return {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip(),
            'status': _status,
        }

    def apply_filters(self, queryset, search_params):
        """Apply filters to queryset based on search parameters"""
        if search_params.get('institute'):
            queryset = queryset.filter(name__icontains=search_params['institute'])
        
        if search_params.get('location'):
            queryset = queryset.filter(address__iexact=search_params['location'])
            
        if search_params.get('location_search'):
            queryset = queryset.filter(address__icontains=search_params['location_search'])

        status_key = (search_params.get('status') or '').strip().lower()
        status_map = {
            'pending': choices.InstituteStatus.PENDING,
            'approved': choices.InstituteStatus.APPROVED,
            'rejected': choices.InstituteStatus.REJECTED,
        }
        if status_key in status_map:
            queryset = queryset.filter(institute_status=status_map[status_key])
        
        return queryset
    

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class InstituteMarketingProfileEditView(TemplateView):
    template_name = 'template20/institute/marketing_group_dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # Redirect to marketing dashboard if accessed via GET
        return HttpResponseRedirect(reverse('institute:marketinggroupdashboard'))
    
    def post(self,request, *args, **kwargs):
        ins_id = request.POST.get("institute_id")
        change_password = request.POST.get("change_password")
        
        # Handle password change
        if change_password == "1":
            new_password = request.POST.get("new_password")
            confirm_password = request.POST.get("confirm_password")
            
            if not new_password or not confirm_password:
                messages.error(request, "Both password fields are required.")
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Both password fields are required.'}, status=400)
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Passwords do not match.'}, status=400)
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            ins = get_object_or_404(Institute, id=ins_id)
            group_admin = request.user
            mg = ins.marketing_group
            if not request.user.is_superuser:
                if not mg or mg.marketing_group_admin_id != group_admin.id:
                    messages.error(request, "Unauthorized access.")
                    # Handle AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)
                    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            # Get the institute user (created_by)
            if ins.created_by:
                ins_user = ins.created_by
                ins_user.set_password(new_password)
                ins_user.save()
                send_new_student_credential.delay(ins_user.email, new_password)
                messages.success(request, f"Password changed successfully for {ins.name}.")
                
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': f'Password changed successfully for {ins.name}.'})
            else:
                messages.error(request, "Institute user not found.")
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Institute user not found.'}, status=400)
            
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        # Handle institute profile update
        ins_name=request.POST.get("institute_name")
        ins_address=request.POST.get("institute_address")
        ins_contact=request.POST.get("institute_contact")
        ins_admin=request.POST.get("institute_admin")
        ins_group=request.POST.get("institute_group")
        ins_logo=request.FILES.get("institute_logo")
        ins_status_raw = request.POST.get("institute_status")

        ins=get_object_or_404(Institute,id=ins_id)
        group_admin = request.user
        mg = ins.marketing_group
        if not request.user.is_superuser:
            if not mg or mg.marketing_group_admin_id != group_admin.id:
                messages.error(request, "Unauthorized access.")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        status_updated = False
        if ins_status_raw not in (None, ""):
            try:
                s = int(str(ins_status_raw).strip())
            except (ValueError, TypeError):
                s = None
            allowed = (
                choices.InstituteStatus.APPROVED,
                choices.InstituteStatus.REJECTED,
                choices.InstituteStatus.PENDING,
            )
            if s in allowed and ins.institute_status != s:
                ins.institute_status = s
                status_updated = True

        from institute.tieup_billing import (
            parse_line_items_from_post,
            sync_institute_tieup_from_post,
        )

        tieup_qty_raw = (
            request.POST.get("tieup_student_test_credits_qty")
            or request.POST.get("upd_credits")
            or ""
        ).strip()
        profile_changed = bool(
            ins_name
            or ins_address
            or ins_contact
            or ins_admin
            or ins_logo
            or ins_group
            or status_updated
            or tieup_qty_raw
            or parse_line_items_from_post(request.POST)
            or request.POST.get("psychometric_access_mode")
            or (request.POST.get("assignment_credits") or "").strip() != ""
            or request.POST.getlist("institute_package_codes")
        )
        if profile_changed:
            if ins_name:
                update_student_data.delay(ins.id, ins_name)
                ins.name = ins_name
            if ins_address:
                ins.address = ins_address
            if ins_contact:
                ins.contact_info = ins_contact
            if ins_admin:
                ins.administrator_contact = ins_admin
            if ins_group:
                institute_group = get_object_or_404(InstituteGroup, id=ins_group)
                ins.institute_group = institute_group
            if ins_logo:
                ins.logo = ins_logo
            from institute.psychometric_packages import (
                apply_institute_psychometric_settings_from_post,
                sync_institute_packages_from_post,
            )

            apply_institute_psychometric_settings_from_post(ins, request.POST, save=False)
            ins.save()
            sync_institute_packages_from_post(ins, request.POST)
            try:
                sync_institute_tieup_from_post(ins, request.user, request.POST)
            except ValueError as e:
                messages.warning(
                    request,
                    f"Institute profile saved; tie-up billing was not updated: {e}",
                )
            messages.success(request, f"Institute {ins.name} updated successfully.")
        else:
            messages.info(request, "No changes were made.")
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'Institute {ins.name} updated successfully.'})
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_group_user_only,name='dispatch')
class InstituteGroupDashboardView(TemplateView):
    # template_name="topteenfrontend/user/institute_group_dashboard.html"
    # template_name="topteenfrontend/user/app/institute_group_dashboard.html"
    template_name="template20/institute/institute_group_dashboard.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_group_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]

    def html_head(self):
        name='Institute Group Dashboard'
        return build_html_head(title=name, description=name)
    
    def get_student_test_sreams(self, user):
        try:
            # Get all results for the user
            results = Results.objects.filter(user=user)
            
            if not results.exists():
                return None
            
            # Try to get test3 result first (personality test)
            test3_result = None
            try:
                test3_result = Results.objects.get(user=user, test_paper='test3')
            except Results.DoesNotExist:
                pass
            
            # If test3 exists, use it for personality data
            if test3_result:
                personality_res = test3_result.results
                sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
            else:
                # If no test3, try to get any available test result
                latest_result = results.last()
                if latest_result.results:
                    sreams_scores = {label.split("_")[0].upper(): value for label, value in latest_result.results.items()}
                else:
                    sreams_scores = {}

            return {
                "streams": sreams_scores,  # Include the scores
            }

        except Exception as e:
            print(f"An error occurred in get_student_test_sreams: {e}")
            return None
    
    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}        

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        return stream_counts
    
    def get_institute_group_info(self, group_admin, search_params=None):
        # All institutes in any group owned by this admin (avoid relying on .first()
        # InstituteGroup row, which can diverge from decorator/user_type access paths).
        institutes = Institute.objects.filter(
            institute_group__institute_group_admin=group_admin
        ).distinct()

        self.update_institute_streams(institutes)

        # Apply filters if provided
        if search_params:
            # Institute name search
            if search_params.get('institute'):
                institutes = institutes.filter(
                    name__icontains=search_params['institute']
                )

            # Location exact match
            if search_params.get('location'):
                institutes = institutes.filter(
                    address__iexact=search_params['location']
                )

            # Location search
            if search_params.get('location_search'):
                institutes = institutes.filter(
                    address__icontains=search_params['location_search']
                )

        institutes = institutes.annotate(student_count=Count("student_management"))

        # Get unique locations for dropdown
        locations = institutes.values_list('address', flat=True).distinct()

        institute_data = [
            {
                'address': institute.address,
                'student_count': institute.student_count,
            }
            for institute in institutes
        ]

        # Students across every institute in groups this admin owns
        tstudents = student_management_for_institute_group_admin(group_admin)
        results_data = {}
        for stu in tstudents:
            student_result = self.get_student_test_sreams(stu.student)
            if student_result:  # Only include results that were found
                results_data[stu.student] = student_result
        
        # If you want to create a list of results instead of a dictionary
        test_results = list(results_data.values())
                
        return {
            "institutes": institutes,
            "student_count": tstudents.count(),
            "counselor_count": Counselor.objects.filter(
                counselor_admin__institute_group__institute_group_admin=group_admin
            )
            .distinct()
            .count(),
            "institute_data": institute_data,
            "tstudents": tstudents,
            "streams": self.get_stream(test_results) if 'test_results' in locals() else {},
            "locations": locations  # Add locations for dropdown
        }

    def update_institute_streams(request, institutes):
        # Ensure that the user is allowed to update this institute
        
        pass
    
    def get_context(self,request,*args,**kwargs):
        ctx={}
        from institute.psychometric_packages import build_marketing_psychometric_form_ctx

        ctx.update(build_marketing_psychometric_form_ctx())
        ctx["html_head"] = self.html_head()
        
        # Check if this is an AJAX request for specific data
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')
        
        search_params = {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip()
        }

        group_admin = request.user
        institute_group = InstituteGroup.objects.filter(institute_group_admin=group_admin).order_by(
            "id"
        ).first()
        ig_institutes_qs = Institute.objects.filter(
            institute_group__institute_group_admin=group_admin
        ).distinct()
        ig_scope = ig_institutes_qs.exists()
        _ig_detached_gid = institute_group.id if institute_group else None

        if is_ajax and data_type == 'stats':
            # AJAX request for statistics (credits, counts)
            _stu_scope = student_management_for_institute_group_admin(group_admin)
            remaining_credits = get_global_remain_credits()
            ctx.update({
                'total_stu_count': _stu_scope.count(),
                'counselors_count': Counselor.objects.filter(
                    counselor_admin__institute_group__institute_group_admin=group_admin
                ).distinct().count(),
                'total_credits': (
                    sum(inst.credit_counts for inst in ig_institutes_qs) if ig_scope else 0
                ),
                'remaining_credits': remaining_credits,
            })
        elif is_ajax and data_type == 'charts':
            # AJAX request for charts data - OPTIMIZED for performance
            if not ig_scope:
                ctx.update({
                    'institutes': [],
                    'total_students_count': 0,
                    'test_result_count': 0,
                    'streams': {},
                    'streams_chart_data': [],
                    'seat_capacity_institutes': [],
                })
            else:
                # OPTIMIZED: Get institute data for students per institute chart
                institute_data = list(
                    ig_institutes_qs.annotate(student_count=Count('student_management'))
                    .values('id', 'name', 'student_count')
                    .order_by('-student_count')[:20]  # Top 20 institutes
                )

                # Get full institute list for seat capacity table
                seat_capacity_institutes = list(
                    ig_institutes_qs.values(
                        'id', 'name', 'address', 'pcm', 'cbm', 'comm', 'hme', 'hmb'
                    ).order_by('name')[:100]  # Limit to 100 institutes
                )

                # OPTIMIZED: Get total student count
                total_students_count = student_management_for_institute_group_admin(
                    group_admin
                ).count()

                # OPTIMIZED: Get test result count (primary psychometric battery complete)
                _psych_done_ig = _sm_primary_psychometric_tests_complete_exists()
                test_result_count = (
                    student_management_for_institute_group_admin(group_admin)
                    .filter(student_id__isnull=False)
                    .filter(_psych_done_ig)
                    .count()
                )

                # OPTIMIZED: Get streams data (completed students only)
                sample_students = (
                    student_management_for_institute_group_admin(group_admin)
                    .filter(student_id__isnull=False)
                    .filter(_psych_done_ig)
                    .select_related("student")[:200]
                )
                
                student_users = [stu.student for stu in sample_students]
                test_results_queryset = Results.objects.filter(
                    user__in=student_users,
                    test_paper='test3'
                ).select_related('user')[:200]
                
                results_map = {result.user: result for result in test_results_queryset}
                test_results = []
                for stu in sample_students:
                    if stu.student in results_map:
                        result = results_map[stu.student]
                        if result.results:
                            personality_res = result.results
                            sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                            test_results.append({"streams": sreams_scores})
                
                streams_data = self.get_stream(test_results) if test_results else {}
                
                # Convert streams dict to list format for chart
                streams_chart_data = []
                if streams_data:
                    sorted_streams = sorted(streams_data.items(), key=lambda x: x[1], reverse=True)[:15]
                    for stream, count in sorted_streams:
                        streams_chart_data.append({
                            'stream': stream,
                            'count': count
                        })
                
                ctx.update({
                    'institutes': institute_data,
                    'total_students_count': total_students_count,
                    'test_result_count': test_result_count,
                    'streams': streams_data,
                    'streams_chart_data': streams_chart_data,
                    'seat_capacity_institutes': seat_capacity_institutes,
                })
        elif is_ajax and data_type == 'institutes':
            # AJAX request for institute table
            info = self.get_institute_group_info(group_admin, search_params)
            institutes_list = info['institutes']
            per_page = int(request.GET.get('per_page', 10))
            if per_page == 0:
                per_page = institutes_list.count() if institutes_list else 10
            pages = Paginator(institutes_list, per_page)
            page_number = request.GET.get('page', 1)
            try:
                ctx['institutes_paginations'] = pages.get_page(page_number)
            except:
                ctx['institutes_paginations'] = pages.get_page(1)
            ctx['search_params'] = search_params
            ctx['per_page'] = per_page
            _icmap, _igsel = build_institute_group_counselor_ui_maps(
                ig_institutes_qs,
                detached_institute_group_id=_ig_detached_gid,
            )
            ctx["ig_institute_counselors_map"] = _icmap
            ctx["ig_group_counselors_select"] = _igsel
        else:
            # Default page load - lightweight initial data
            info = self.get_institute_group_info(group_admin, search_params)
            institutes_list = info['institutes']        
            pages = Paginator(institutes_list, 3)
            page_number = request.GET.get('page', 1)
            
            # Update context
            try:
                institutes_paginations = pages.get_page(page_number)
            except:
                institutes_paginations = pages.get_page(1)
            
            from core.ttv2_dashboard_analytics import build_ttv2_analytics, empty_ttv2_analytics
            from institute.counselor_component_data import (
                build_unique_counselor_identity_rows,
                build_ig_counselor_placement_rows,
                filter_counselor_data_list_by_query,
                filter_ig_placement_rows_by_query,
            )

            _sm_ig = student_management_for_institute_group_admin(group_admin)
            # v2 quick-links: used by modal dropdowns (add counselor / bulk upload)
            try:
                ctx["ttv2_quicklink_institutes"] = build_ttv2_quicklink_institutes(group_admin)
            except Exception:
                ctx["ttv2_quicklink_institutes"] = []
            _dr_start, _dr_end = _ttv2_date_range_from_request(request)
            try:
                ctx["ttv2_analytics"] = build_ttv2_analytics(
                    "institute_group",
                    student_management_qs=_sm_ig,
                    week_start=_ttv2_week_start_from_request(request),
                    date_start=_dr_start,
                    date_end=_dr_end,
                )
                _roster_n = int(_sm_ig.count())
                if isinstance(ctx.get("ttv2_analytics"), dict):
                    ctx["ttv2_analytics"].setdefault("kpi", {})
                    ctx["ttv2_analytics"]["kpi"]["total_students"] = _roster_n
            except Exception:
                ctx["ttv2_analytics"] = empty_ttv2_analytics()
            _ig_counselor_iids = list(
                ig_institutes_qs.values_list("id", flat=True).distinct()
            )
            _ig_placement_rows = build_ig_counselor_placement_rows(_ig_counselor_iids)
            ctx["counselor_data_list"] = build_unique_counselor_identity_rows(
                _ig_counselor_iids,
                detached_institute_group_id=_ig_detached_gid,
            )
            _ig_cq = (request.GET.get("counselor_q") or "").strip()
            ctx["counselor_q"] = _ig_cq
            if _ig_cq:
                ctx["counselor_data_list"] = filter_counselor_data_list_by_query(
                    ctx["counselor_data_list"], _ig_cq
                )
                _ig_placement_rows = filter_ig_placement_rows_by_query(
                    _ig_placement_rows, _ig_cq
                )
            ctx["ig_counselor_placement_rows"] = _ig_placement_rows
            _icmap, _igsel = build_institute_group_counselor_ui_maps(
                ig_institutes_qs,
                detached_institute_group_id=_ig_detached_gid,
            )
            ctx["ig_institute_counselors_map"] = _icmap
            ctx["ig_group_counselors_select"] = _igsel
            ctx.update({
                'institutes_paginations': institutes_paginations,
                'total_institute_count': institutes_list.count() if institutes_list else 0,
                'total_stu_count': _sm_ig.count(),
                'counselors_count': info['counselor_count'],
                'institutes': info['institute_data'],
                'total_students_count': info['tstudents'],
                'test_result_count': [r1 for r1 in info['tstudents'] if r1.get_test_result()],
                'streams': info['streams'],
                'locations': info['locations'],
                'institute_names': list(
                    institutes_list.values_list('name', flat=True).distinct()[:200]
                ) if institutes_list is not None else [],
                'search_params': search_params,
                "institute_group": institute_group,
                "institute_groups": InstituteGroup.objects.filter(
                    institute_group_admin=group_admin
                ).order_by(Lower("group_name")),
                "institute_types": choices.InstituteType.CHOICES
            })
        # v2 shell: separate page mode (dashboard/students/assessments/...) from URL
        ctx["ttv2_page"] = (kwargs.get("page") or "dashboard").strip().lower()
        if ctx["ttv2_page"] == "session_report":
            _ttv2_fill_institute_group_session_report_ctx(
                request, group_admin, ctx, ig_institutes_qs
            )
        if ctx["ttv2_page"] == "students":
            sm_scope = scoped_student_management_for_dashboard(request)
            ctx["total_students_count"] = sm_scope.count()
            ctx["class_and_sections"] = get_class_and_sections_by_role(
                request.user, sm_scope
            )
            ctx["unique_streams"] = get_unique_streams_by_role(request.user, sm_scope)
        from institute.tieup_billing import attach_group_tieup_payment_ctx

        status_filter = None
        institute_filter = ""
        if ctx["ttv2_page"] == "payments":
            status_filter = (request.GET.get("status") or "").strip().lower() or None
            institute_filter = (request.GET.get("institute") or "").strip()
        attach_group_tieup_payment_ctx(
            ctx,
            request.user,
            status_filter=status_filter,
            institute_slug=institute_filter or None,
        )
        if ctx["ttv2_page"] == "payments":
            ctx["ttv2_tieup_payments"] = ctx.get("tieup_payment_rows") or ctx.get("rows", [])
            ctx["ttv2_payments_status_filter"] = status_filter or ""
            ctx["ttv2_payments_institute_filter"] = institute_filter
            ctx["tieup_payment_institutes"] = ctx.get("tieup_coupon_institutes") or []
            ctx["is_group_view"] = True
        if ctx["ttv2_page"] == "accounts":
            from institute.accounts_analytics import build_group_accounts_ctx

            ctx["ttv2_accounts"] = build_group_accounts_ctx(request.user, request)
        return ctx
    
    def get_search_parameters(self, request):
        """Extract and validate search parameters from request"""
        return {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip()
        }

    def apply_filters(self, queryset, search_params):
        """Apply filters to queryset based on search parameters"""
        if search_params.get('institute'):
            queryset = queryset.filter(name__icontains=search_params['institute'])
        
        if search_params.get('location'):
            queryset = queryset.filter(address__iexact=search_params['location'])
            
        if search_params.get('location_search'):
            queryset = queryset.filter(address__icontains=search_params['location_search'])
        
        return queryset
    
    def get(self,request,*args,**kwargs):
        from django.template.loader import render_to_string
        from django.http import JsonResponse, HttpResponse
        import json
        
        # Check if this is an AJAX request for specific data
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')
        
        if is_ajax and data_type == 'students_analytics':
            qs = student_management_for_institute_group_admin(request.user)
            return JsonResponse(
                build_students_analytics_payload(qs, week_start=_ttv2_week_start_from_request(request))
            )
        if is_ajax and data_type == "session_history_student":
            return _ttv2_session_history_student_response(
                request,
                scoped_student_management_for_dashboard(request),
            )
        if is_ajax and data_type == "sessions":
            return _ttv2_json_weekly_sessions_for_student_scope(
                request,
                student_management_for_institute_group_admin(request.user),
            )
        if is_ajax and data_type == "students":
            from institute.student_table_helpers import (
                get_student_action_urls,
                get_student_table_config,
            )

            stu_qs = (
                scoped_student_management_for_dashboard(request)
                .select_related("student", "class_and_section", "institute", "counselor")
                .prefetch_related("counselors")
            )
            scoped_institute = _resolve_dashboard_institute_from_request(request)
            iv = InstituteDashboardView()
            ctx = iv.get_student_table_context_ajax(
                request,
                *args,
                stu_manage=stu_qs,
                institute=scoped_institute,
                **kwargs,
            )
            ctx["table_config"] = get_student_table_config("institute_group")
            ctx["action_urls"] = get_student_action_urls("institute_group")
            ctx["students"] = ctx.get("total_students")
            apply_student_table_display_enrichment(request, ctx)
            ctx["ttv2_students_role"] = "institute_group"
            display = (request.GET.get("display") or "").strip().lower()
            if display == "cards":
                return render(
                    request,
                    "template_v2/institute/pages/student_roster_cards.html",
                    ctx,
                )
            return render(request, "template20/shared/students_table.html", ctx)
        if is_ajax and data_type == 'institutes':
            # Return institute table partial
            context = self.get_context(request, *args, **kwargs)
            html = render_to_string('template20/institute/institute_group_institutes_table.html', context, request=request)
            return HttpResponse(html)
        elif is_ajax and data_type in ['stats', 'charts']:
            # Return JSON data for stats or charts
            context = self.get_context(request, *args, **kwargs)
            # Convert QuerySets to counts/lists for JSON serialization
            json_data = {}
            for key, value in context.items():
                # Skip non-serializable items
                if key in ['html_head', 'request', 'search_params', 'institute_group', 'institute_groups', 'institute_types']:
                    continue
                if hasattr(value, 'count') and not isinstance(value, (str, dict, list, int)):
                    try:
                        json_data[key] = value.count()
                    except:
                        json_data[key] = len(value) if hasattr(value, '__len__') else str(value)
                elif hasattr(value, '__iter__') and not isinstance(value, (str, dict)):
                    try:
                        json_data[key] = list(value)
                    except:
                        json_data[key] = str(value)
                elif isinstance(value, (list, dict, int, str, float, bool, type(None))):
                    json_data[key] = value
                else:
                    json_data[key] = str(value)
            return JsonResponse(json_data)
        else:
            # Regular page load (support v2 partial for AJAX shell boot)
            ctx = self.get_context(request, *args, **kwargs)
            payments_partial = _render_ttv2_tieup_payments_partial(request, ctx)
            if payments_partial is not None:
                return payments_partial
            try:
                template_version = (
                    Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
                ).strip()
            except Exception:
                template_version = "v1"
            if template_version == "v2" and request_wants_ttv2_dashboard_body_partial(request):
                return render(request, "template_v2/dashboard_unified_body.html", ctx)
            return render(request, _dashboard_primary_template_name(self), ctx)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class InstituteBlockView(TemplateView):
    def get(self,request,*args,**kwargs):
        id=kwargs.get("id")
        ins_user=get_object_or_404(User,id=id)
        if ins_user.user_status==choices.UserStatus.UNBLOCK:
            ins_user.user_status=choices.UserStatus.BLOCK
            ins_user.save()
        else:
            ins_user.user_status=choices.UserStatus.UNBLOCK
            ins_user.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class MarketingBlockView(TemplateView):
    """
    View to activate/deactivate marketing users (admin only)
    """
    def get(self,request,*args,**kwargs):
        id=kwargs.get("id")
        marketing_user=get_object_or_404(User,id=id, user_type=choices.UserType.MARKETINGGROUPADMIN)
        if marketing_user.user_status==choices.UserStatus.UNBLOCK:
            marketing_user.user_status=choices.UserStatus.BLOCK
            marketing_user.save()
        else:
            marketing_user.user_status=choices.UserStatus.UNBLOCK
            marketing_user.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class InstituteChangePasswordView(TemplateView):
    def post(self, request, *args, **kwargs):
        
        id=request.POST.get("password_id")
        password=request.POST.get("change_password")
        user=get_object_or_404(User,id=id)
        user.set_password(password)
        user.save()
        send_new_student_credential.delay(user.email,password)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
from app_post_matric.models import (
    TestCategory, Test, Question, Answer,
    TestSession, UserResponse, TestResult, Sections, SectionSession, TestTopCategories
)
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_authenticated_user_only,name='dispatch')
class InstituteDashboardView(TemplateView):
    # template_name="topteenfrontend/user/institute_dashboard.html" 
    # template_name="topteenfrontend/user/app/profile_index.html" 
    template_name="template20/institute/institute_dashboard.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]
    
    def html_head(self):
        name='Institute Dashboard'
        return build_html_head(title=name, description=name)
    
    
    def get_student_test(self,user):
        ctd=CentralTestCandidate.objects.filter(user=user)
        if ctd.exists():
            test=ctd.last().candidate_test.last()
            if test.is_success == choices.YesNoChoices.YES:
                link="{}{}".format('https://www.topteen.in',test.get_pyschometric_test_result_url())
                return link
                # return True
            else:
                return test.test_link
                # return False
        else:
            return ""

    def get_post_matric_student(self, user):
        # Check if all 4 tests are completed
        test1_completed = TestSession.objects.filter(
            user=user, 
            test__id=1,
            is_completed=True
        ).exists()
        
        test2_completed = TestSession.objects.filter(
            user=user, 
            test__id=2,
            is_completed=True
        ).exists()
        
        test3_completed = TestSession.objects.filter(
            user=user, 
            test__id=3,
            is_completed=True
        ).exists()
        
        test4_completed = TestSession.objects.filter(
            user=user, 
            test__id=4,
            is_completed=True
        ).exists()
        
        all_tests_completed = test1_completed and test2_completed and test3_completed and test4_completed
        

        
        # From APTITUDE
        return all_tests_completed
    
    def get_student_test_result(self, user):
        try:
            # Check student's class to determine which system to use
            student_management = StudentManagement.objects.filter(student=user).first()
            
            if student_management and student_management.class_and_section:
                class_name = student_management.class_and_section.class_and_section
                
                # Extract class number
                class_number = None
                try:
                    import re
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                except (ValueError, IndexError):
                    pass
                
                # Determine system based on class
                if class_number and class_number >= 11:
                    institute = getattr(student_management, "institute", None)
                    from app_post_matric.models import TestSession, TestResult
                    post_matric_sessions = TestSession.objects.filter(user=user)
                    # Demo Class 11–12: post-matric when seeded; else legacy psychometric
                    if institute and getattr(institute, "is_system_demo", False):
                        if post_matric_sessions.filter(is_completed=True).exists():
                            return self._get_post_matric_test_result(user, post_matric_sessions)
                        return self._get_psychometric_test_result(user)
                    return self._get_post_matric_test_result(user, post_matric_sessions)
                else:
                    # Class 10 and below: Use psychometric system
                    return self._get_psychometric_test_result(user)
            else:
                # No class information, default to psychometric system
                return self._get_psychometric_test_result(user)
                
        except Exception as e:
            print(f"An error occurred in get_student_test_result: {e}")
            return {
                "streams": {},
                "test_success": False,
                "test_link": None,
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False
                },
                "tooltip": "Error loading test data"
            }
    
    def _get_post_matric_test_result(self, user, test_sessions):
        """Handle post-matric students (class 11-12) using TestSession/TestResult"""
        try:
            test_completion = {
                "personality_assessment": False,
                "motivation_assessment": False,
                "career_interest_inventory": False,
                "aptitude_assessment": False,
            }

            # Prefer test title mapping (stable across DBs); keep ID fallback for legacy rows.
            for session in test_sessions:
                test_obj = getattr(session, "test", None)
                # Consider attempted if marked completed OR any result payload exists.
                has_result_payload = False
                try:
                    sr = getattr(session, "result", None)
                    if sr and (
                        getattr(sr, "score", None) is not None
                        or bool(getattr(sr, "result_data", None))
                        or bool(getattr(sr, "category_counts", None))
                    ):
                        has_result_payload = True
                except Exception:
                    has_result_payload = False
                if not (getattr(session, "is_completed", False) or has_result_payload):
                    continue
                test_title = (getattr(test_obj, "title", "") or "").strip().lower()
                matched = False
                if test_title:
                    if "aptitude" in test_title:
                        test_completion["aptitude_assessment"] = True
                        matched = True
                    elif "motivation" in test_title:
                        test_completion["motivation_assessment"] = True
                        matched = True
                    elif "career interest" in test_title:
                        test_completion["career_interest_inventory"] = True
                        matched = True
                    elif "personality" in test_title or "career assessment" in test_title:
                        test_completion["personality_assessment"] = True
                        matched = True

                if not matched and test_obj and getattr(test_obj, "id", None):
                    legacy_map = {
                        1: "personality_assessment",
                        2: "motivation_assessment",
                        3: "career_interest_inventory",
                        4: "aptitude_assessment",
                    }
                    key = legacy_map.get(test_obj.id)
                    if key:
                        test_completion[key] = True
            
            # Count completed tests
            completed_tests = sum(test_completion.values())
            
            
            # Determine overall status and create detailed tooltip
            completed_list = []
            not_completed_list = []
            
            if test_completion["personality_assessment"]:
                completed_list.append("Personality")
            else:
                not_completed_list.append("Personality")
                
            if test_completion["motivation_assessment"]:
                completed_list.append("Motivation")
            else:
                not_completed_list.append("Motivation")
                
            if test_completion["career_interest_inventory"]:
                completed_list.append("Career Interest")
            else:
                not_completed_list.append("Career Interest")
                
            if test_completion["aptitude_assessment"]:
                completed_list.append("Aptitude")
            else:
                not_completed_list.append("Aptitude")
            
            # Create detailed tooltip showing all test statuses
            tooltip_parts = []
            if completed_list:
                tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
            if not_completed_list:
                tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
            tooltip = " | ".join(tooltip_parts)
            
            # Determine overall status
            if completed_tests == 0:
                test_status = "no_tests"
            elif completed_tests == 4:
                test_status = "completed"
            else:
                test_status = "in_progress"
            
            # Get test link - only provide link if all tests are completed
            test_link = None
            if test_status == "completed":
                # test_link = reverse('post_matric:tests')
                test_link = f"{reverse('post_matric:combined_report',args=[user.id])}"
            
            
            return {
                "streams": {},
                "test_success": completed_tests > 0,
                "test_link": test_link,
                "success_count": completed_tests,
                "test_status": test_status,
                "test_details": {
                    "test1": test_completion["personality_assessment"],
                    "test2": test_completion["motivation_assessment"],
                    "test3": test_completion["career_interest_inventory"],
                    "test4": test_completion["aptitude_assessment"],
                    "personality_assessment": test_completion["personality_assessment"],
                    "career_assessment": test_completion["personality_assessment"],
                    "motivation_assessment": test_completion["motivation_assessment"],
                    "career_interest_inventory": test_completion["career_interest_inventory"],
                    "aptitude_assessment": test_completion["aptitude_assessment"],
                },
                "tooltip": tooltip
            }
            
        except Exception as e:
            print(f"Error in _get_post_matric_test_result: {e}")
            return {
                "streams": {},
                "test_success": False,
                "test_link": reverse('post_matric:tests'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False,
                    "test4": False
                },
                "tooltip": "Error loading post-matric test data"
            }
    
    def _get_psychometric_test_result(self, user):
        """Handle psychometric students (class 1-10) using TestCompletion/Results"""
        try:
            # Check TestCompletion first to determine if student has completed tests
            test_completion = None
            try:
                test_completion = TestCompletion.objects.get(user=user)
            except TestCompletion.DoesNotExist:
                # If no TestCompletion record exists, student hasn't taken any tests
                return {
                    "streams": {},
                    "test_success": False,
                    "test_link": reverse('app:test_buttons'),
                    "success_count": 0,
                    "test_status": "no_tests",
                    "test_details": {
                        "test1": False,
                        "test2": False,
                        "test3": False
                    },
                    "tooltip": "No tests taken"
                }
            
            # Get individual test completion status
            test1_complete = test_completion.test1_complete
            test2_complete = test_completion.test2_complete
            
            # Verify test3_complete - only True if ALL subtests are complete
            all_test3_subtests_complete = (
                test_completion.numerical_complete and
                test_completion.verbal_complete and
                test_completion.logical_complete and
                test_completion.emotional_complete and
                test_completion.machanical_complete and
                test_completion.language_complete and
                test_completion.spatial_complete
            )
            
            # Correct test3_complete if it's incorrectly set
            if test_completion.test3_complete and not all_test3_subtests_complete:
                test_completion.test3_complete = False
                test_completion.save()
            elif not test_completion.test3_complete and all_test3_subtests_complete:
                test_completion.test3_complete = True
                test_completion.save()
            
            test3_complete = test_completion.test3_complete
            
            # Count completed tests
            completed_tests = sum([test1_complete, test2_complete, test3_complete])
            
            # Create detailed tooltip showing all test statuses
            completed_list = []
            not_completed_list = []
            
            if test1_complete:
                completed_list.append("Career Interest")
            else:
                not_completed_list.append("Career Interest")
                
            if test2_complete:
                completed_list.append("Intelligence")
            else:
                not_completed_list.append("Intelligence")
                
            if test3_complete:
                completed_list.append("Personality")
            else:
                not_completed_list.append("Personality")
            
            # Create detailed tooltip showing all test statuses
            tooltip_parts = []
            if completed_list:
                tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
            if not_completed_list:
                tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
            tooltip = " | ".join(tooltip_parts)
            
            # Determine overall status
            if completed_tests == 0:
                test_status = "no_tests"
            elif completed_tests == 3:
                test_status = "completed"
            else:
                test_status = "in_progress"
            
            # Get streams data if any tests are completed
            scores = {}
            if completed_tests > 0:
                results = Results.objects.filter(user=user)
                
                # Try to get test3 result first (personality test) for streams data
                test3_result = None
                try:
                    test3_result = Results.objects.get(user=user, test_paper='test3')
                except Results.DoesNotExist:
                    pass
                
                # If test3 exists, use it for personality data
                if test3_result:
                    personality_res = test3_result.results
                    scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                else:
                    # If no test3, try to get any available test result
                    if results.exists():
                        latest_result = results.last()
                        if latest_result.results:
                            scores = {label.split("_")[0].upper(): value for label, value in latest_result.results.items()}

            # Get test link - only provide link if all tests are completed
            test_link = None
            if test_status == "completed":
                results = Results.objects.filter(user=user)
                if results.exists():
                    latest_result = results.last()
                    test_link = latest_result.get_test_report_or_test_link(user)
                else:
                    # If no Results but has TestCompletion, link to test buttons
                    test_link = reverse('app:test_buttons')

            return {
                "streams": scores,
                "test_success": completed_tests > 0,
                "test_link": test_link,
                "success_count": completed_tests,
                "test_status": test_status,
                "test_details": {
                    "test1": test1_complete,
                    "test2": test2_complete,
                    "test3": test3_complete
                },
                "tooltip": tooltip
            }
            
        except Exception as e:
            print(f"Error in _get_psychometric_test_result: {e}")
            return {
                "streams": {},
                "test_success": False,
                "test_link": reverse('app:test_buttons'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False
                },
                "tooltip": "Error loading psychometric test data"
            }

    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        # Extract unique streams and counts
        unique_streams = list(stream_counts.keys())
        counts = list(stream_counts.values())
        return stream_counts
    
    def get_filter_data(self,request,data):
        import csv
        response=HttpResponse(content_type="text/csv")
        writer=csv.writer(response)
        writer.writerow(['Name','Email','Class','Mobile','test taken','Test Link'])
        for d in data:
            test_result = self.get_student_test_result(d.student)
            # Extracting the specific fields
            test_link = test_result.get("test_link", None) if test_result else None
            test_success = test_result.get("test_success", False) if test_result else False
            writer.writerow([d.student.name,d.student.email,d.class_and_section,d.student.mobile,test_success,test_link])
        response['Content-Disposition'] = 'attachment; filename="students_data.csv"'
        return response
    
    def get_higher_class_result(self, stu_manage):
        higher_class_students = [ts.student for ts in stu_manage if 
                            ts.class_and_section.class_and_section in ['11', '12', '11th', '12th']]
        return higher_class_students
    
    def _get_student_test_result_optimized(self, user, student_management, test_completion, post_matric_sessions, results_list):
        """
        Optimized version of get_student_test_result that uses pre-fetched data.
        This avoids N+1 queries by using batch-fetched data.
        """
        try:
            if student_management and student_management.class_and_section:
                class_name = student_management.class_and_section.class_and_section
                
                # Extract class number
                class_number = None
                try:
                    import re
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                except (ValueError, IndexError):
                    pass
                
                # Class 11–12: post-matric (demo institutes use it when sessions are seeded)
                if class_number and class_number >= 11:
                    institute = getattr(student_management, "institute", None)
                    if institute and getattr(institute, "is_system_demo", False):
                        if any(getattr(s, "is_completed", False) for s in (post_matric_sessions or [])):
                            return self._get_post_matric_test_result_optimized(user, post_matric_sessions)
                        return self._get_psychometric_test_result_optimized(user, test_completion, results_list)
                    return self._get_post_matric_test_result_optimized(user, post_matric_sessions)
                else:
                    # Class 10 and below: Use psychometric system
                    return self._get_psychometric_test_result_optimized(user, test_completion, results_list)
            else:
                # No class information, default to psychometric system
                return self._get_psychometric_test_result_optimized(user, test_completion, results_list)
                
        except Exception as e:
            print(f"An error occurred in _get_student_test_result_optimized: {e}")
            return {
                "streams": {},
                "test_success": False,
                "test_link": None,
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False
                },
                "tooltip": "Error loading test data"
            }
    
    def _get_post_matric_test_result_optimized(self, user, test_sessions):
        """Optimized version using pre-fetched test_sessions"""
        try:
            test_completion = {
                "personality_assessment": False,
                "motivation_assessment": False,
                "career_interest_inventory": False,
                "aptitude_assessment": False,
            }

            # Prefer title-based mapping; IDs are not stable across environments.
            for session in test_sessions:
                test_obj = getattr(session, "test", None)
                has_result_payload = False
                try:
                    sr = getattr(session, "result", None)
                    if sr and (
                        getattr(sr, "score", None) is not None
                        or bool(getattr(sr, "result_data", None))
                        or bool(getattr(sr, "category_counts", None))
                    ):
                        has_result_payload = True
                except Exception:
                    has_result_payload = False
                if not ((getattr(session, "is_completed", False) or has_result_payload) and test_obj):
                    continue
                test_title = (getattr(test_obj, "title", "") or "").strip().lower()
                matched = False
                if test_title:
                    if "aptitude" in test_title:
                        test_completion["aptitude_assessment"] = True
                        matched = True
                    elif "motivation" in test_title:
                        test_completion["motivation_assessment"] = True
                        matched = True
                    elif "career interest" in test_title:
                        test_completion["career_interest_inventory"] = True
                        matched = True
                    elif "personality" in test_title or "career assessment" in test_title:
                        test_completion["personality_assessment"] = True
                        matched = True

                if not matched:
                    legacy_map = {
                        1: "personality_assessment",
                        2: "motivation_assessment",
                        3: "career_interest_inventory",
                        4: "aptitude_assessment",
                    }
                    key = legacy_map.get(getattr(test_obj, "id", None))
                    if key:
                        test_completion[key] = True
            
            # Count completed tests
            completed_tests = sum(test_completion.values())
            
            # Determine overall status and create detailed tooltip
            completed_list = []
            not_completed_list = []
            
            if test_completion["personality_assessment"]:
                completed_list.append("Personality")
            else:
                not_completed_list.append("Personality")
                
            if test_completion["motivation_assessment"]:
                completed_list.append("Motivation")
            else:
                not_completed_list.append("Motivation")
                
            if test_completion["career_interest_inventory"]:
                completed_list.append("Career Interest")
            else:
                not_completed_list.append("Career Interest")
                
            if test_completion["aptitude_assessment"]:
                completed_list.append("Aptitude")
            else:
                not_completed_list.append("Aptitude")
            
            # Create detailed tooltip showing all test statuses
            tooltip_parts = []
            if completed_list:
                tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
            if not_completed_list:
                tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
            tooltip = " | ".join(tooltip_parts)
            
            # Determine overall status
            if completed_tests == 0:
                test_status = "no_tests"
            elif completed_tests == 4:
                test_status = "completed"
            else:
                test_status = "in_progress"
            
            # Get test link - only provide link if all tests are completed
            test_link = None
            if test_status == "completed":
                from django.urls import reverse
                test_link = f"{reverse('post_matric:combined_report',args=[user.id])}"
            
            return {
                "streams": {},
                "test_success": completed_tests > 0,
                "test_link": test_link,
                "success_count": completed_tests,
                "test_status": test_status,
                "test_details": {
                    "test1": test_completion["personality_assessment"],
                    "test2": test_completion["motivation_assessment"],
                    "test3": test_completion["career_interest_inventory"],
                    "test4": test_completion["aptitude_assessment"],
                    "personality_assessment": test_completion["personality_assessment"],
                    "career_assessment": test_completion["personality_assessment"],
                    "motivation_assessment": test_completion["motivation_assessment"],
                    "career_interest_inventory": test_completion["career_interest_inventory"],
                    "aptitude_assessment": test_completion["aptitude_assessment"],
                },
                "tooltip": tooltip
            }
            
        except Exception as e:
            print(f"Error in _get_post_matric_test_result_optimized: {e}")
            from django.urls import reverse
            return {
                "streams": {},
                "test_success": False,
                "test_link": reverse('post_matric:tests'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False,
                    "test4": False
                },
                "tooltip": "Error loading post-matric test data"
            }
    
    def _get_psychometric_test_result_optimized(self, user, test_completion, results_list):
        """Optimized version using pre-fetched test_completion and results_list"""
        try:
            if not test_completion:
                # If no TestCompletion record exists, student hasn't taken any tests
                return {
                    "streams": {},
                    "test_success": False,
                    "test_link": None,
                    "success_count": 0,
                    "test_status": "no_tests",
                    "test_details": {
                        "test1": False,
                        "test2": False,
                        "test3": False
                    },
                    "tooltip": "No tests taken"
                }
            
            # Get individual test completion status
            test1_complete = test_completion.test1_complete
            test2_complete = test_completion.test2_complete
            
            # Verify test3_complete - only True if ALL subtests are complete
            all_test3_subtests_complete = (
                test_completion.numerical_complete and
                test_completion.verbal_complete and
                test_completion.logical_complete and
                test_completion.emotional_complete and
                test_completion.machanical_complete and
                test_completion.language_complete and
                test_completion.spatial_complete
            )
            
            # Use computed subtest state for display; do not write on dashboard read.
            test3_complete = all_test3_subtests_complete
            
            # Count completed tests
            completed_tests = sum([test1_complete, test2_complete, test3_complete])
            
            # Create detailed tooltip showing all test statuses
            completed_list = []
            not_completed_list = []
            
            if test1_complete:
                completed_list.append("Career Interest")
            else:
                not_completed_list.append("Career Interest")
                
            if test2_complete:
                completed_list.append("Intelligence")
            else:
                not_completed_list.append("Intelligence")
                
            if test3_complete:
                completed_list.append("Personality")
            else:
                not_completed_list.append("Personality")
            
            # Create detailed tooltip showing all test statuses
            tooltip_parts = []
            if completed_list:
                tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
            if not_completed_list:
                tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
            tooltip = " | ".join(tooltip_parts)
            
            # Determine overall status
            if completed_tests == 0:
                test_status = "no_tests"
            elif completed_tests == 3:
                test_status = "completed"
            else:
                test_status = "in_progress"
            
            # Get streams data if any tests are completed
            scores = {}
            if completed_tests > 0 and results_list:
                # Use pre-fetched results_list instead of querying
                # Try to get test3 result first (personality test) for streams data
                test3_result = None
                for result in results_list:
                    if result.test_paper == 'test3':
                        test3_result = result
                        break
                
                if test3_result and test3_result.results:
                    personality_res = test3_result.results
                    scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                
                # Count successful tests from pre-fetched results
                success_count = sum(1 for result in results_list if result.is_test_successful)
            else:
                success_count = 0
            
            # Get test link only when the full Class 10 bundle is complete.
            # Never fall back to the test-home URL — that made Report open a non-report page.
            from django.urls import reverse
            test_link = None
            if test_status == "completed":
                latest_result = None
                if results_list:
                    latest_result = max(results_list, key=lambda r: r.created if hasattr(r, 'created') else r.id)
                    if latest_result:
                        candidate = latest_result.get_test_report_or_test_link(user)
                        if candidate and candidate != '#':
                            test_link = candidate
                if not test_link:
                    test_link = reverse('app:dashboard_for_user', args=[user.id])
            
            return {
                "streams": scores,
                "test_success": completed_tests > 0,
                "test_link": test_link,
                "success_count": success_count,
                "test_status": test_status,
                "test_details": {
                    "test1": test1_complete,
                    "test2": test2_complete,
                    "test3": test3_complete
                },
                "tooltip": tooltip
            }
            
        except Exception as e:
            print(f"Error in _get_psychometric_test_result_optimized: {e}")
            return {
                "streams": {},
                "test_success": False,
                "test_link": None,
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False
                },
                "tooltip": "Error loading psychometric test data"
            }
    
    def get_context(self,request,*args,**kwargs):        
        slug=kwargs.get("slug")
        institute=get_object_or_404(Institute,slug=slug)
        
        # Use centralized function to get students based on role
        # Optimize with select_related and prefetch_related to avoid N+1 queries
        stu_manage = get_students_by_role(request.user, institute=institute).select_related(
            'student', 
            'class_and_section',
            'institute'
        )
        
        # Get filter parameters
        test_taken_filter = request.GET.get('test_taken', '')
        stream_filter = request.GET.get('stream', '')

        # Batch psychometric + Results without materializing all StudentManagement rows
        from psychometric_tests.models import PsychometricTestResult
        from app.models import Results
        student_user_ids = list(
            stu_manage.values_list("student_id", flat=True).filter(student__isnull=False)
        )
        psychometric_results_map = {}
        if student_user_ids:
            psychometric_results = PsychometricTestResult.objects.filter(
                assessment__central_test_candidate__user_id__in=student_user_ids
            ).select_related("assessment__central_test_candidate__user")
            for result in psychometric_results:
                user = result.assessment.central_test_candidate.user
                if user not in psychometric_results_map:
                    psychometric_results_map[user] = []
                psychometric_results_map[user].append(result)

        psych_stu_ids = set(psychometric_results_map.keys())
        ptr_count = stu_manage.filter(student_id__in=[u.id for u in psych_stu_ids]).count()

        test_results_map = {}
        all_results = []
        if student_user_ids:
            all_results = list(
                Results.objects.filter(
                    user_id__in=student_user_ids
                ).select_related("user")
            )
            for result in all_results:
                if result.user not in test_results_map:
                    test_results_map[result.user] = []
                test_results_map[result.user].append(result)

        success_user_ids = {
            r.user_id
            for r in all_results
            if getattr(r, "is_test_successful", False)
        }
        ptr_count1 = stu_manage.filter(student_id__in=success_user_ids).count()
        
        # Use centralized function to get class_and_sections based on role
        class_and_sections = get_class_and_sections_by_role(request.user, stu_manage)
        
        # Get class counts using centralized function
        class_counts = get_class_counts(stu_manage)
        
        # Get unique streams using centralized function
        from counselor.views import get_unique_streams_by_role
        unique_streams = get_unique_streams_by_role(request.user, stu_manage)

        # For initial page load, skip heavy student data processing
        # Student table will be loaded via AJAX with full data
        results_data = {}
        completed_students_count = []
        higher_class_results = {}
        
        # Lightweight streams chart: sample first 200 students, batch Results by user_id
        streams = {}
        if student_user_ids:
            sample_students = list(stu_manage[:200])
            sample_user_ids = [s.student_id for s in sample_students if s.student_id]
            if sample_user_ids:
                test_results_queryset = Results.objects.filter(
                    user_id__in=sample_user_ids,
                    test_paper="test3",
                ).select_related("user")[:200]
                
                # Process streams from sample results - use same format as marketing dashboard
                test_results = []
                results_map = {result.user: result for result in test_results_queryset}
                for stu in sample_students:
                    if stu.student and stu.student in results_map:
                        result = results_map[stu.student]
                        if result.results:
                            personality_res = result.results
                            streams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                            test_results.append({"streams": streams_scores})
                
                # Calculate streams from sample
                if test_results:
                    streams = self.get_stream(test_results)
        
        # Lightweight: Don't convert to list - keep as QuerySet for initial load
        # Only get count for statistics
        total_students_count_list = stu_manage.count() if hasattr(stu_manage, 'count') else len(list(stu_manage))
        
        # Optimize: Batch fetch counselor data and FollowUpStatus records
        counselors = Counselor.qs_for_institute(institute).select_related('counselor_admin')
        counselor_ids = [c.id for c in counselors]

        # v2 dashboard: Unassigned students (not mapped to any counselor)
        ttv2_unassigned_rows = []
        ttv2_counselor_options = []
        try:
            unassigned_qs = (
                stu_manage.filter(counselors__isnull=True)
                .select_related("student", "class_and_section")
                .order_by("-created")
            )
            unassigned_rows = []
            for sm in list(unassigned_qs[:25]):
                u = getattr(sm, "student", None)
                cas = getattr(sm, "class_and_section", None)
                unassigned_rows.append(
                    {
                        "sm_id": sm.id,
                        "student_id": getattr(sm, "student_id", None),
                        "name": getattr(u, "name", None) or getattr(u, "email", None) or "Student",
                        "email": getattr(u, "email", None) or "",
                        "class": getattr(cas, "class_and_section", None) or "",
                        "stream": getattr(cas, "stream", None) or "",
                    }
                )
            ttv2_unassigned_rows = unassigned_rows
            ttv2_counselor_options = [
                _ttv2_counselor_dropdown_row(c.id, getattr(c, "counselor_name", "") or "")
                for c in counselors
            ]
        except Exception:
            ttv2_unassigned_rows = []
            ttv2_counselor_options = []
        
        # Batch fetch all FollowUpStatus records for all counselors at once
        all_followups = FollowUpStatus.objects.filter(counselor_id__in=counselor_ids).select_related('counselor')
        
        # Create maps for efficient lookup
        followups_by_counselor = {}
        for followup in all_followups:
            if followup.counselor_id not in followups_by_counselor:
                followups_by_counselor[followup.counselor_id] = []
            followups_by_counselor[followup.counselor_id].append(followup)
        
        # Batch fetch session data grouped by counselor and date
        from django.db.models import Count
        sessions_data_all = (
            FollowUpStatus.objects
            .filter(counselor_id__in=counselor_ids)
            .values('counselor_id', 'last_follow_up_date')
            .annotate(session_count=Count('id'))
        )
        
        # Group session data by counselor
        sessions_by_counselor = {}
        for session in sessions_data_all:
            counselor_id = session['counselor_id']
            if counselor_id not in sessions_by_counselor:
                sessions_by_counselor[counselor_id] = []
            sessions_by_counselor[counselor_id].append(session)
        
        counselor_data_list = []
        couns_sessions_data = []

        for counselor in counselors:
            counselor_id = counselor.id
            followups = followups_by_counselor.get(counselor_id, [])
            
            # Calculate counts from pre-fetched data
            sessions_count = len(followups)
            # "Students counseled" should match KPI semantics: distinct students with >=1 completed follow-up.
            completed_followups = [f for f in followups if (getattr(f, "follow_up_status", "") or "").lower() == "completed"]
            students_counseled_count = len({int(getattr(f, "student_id", 0) or 0) for f in completed_followups if getattr(f, "student_id", None)})
            
            # Append data for each counselor to the list
            counselor_data_list.append({
                'id': counselor.id,
                'coun_admin': counselor.counselor_admin,
                'name': counselor.counselor_name,
                'email': counselor.counselor_email,
                'sessions': sessions_count,
                'students_counseled': students_counseled_count,
                'completed_followups': int(len(completed_followups)),
                'created': counselor.created
            })
            
            # Get session data for the current counselor from pre-fetched data
            sessions_data_list = sessions_by_counselor.get(counselor_id, [])
            # Convert dates to strings
            for session in sessions_data_list:
                if session.get('last_follow_up_date'):
                    session['last_follow_up_date'] = session['last_follow_up_date'].isoformat()

            # Calculate sessions for the current week (Monday to Saturday)
            week_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}  # Monday to Saturday
            for session in sessions_data_list:
                try:
                    if session.get('last_follow_up_date'):
                        session_date = datetime.strptime(session['last_follow_up_date'], "%Y-%m-%d")
                        day_of_week = session_date.weekday()  # Monday is 0
                        if day_of_week < 6:  # Only consider Monday to Saturday
                            week_data[day_of_week] += session.get('session_count', 0)
                except (KeyError, ValueError) as e:
                    print(f"Error parsing session data: {e} in session: {session}")

            # Prepare the final sessions data for the counselor
            final_sessions_data = []
            for day, count in week_data.items():
                # Calculate the correct date for each day in the week
                # Assume we want the date of the most recent Monday
                recent_monday = datetime.now() - timedelta(days=datetime.now().weekday())
                final_sessions_data.append({
                    "day": (recent_monday + timedelta(days=day)).strftime("%Y-%m-%d"),
                    "session_count": count
                })

            # Append the sessions data for the current counselor to the main list
            couns_sessions_data.append({
                'counselor_id': counselor.id,
                'counselor_name': counselor.counselor_name,
                'sessions': final_sessions_data  # Add sessions data for this counselor
            })
        # Convert to JSON
        try:
            sessions_data_json = json.dumps(couns_sessions_data)
        except Exception as e:
            print(f"Error serializing sessions data: {e}")
            sessions_data_json = '[]'
        
        # For initial page load, create minimal pagination - table will load via AJAX
        # Don't process filters or student data here - it's done in AJAX request
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        # Create a minimal paginator with just 1 item for initial structure
        minimal_students = stu_manage[:1] if hasattr(stu_manage, '__getitem__') else []
        pages = Paginator(minimal_students, 10)
        page_number = request.GET.get('page', 1)
        try:
            total_students = pages.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            total_students = pages.get_page(1)
        
        ctx={}
        ctx["html_head"] = self.html_head()
        # Pass count directly as integer for this specific institute
        ctx['total_students_count'] = total_students_count_list  # Direct count for this institute
        ctx["total_students"]=total_students  # Minimal for initial structure
        ctx["active_students"]=stu_manage.filter(student__is_active=True).count() if hasattr(stu_manage, 'count') else 0
        ctx["psychometric_test_result_count"]=ptr_count  # Just count
        ctx["central_test_candidate"]=CentralTestCandidate.objects.none()  # Don't load all
        ctx["institute"]=institute
        ctx["class_and_sections"]=class_and_sections
        ctx["ttv2_dashboard_body_role"] = "institute"
        if institute:
            from institute.psychometric_packages import (
                build_institute_package_dashboard_ctx,
                get_student_package_labels_for_institute,
            )

            ctx.update(build_institute_package_dashboard_ctx(institute))
            ctx["student_psychometric_packages"] = get_student_package_labels_for_institute(institute)
        ctx['class_counts']=class_counts  # Add class counts for dropdown
        ctx['unique_streams']=unique_streams  # Add unique streams for dropdown
        ctx['stu']=stu_manage  # Keep as QuerySet, don't convert to list
        ctx['results_data']={}  # Empty - will be loaded via AJAX
        ctx['test_result_count']=ptr_count1  # Just count
        ctx['counselor_list']= counselors     
        ctx['counselor_data_list']= counselor_data_list
        ctx["ttv2_unassigned_students"] = ttv2_unassigned_rows
        ctx["ttv2_counselor_options"] = ttv2_counselor_options
        ctx['sessions_data_json']= sessions_data_json 
        ctx['streams'] = streams  # Empty for initial load
        ctx['higher_class_results'] = {}  # Empty for initial load
        ctx['Testsession'] = TestSession
        try:
            from core.ttv2_dashboard_analytics import build_ttv2_analytics, empty_ttv2_analytics
            _dr_start, _dr_end = _ttv2_date_range_from_request(request)

            ctx["ttv2_analytics"] = build_ttv2_analytics(
                "institute",
                institute=institute,
                student_management_qs=stu_manage,
                week_start=_ttv2_week_start_from_request(request),
                date_start=_dr_start,
                date_end=_dr_end,
            )
        except Exception:
            from core.ttv2_dashboard_analytics import empty_ttv2_analytics

            ctx["ttv2_analytics"] = empty_ttv2_analytics()
        # v2 shell: separate page mode (dashboard/students/assessments/...) from URL
        ctx["ttv2_page"] = (kwargs.get("page") or "dashboard").strip().lower()
        _ttv2_dbg(
            {
                "hypothesisId": "H1",
                "location": "institute/views.py:get_context:ttv2_page",
                "message": "Computed ttv2_page",
                "data": {
                    "page_kw": (kwargs.get("page") or ""),
                    "ttv2_page": ctx.get("ttv2_page"),
                    "path": (getattr(request, "path", "") or ""),
                    "ttv2_partial": (request.GET.get("ttv2_partial") or ""),
                },
            }
        )
        if institute:
            from institute.tieup_billing import attach_institute_tieup_payment_ctx

            status_filter = None
            if ctx["ttv2_page"] == "payments":
                status_filter = (request.GET.get("status") or "").strip().lower() or None
            attach_institute_tieup_payment_ctx(
                ctx, institute, request.user, status_filter=status_filter
            )
            if ctx["ttv2_page"] in ("payments", "dashboard"):
                ctx["ttv2_tieup_payments"] = ctx.get("tieup_payment_rows") or ctx.get("rows", [])
                ctx["ttv2_payments_status_filter"] = status_filter or ""

        # Students page: Psychometric assessment PDF stats (MI/EI attempts in scope)
        try:
            from core.models import MIAssessmentResult, EQAssessmentResult
            uids = list(stu_manage.values_list("student_id", flat=True))
            uids = [int(x) for x in uids if x]
            mi_uids = set(MIAssessmentResult.objects.filter(user_id__in=uids).values_list("user_id", flat=True).distinct())
            eq_uids = set(EQAssessmentResult.objects.filter(user_id__in=uids).values_list("user_id", flat=True).distinct())
            attempted = len(mi_uids.union(eq_uids))
            ctx["ttv2_psych_pdf"] = {"attempted": attempted, "total": len(set(uids))}
        except Exception:
            ctx["ttv2_psych_pdf"] = {"attempted": 0, "total": 0}
        # v2 unified body picks the embedded partial from ttv2_role_ctx.role, not the URL. A
        # marketing (or other) user opening an institute dashboard URL with ?ttv2_partial=1
        # can still render marketing_group_dashboard_body, which expects search_params.
        _raw_status = (request.GET.get("status") or "").strip().lower()
        _sp_status = _raw_status if _raw_status in ("pending", "approved", "rejected", "") else ""
        ctx["search_params"] = {
            "institute": request.GET.get("institute", "").strip(),
            "location": request.GET.get("location", "").strip(),
            "location_search": request.GET.get("location_search", "").strip(),
            "status": _sp_status,
        }

        # v2 "Streams & capacity" page: counts per stream vs configured seat capacity on Institute.
        # NOTE: this must live in this get_context() (the one used for v2 partial loads).
        if (ctx.get("ttv2_page") or "").strip().lower() == "streams_capacity":
            inst = ctx.get("institute")
            stu_qs = ctx.get("stu")
            # Always build capacity rows; stream enrollment aggregation may fail in some deployments.
            cap_map = {
                "PCM": int(getattr(inst, "pcm", 0) or 0) if inst else 0,
                "CBM": int(getattr(inst, "cbm", 0) or 0) if inst else 0,
                "COMM": int(getattr(inst, "comm", 0) or 0) if inst else 0,
                "HME": int(getattr(inst, "hme", 0) or 0) if inst else 0,
                "HMB": int(getattr(inst, "hmb", 0) or 0) if inst else 0,
            }

            def _norm_stream_code(raw):
                v = (raw or "").strip().upper()
                if not v:
                    return ""
                # Backwards-compatible aliases used across templates/datasets
                alias = {
                    "CB": "CBM",
                    "MCOM": "COMM",
                    "HUM": "HME",
                    "HM": "HMB",
                }
                return alias.get(v, v)

            stream_counts = {}
            if hasattr(stu_qs, "exclude"):
                try:
                    for row in (
                        stu_qs.exclude(class_and_section__stream__isnull=True)
                        .exclude(class_and_section__stream__exact="")
                        .values("class_and_section__stream")
                        .annotate(n=Count("id"))
                    ):
                        key = _norm_stream_code(row.get("class_and_section__stream"))
                        if key:
                            stream_counts[key] = int(row.get("n") or 0)
                except Exception:
                    stream_counts = {}

            rows = []
            seen = set()
            for code, cap in cap_map.items():
                enrolled = int(stream_counts.get(code, 0))
                rows.append(
                    {
                        "code": code,
                        "label": {"PCM": "PCM", "CBM": "CB", "COMM": "MCOM", "HME": "HUM", "HMB": "HM"}.get(code, code),
                        "enrolled": enrolled,
                        "capacity": int(cap),
                        "remaining": max(0, int(cap) - enrolled) if cap else 0,
                    }
                )
                seen.add(code)

            # Include any other streams present in data (capacity unknown -> 0)
            for code, enrolled in sorted(stream_counts.items(), key=lambda x: x[0]):
                if code in seen:
                    continue
                rows.append(
                    {
                        "code": code,
                        "label": code,
                        "enrolled": int(enrolled),
                        "capacity": 0,
                        "remaining": 0,
                    }
                )

            ctx["ttv2_streams_capacity_is_dummy"] = False
            ctx["ttv2_streams_capacity"] = rows

            # Rich UI payload (KPI cards, charts, full table) for Template v2.
            # Capacity fields on Institute are treated as per-class capacity for 11th & 12th classes.
            classes = ["11th class", "12th class"]
            class_stream_counts = {}
            if hasattr(stu_qs, "values") and hasattr(stu_qs, "exclude"):
                try:
                    for r in (
                        stu_qs.exclude(class_and_section__stream__isnull=True)
                        .exclude(class_and_section__stream__exact="")
                        .exclude(class_and_section__class_and_section__isnull=True)
                        .exclude(class_and_section__class_and_section__exact="")
                        .values("class_and_section__class_and_section", "class_and_section__stream")
                        .annotate(n=Count("id"))
                    ):
                        cls_raw = (r.get("class_and_section__class_and_section") or "").strip().lower()
                        if "11" in cls_raw:
                            cls_key = "11th class"
                        elif "12" in cls_raw:
                            cls_key = "12th class"
                        else:
                            continue
                        sc = _norm_stream_code(r.get("class_and_section__stream"))
                        if not sc:
                            continue
                        class_stream_counts[(cls_key, sc)] = int(r.get("n") or 0)
                except Exception:
                    class_stream_counts = {}

            streams_meta = [
                {"code": "PCM", "label": "PCM"},
                {"code": "CBM", "label": "CB"},
                {"code": "COMM", "label": "MCOM"},
                {"code": "HME", "label": "HUM"},
                {"code": "HMB", "label": "HM"},
            ]

            class_rows = []
            total_filled = 0
            cap_per_class = sum(int(v or 0) for v in cap_map.values())
            for idx, cls in enumerate(classes, start=1):
                filled = 0
                per_stream = {}
                for sm in streams_meta:
                    code = sm["code"]
                    n = int(class_stream_counts.get((cls, code), 0))
                    per_stream[code] = {"cap": int(cap_map.get(code, 0) or 0), "filled": n}
                    filled += n
                total = int(cap_per_class)
                available = max(0, total - filled)
                pct = (float(filled) / float(total) * 100.0) if total else 0.0
                total_filled += filled
                class_rows.append(
                    {
                        "idx": idx,
                        "class_label": cls,
                        "streams": per_stream,
                        "total": total,
                        "filled": int(filled),
                        "available": int(available),
                        "fill_pct": round(pct, 1),
                    }
                )

            total_capacity = int(cap_per_class) * len(classes)
            open_seats = max(0, total_capacity - total_filled)
            fill_rate = (float(total_filled) / float(total_capacity) * 100.0) if total_capacity else 0.0

            occ_by_stream = []
            for sm in streams_meta:
                code = sm["code"]
                cap_total = int(cap_map.get(code, 0) or 0) * len(classes)
                filled_stream = sum(int(class_stream_counts.get((cls, code), 0)) for cls in classes)
                occ_pct = (float(filled_stream) / float(cap_total) * 100.0) if cap_total else 0.0
                occ_by_stream.append(
                    {"code": code, "label": sm["label"], "filled": int(filled_stream), "capacity": int(cap_total), "pct": round(occ_pct, 2)}
                )

            ctx["ttv2_streams_capacity_payload"] = {
                "kpis": {
                    "total_capacity": total_capacity,
                    "seats_filled": int(total_filled),
                    "open_seats": int(open_seats),
                    "fill_rate_pct": round(fill_rate, 2),
                    "streams_count": len(streams_meta),
                    "classes_count": len(classes),
                    "capacity_per_stream_default": int(max(cap_map.values()) if cap_map else 0),
                },
                "streams_meta": streams_meta,
                "classes": classes,
                "cap_map": cap_map,
                "class_rows": class_rows,
                "occupancy_by_stream": occ_by_stream,
            }
            _ttv2_dbg(
                {
                    "hypothesisId": "H2",
                    "location": "institute/views.py:get_context:streams_capacity",
                    "message": "Built ttv2_streams_capacity",
                    "data": {
                        "rows_len": len(rows),
                        "first_rows": rows[:3],
                        "has_inst": bool(inst),
                        "stu_count": (stu_qs.count() if hasattr(stu_qs, "count") else None),
                    },
                }
            )
        return ctx

    def get(self, request, *args, **kwargs):
        download=request.GET.get("download")

        # Students page: Psychometric assessment PDF download (MI/EI attempts in current scope; ignores search filters)
        if (request.GET.get("psychometric_pdf") or "").strip() == "1":
            slug = kwargs.get("slug")
            institute = get_object_or_404(Institute, slug=slug)
            stu_manage = (
                get_students_by_role(request.user, institute=institute)
                .select_related("student", "class_and_section", "institute")
                .prefetch_related("counselors")
            )
            uids = [int(x) for x in stu_manage.values_list("student_id", flat=True) if x]
            try:
                from core.models import MIAssessmentResult, EQAssessmentResult
                mi_latest = {}
                for r in MIAssessmentResult.objects.filter(user_id__in=uids).order_by("user_id", "-updated_at"):
                    if r.user_id not in mi_latest:
                        mi_latest[r.user_id] = r
                eq_latest = {}
                for r in EQAssessmentResult.objects.filter(user_id__in=uids).order_by("user_id", "-updated_at"):
                    if r.user_id not in eq_latest:
                        eq_latest[r.user_id] = r
                keep = []
                for sm in stu_manage:
                    uid = getattr(sm, "student_id", None)
                    if uid and (uid in mi_latest or uid in eq_latest):
                        keep.append(sm)

                # Build a simple 1-page-per-student PDF (page breaks)
                def esc(s):
                    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                pages = []
                for sm in keep:
                    u = sm.student
                    cas = sm.class_and_section
                    uid = sm.student_id
                    mi = mi_latest.get(uid)
                    eq = eq_latest.get(uid)
                    mi_line = "MI: —"
                    if mi:
                        mi_line = "MI: %s (%s)" % (esc(mi.style_name), esc(mi.primary_style))
                    eq_line = "EI: —"
                    if eq:
                        eq_line = "EI: %.1f (%s)" % (float(eq.ei_total or 0), esc(expand_eq_band_percentile(eq.band_label)))
                    pages.append(
                        """
                        <div class="page">
                          <div class="h1">%s</div>
                          <div class="meta">%s%s</div>
                          <div class="meta">%s</div>
                          <div class="box">
                            <div class="row">%s</div>
                            <div class="row">%s</div>
                          </div>
                          <div class="foot">Generated for %s</div>
                        </div>
                        """ % (
                            esc(getattr(u, "name", "") or "-"),
                            esc(getattr(cas, "class_and_section", "") or "-"),
                            (" · " + esc(getattr(cas, "stream", "") or "")) if cas and getattr(cas, "stream", None) else "",
                            esc(getattr(u, "email", "") or ""),
                            mi_line,
                            eq_line,
                            esc(getattr(institute, "name", "") or "School"),
                        )
                    )

                full_html = """<!doctype html>
                <html><head><meta charset="utf-8">
                <title>Psychometric assessment PDF</title>
                <style>
                  @page { size: A4; margin: 18mm; }
                  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color:#111827; }
                  .page { page-break-after: always; }
                  .h1 { font-size: 18px; font-weight: 800; margin: 0 0 4px; }
                  .meta { font-size: 11px; color:#4b5563; margin: 0 0 2px; }
                  .box { margin-top: 14px; padding: 12px; border: 1px solid #e5e7eb; border-radius: 12px; }
                  .row { font-size: 12px; margin: 0 0 6px; }
                  .foot { margin-top: 18px; font-size: 10px; color:#6b7280; }
                </style></head><body>%s</body></html>""" % ("\n".join(pages) if pages else "<p>No students with MI/EI attempts found.</p>")
                try:
                    import weasyprint
                    pdf_bytes = weasyprint.HTML(string=full_html, base_url=request.build_absolute_uri("/")).write_pdf()
                except Exception as e:
                    return HttpResponse("PDF generation failed: %s" % str(e), status=500)
                resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                resp["Content-Disposition"] = 'attachment; filename="Psychometric-assessment.pdf"'
                return resp
            except Exception as e:
                return HttpResponse("PDF generation failed: %s" % str(e), status=500)
        
        # Check if this is an AJAX request for student table - process only student data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data_type = request.GET.get('data_type', '')
            if data_type == "sessions":
                # Weekly session report widget JSON (chart/table). Scope: this institute.
                try:
                    slug = kwargs.get("slug")
                    institute = get_object_or_404(Institute, slug=slug)
                except Exception:
                    return JsonResponse({"sessions_data": []})

                group = (request.GET.get("group") or "").strip().lower()
                wk = _ttv2_week_start_from_request(request) or timezone.localdate()
                week_start = wk - timedelta(days=wk.weekday())
                week_end = week_start + timedelta(days=6)
                days = [week_start + timedelta(days=i) for i in range(7)]
                day_keys = [d.isoformat() for d in days]

                # Student scope for the institute
                sm_qs = StudentManagement.objects.filter(institute=institute).select_related("student")
                sm_ids = list(sm_qs.values_list("id", flat=True))

                from django.db.models.functions import Coalesce, TruncDate
                from django.db import models as _models
                from django.db.models import Count

                base_qs = (
                    FollowUpStatus.objects.filter(
                        _followup_for_institute_counselors_q(institute),
                        student_id__in=sm_ids,
                    )
                    .annotate(
                        _sess_day=Coalesce(
                            "last_follow_up_date",
                            TruncDate("created"),
                            output_field=_models.DateField(),
                        )
                    )
                    .filter(_sess_day__gte=week_start, _sess_day__lte=week_end)
                )

                if group == "student":
                    # Top N students (by sessions in selected week)
                    top_n = 8
                    try:
                        top_ids = list(
                            base_qs.values("student_id")
                            .annotate(n=Count("id"))
                            .order_by("-n")[:top_n]
                        )
                        top_ids = [int(r["student_id"]) for r in top_ids if r.get("student_id")]
                    except Exception:
                        top_ids = []

                    name_map = {}
                    try:
                        for sm in sm_qs.filter(id__in=top_ids):
                            u = getattr(sm, "student", None)
                            name_map[int(sm.id)] = (getattr(u, "name", "") or "").strip() or f"Student {sm.id}"
                    except Exception:
                        for sid in top_ids:
                            name_map[int(sid)] = f"Student {sid}"

                    counts = {}
                    try:
                        for r in (
                            base_qs.filter(student_id__in=top_ids)
                            .values("student_id", "_sess_day")
                            .annotate(n=Count("id"))
                        ):
                            sid = int(r.get("student_id") or 0)
                            d = r.get("_sess_day")
                            if not sid or not d:
                                continue
                            counts[(sid, d.isoformat())] = int(r.get("n") or 0)
                    except Exception:
                        counts = {}

                    out = []
                    for sid in top_ids:
                        series = [{"day": dk, "session_count": int(counts.get((int(sid), dk), 0))} for dk in day_keys]
                        out.append({"series_id": int(sid), "series_name": name_map.get(int(sid)) or f"Student {sid}", "sessions": series})
                    return JsonResponse({"sessions_data": out})

                # Default: counselor-wise series (top N counselors by sessions this week)
                top_n = 8
                try:
                    top_c = list(
                        base_qs.values("counselor_id")
                        .annotate(n=Count("id"))
                        .order_by("-n")[:top_n]
                    )
                    top_cids = [int(r["counselor_id"]) for r in top_c if r.get("counselor_id")]
                except Exception:
                    top_cids = []

                name_map = {}
                try:
                    for c in Counselor.objects.filter(id__in=top_cids).only("id", "counselor_name"):
                        name_map[int(c.id)] = (getattr(c, "counselor_name", "") or "").strip() or f"Counselor {c.id}"
                except Exception:
                    for cid in top_cids:
                        name_map[int(cid)] = f"Counselor {cid}"

                counts = {}
                try:
                    for r in (
                        base_qs.filter(counselor_id__in=top_cids)
                        .values("counselor_id", "_sess_day")
                        .annotate(n=Count("id"))
                    ):
                        cid = int(r.get("counselor_id") or 0)
                        d = r.get("_sess_day")
                        if not cid or not d:
                            continue
                        counts[(cid, d.isoformat())] = int(r.get("n") or 0)
                except Exception:
                    counts = {}

                out = []
                for cid in top_cids:
                    series = [{"day": dk, "session_count": int(counts.get((int(cid), dk), 0))} for dk in day_keys]
                    out.append({"counselor_id": int(cid), "counselor_name": name_map.get(int(cid)) or f"Counselor {cid}", "sessions": series})
                return JsonResponse({"sessions_data": out})

            if data_type == "session_history_student":
                slug = kwargs.get("slug")
                institute = get_object_or_404(Institute, slug=slug)
                return _ttv2_session_history_student_response(
                    request,
                    get_students_by_role(request.user, counselor=None, institute=institute),
                )
            if data_type == 'students':
                # Lightweight context for AJAX - only student table data
                ctx = self.get_student_table_context_ajax(request, *args, **kwargs)
                from institute.student_table_helpers import get_student_table_config, get_student_action_urls
                ctx['table_config'] = get_student_table_config('institute')
                ctx['action_urls'] = get_student_action_urls('institute')
                # Map total_students to students for template compatibility
                ctx['students'] = ctx.get('total_students')

                apply_student_table_display_enrichment(request, ctx)
                ctx['ttv2_students_role'] = 'institute'

                display = (request.GET.get("display") or "").strip().lower()
                if display == "cards":
                    return render(request, "template_v2/institute/pages/student_roster_cards.html", ctx)
                # default: list/table
                return render(request, "template20/shared/students_table.html", ctx)
            if data_type == 'students_analytics':
                slug = kwargs.get("slug")
                institute = get_object_or_404(Institute, slug=slug)
                stu_manage = get_students_by_role(request.user, institute=institute)
                return JsonResponse(
                    build_students_analytics_payload(
                        stu_manage, week_start=_ttv2_week_start_from_request(request)
                    )
                )

        # Full context for initial page load
        ctx=self.get_context(request, *args, **kwargs)
        if download=="Yes":
            data=ctx.get('stu')
            return self.get_filter_data(request,data)

        if (ctx.get("ttv2_page") or "").strip().lower() == "accounts":
            from institute.accounts_analytics import build_institute_accounts_ctx

            institute = ctx.get("institute")
            if institute:
                ctx["ttv2_accounts"] = build_institute_accounts_ctx(
                    institute, request.user, request
                )

        # v2 sessions-like pages: show counselor follow-ups for this institute.
        # - sessions: legacy table
        # - session_report: same rows, but with filters UI
        if (ctx.get("ttv2_page") or "").strip().lower() in ("sessions", "session_report"):
            try:
                from counselor.models import Counselor as _Counselor
                from django.db.models.functions import Coalesce, TruncDate
                from django.db import models as _models
                from django.utils import timezone as _tz
                from django.db.models import Count

                slug = kwargs.get("slug")
                institute = get_object_or_404(Institute, slug=slug) if slug else ctx.get("institute")

                # Filter controls (used by session_report template):
                # - from/to: date range on session day (COALESCE(last_follow_up_date, created))
                # - counselor: specific counselor id
                raw_from = (request.GET.get("from") or "").strip()
                raw_to = (request.GET.get("to") or "").strip()
                raw_coun = (request.GET.get("counselor") or "").strip()
                raw_mode = (request.GET.get("mode") or "").strip()
                raw_status = (request.GET.get("status") or "").strip()
                raw_class = (request.GET.get("class") or "").strip()
                date_from = None
                date_to = None
                try:
                    if raw_from:
                        date_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
                except Exception:
                    date_from = None
                try:
                    if raw_to:
                        date_to = datetime.strptime(raw_to, "%Y-%m-%d").date()
                except Exception:
                    date_to = None

                qs = FollowUpStatus.objects.filter(
                    _followup_for_institute_counselors_q(institute)
                ).select_related(
                    "counselor", "student", "student__student"
                )
                # Stable "session day" like v2 session report widgets.
                qs = qs.annotate(
                    _sess_day=Coalesce(
                        "last_follow_up_date",
                        TruncDate("created"),
                        output_field=_models.DateField(),
                    )
                )
                if date_from:
                    qs = qs.filter(_sess_day__gte=date_from)
                if date_to:
                    qs = qs.filter(_sess_day__lte=date_to)
                if raw_coun:
                    try:
                        qs = qs.filter(counselor_id=int(raw_coun))
                    except Exception:
                        pass
                if raw_mode:
                    qs = qs.filter(mode_of_follow_up__iexact=raw_mode)
                if raw_status:
                    qs = qs.filter(follow_up_status__iexact=raw_status)
                if raw_class:
                    try:
                        qs = qs.filter(student__class_and_section_id=int(raw_class))
                    except Exception:
                        pass

                qs = qs.order_by("-_sess_day", "-created")

                # Sessions page KPI counts (computed on full filtered queryset)
                try:
                    total_sessions = int(qs.count())
                    unique_students = int(qs.values("student_id").distinct().count())
                    completed_sessions = int(qs.filter(follow_up_status__iexact="completed").count())
                    pending_sessions = int(qs.filter(follow_up_status__iexact="pending").count())
                    followup_sessions = int(qs.filter(follow_up_status__iexact="follow-up").count())
                    avg_per_student = round((float(total_sessions) / float(unique_students)), 2) if unique_students else 0
                    top_students = list(
                        qs.values("student_id")
                        .annotate(c=Count("id"))
                        .order_by("-c")[:5]
                    )
                    top_map = {x["student_id"]: int(x["c"]) for x in top_students if x.get("student_id")}
                    ctx["ttv2_sessions_kpis_simple"] = {
                        "total_sessions": total_sessions,
                        "unique_students": unique_students,
                        "avg_per_student": avg_per_student,
                        "completed": completed_sessions,
                        "pending": pending_sessions,
                        "follow_up": followup_sessions,
                        "top_map": top_map,
                    }
                except Exception:
                    ctx["ttv2_sessions_kpis_simple"] = {
                        "total_sessions": 0,
                        "unique_students": 0,
                        "avg_per_student": 0,
                        "completed": 0,
                        "pending": 0,
                        "follow_up": 0,
                        "top_map": {},
                    }

                # Keep only recent rows for the legacy table.
                qs = qs[:200]
                rows = []
                for fu in qs:
                    sm = getattr(fu, "student", None)
                    u = getattr(sm, "student", None) if sm else None
                    scount = None
                    try:
                        scount = (ctx.get("ttv2_sessions_kpis_simple") or {}).get("top_map", {}).get(getattr(fu, "student_id", None))
                    except Exception:
                        scount = None
                    rows.append(
                        {
                            "when": getattr(fu, "last_follow_up_date", None).strftime("%Y-%m-%d")
                            if getattr(fu, "last_follow_up_date", None)
                            else (getattr(fu, "created", None).strftime("%Y-%m-%d") if getattr(fu, "created", None) else "-"),
                            "counselor": getattr(getattr(fu, "counselor", None), "counselor_name", None) or "-",
                            "student": getattr(u, "name", None)
                            or getattr(u, "email", None)
                            or (getattr(sm, "student_name", None) if sm else None)
                            or "-",
                            "mode": getattr(fu, "mode_of_follow_up", None) or "-",
                            "status": getattr(fu, "follow_up_status", None) or "-",
                            "next": getattr(fu, "next_follow_up_date", None).strftime("%Y-%m-%d")
                            if getattr(fu, "next_follow_up_date", None)
                            else "-",
                            "student_sessions": scount,
                        }
                    )
                ctx["ttv2_sessions_is_dummy"] = False
                ctx["ttv2_sessions"] = rows
                ctx["ttv2_sessions_filters"] = {
                    "from": raw_from,
                    "to": raw_to,
                    "counselor": raw_coun,
                    "mode": raw_mode,
                    "status": raw_status,
                    "class": raw_class,
                }

                # For session_report filters: counselor dropdown options (all institute counselors).
                try:
                    ctx["ttv2_session_report_counselors"] = list(
                        _Counselor.qs_for_institute(institute)
                        .order_by("counselor_name")
                        .values("id", name=_models.F("counselor_name"))
                    )
                except Exception:
                    try:
                        ctx["ttv2_session_report_counselors"] = [
                            {"id": x.id, "name": x.counselor_name}
                            for x in _Counselor.qs_for_institute(institute).order_by("counselor_name")
                        ]
                    except Exception:
                        ctx["ttv2_session_report_counselors"] = []
            except Exception:
                ctx["ttv2_sessions_is_dummy"] = False
                ctx["ttv2_sessions"] = []
                ctx["ttv2_session_report_counselors"] = []
            # Aliases for session_report template.
            try:
                if (ctx.get("ttv2_page") or "").strip().lower() == "session_report":
                    ctx["ttv2_session_report_rows"] = ctx.get("ttv2_sessions") or []
                    ctx["ttv2_session_report_is_dummy"] = bool(ctx.get("ttv2_sessions_is_dummy"))
            except Exception:
                pass

        # v2 institute session report (rich): KPIs + MTD + student cards.
        if (ctx.get("ttv2_page") or "").strip().lower() == "session_report":
            try:
                import calendar
                from django.db.models.functions import Coalesce, TruncDate
                from django.db import models as _models
                from django.db.models import Count, Q

                institute = ctx.get("institute")
                if not institute:
                    slug = kwargs.get("slug")
                    institute = get_object_or_404(Institute, slug=slug) if slug else None
                if not institute:
                    raise Exception("no institute")

                today = timezone.localdate()
                week_start = _ttv2_week_start_from_request(request) or (today - timedelta(days=today.weekday()))
                week_end = week_start + timedelta(days=6)

                # Institute students scope (StudentManagement ids)
                sm_qs = StudentManagement.objects.filter(institute=institute).select_related("student", "class_and_section")
                sm_ids = list(sm_qs.values_list("id", flat=True))
                total_students = int(len(sm_ids))

                fu_base = (
                    FollowUpStatus.objects.filter(
                        _followup_for_institute_counselors_q(institute),
                        student_id__in=sm_ids,
                    )
                    .annotate(
                        _sess_day=Coalesce(
                            "last_follow_up_date",
                            TruncDate("created"),
                            output_field=_models.DateField(),
                        )
                    )
                )

                fu_week = fu_base.filter(_sess_day__gte=week_start, _sess_day__lte=week_end)
                sessions_week = int(fu_week.count())
                completed_week = int(fu_week.filter(follow_up_status="completed").count())
                unique_students_week = int(fu_week.values("student_id").distinct().count())
                completion_rate = int(round((100.0 * completed_week / sessions_week), 0)) if sessions_week else 0

                upcoming = 0
                try:
                    upcoming = int(
                        FollowUpStatus.objects.filter(
                            _followup_for_institute_counselors_q(institute),
                            student_id__in=sm_ids,
                            next_follow_up_date__isnull=False,
                            next_follow_up_date__gte=today,
                        )
                        .values("student_id")
                        .distinct()
                        .count()
                    )
                except Exception:
                    upcoming = 0

                ctx["ttv2_sessions_kpis"] = {
                    "sessions_week": sessions_week,
                    "unique_students_week": unique_students_week,
                    "completed_week": completed_week,
                    "completion_rate_week": completion_rate,
                    "upcoming_followups": upcoming,
                }

                # Month-to-date table: month determined by selected week_start
                month_ref = week_start or today
                month_first = month_ref.replace(day=1)
                month_last = month_ref.replace(day=calendar.monthrange(month_ref.year, month_ref.month)[1])
                month_end = min(today, month_last) if (month_ref.year == today.year and month_ref.month == today.month) else month_last

                def _month_week_ranges(start_d, end_d):
                    out = []
                    cur = start_d
                    idx = 1
                    while cur <= end_d:
                        nxt = min(end_d, cur + timedelta(days=6))
                        out.append((idx, cur, nxt))
                        idx += 1
                        cur = nxt + timedelta(days=1)
                    return out

                month_weeks = _month_week_ranges(month_first, month_end)
                fu_month = fu_base.filter(_sess_day__gte=month_first, _sess_day__lte=month_end)

                # Proxies from global analytics KPI (already computed earlier in ctx["ttv2_analytics"])
                try:
                    clarity_gap = float((ctx.get("ttv2_analytics") or {}).get("kpi", {}).get("clarity_gap", 0) or 0)
                except Exception:
                    clarity_gap = 0.0
                try:
                    test_completion = int((ctx.get("ttv2_analytics") or {}).get("kpi", {}).get("psych_pct", 0) or 0)
                except Exception:
                    test_completion = 0

                mtd_rows = []
                for widx, ws, we in month_weeks:
                    try:
                        qs_w = fu_month.filter(_sess_day__gte=ws, _sess_day__lte=we)
                        sessions_cnt = int(qs_w.count())
                        students_reached = int(qs_w.values("student_id").distinct().count())
                    except Exception:
                        sessions_cnt = 0
                        students_reached = 0
                    mtd_rows.append(
                        {
                            "week": f"Week {widx}",
                            "period": f"{ws:%b} {ws.day}–{we.day}",
                            "week_start": ws.isoformat(),
                            "sessions": sessions_cnt,
                            "students_reached": f"{students_reached}/{total_students}" if total_students else f"{students_reached}/0",
                            "test_completion": test_completion,
                            "clarity_gap": clarity_gap,
                            "paths": 0,
                            "milestone": "—",
                            "rating": 0,
                            "is_current": bool(ws <= week_start <= we),
                        }
                    )
                ctx["ttv2_sessions_month_label"] = f"{month_first:%B} {month_first.year}"
                ctx["ttv2_sessions_mtd_rows"] = mtd_rows
                ctx["ttv2_sessions_weekly_note"] = "—"
                ctx["ttv2_sessions_next_actions"] = []

                # Student cards (top by week sessions), include counselor info in preview/history.
                try:
                    totals = {
                        int(r["student_id"]): {"total": int(r["n"] or 0), "done": int(r["done"] or 0)}
                        for r in fu_base.values("student_id").annotate(
                            n=Count("id"),
                            done=Count("id", filter=Q(follow_up_status="completed")),
                        )
                    }
                    week_map = {
                        int(r["student_id"]): {"week_total": int(r["n"] or 0), "week_done": int(r["done"] or 0)}
                        for r in fu_week.values("student_id").annotate(
                            n=Count("id"),
                            done=Count("id", filter=Q(follow_up_status="completed")),
                        )
                    }
                except Exception:
                    totals, week_map = {}, {}

                # recent follow-ups: 2 per student for preview
                previews = {}
                try:
                    recent_fu = list(
                        fu_base.select_related("counselor")
                        .order_by("-_sess_day", "-created")[:400]
                    )
                    def _fmt(d):
                        try:
                            return d.strftime("%a %d %b %Y") if d else ""
                        except Exception:
                            return ""
                    for fu in recent_fu:
                        sid = int(getattr(fu, "student_id", 0) or 0)
                        if not sid:
                            continue
                        arr = previews.setdefault(sid, [])
                        if len(arr) >= 2:
                            continue
                        arr.append(
                            {
                                "when": _fmt(getattr(fu, "_sess_day", None)) or "—",
                                "counselor": (getattr(getattr(fu, "counselor", None), "counselor_name", None) or ""),
                                "mode": (getattr(fu, "mode_of_follow_up", None) or "—"),
                                "status": (getattr(fu, "follow_up_status", None) or "—"),
                                "next": _fmt(getattr(fu, "next_follow_up_date", None)) or "",
                                "message": (getattr(fu, "message", None) or "").strip(),
                            }
                        )
                except Exception:
                    previews = {}

                # pick top 12 students by week_total
                top_ids = sorted(list(week_map.keys()), key=lambda x: int(week_map.get(x, {}).get("week_total", 0)), reverse=True)[:12]
                if not top_ids:
                    # fallback to any students with totals
                    top_ids = sorted(list(totals.keys()), key=lambda x: int(totals.get(x, {}).get("total", 0)), reverse=True)[:12]

                sm_by_id = {int(sm.id): sm for sm in sm_qs.filter(id__in=top_ids)}
                out_students = []
                for sm_id in top_ids:
                    sm = sm_by_id.get(int(sm_id))
                    if not sm:
                        continue
                    u = getattr(sm, "student", None)
                    name = (getattr(u, "name", "") or "").strip() or f"Student {sm_id}"
                    cas = getattr(sm, "class_and_section", None)
                    meta = ""
                    try:
                        cls = (getattr(cas, "class_and_section", "") or "").strip()
                        st = (getattr(cas, "stream", "") or "").strip()
                        meta = " · ".join([x for x in [cls, st] if x])
                    except Exception:
                        meta = ""
                    t = totals.get(int(sm_id), {})
                    w = week_map.get(int(sm_id), {})
                    out_students.append(
                        {
                            "student_id": int(sm_id),
                            "student": name,
                            "meta": meta,
                            "total": int(t.get("total", 0) or 0),
                            "done": int(t.get("done", 0) or 0),
                            "week_total": int(w.get("week_total", 0) or 0),
                            "week_done": int(w.get("week_done", 0) or 0),
                            "preview": previews.get(int(sm_id), []),
                        }
                    )
                ctx["ttv2_sessions_students"] = out_students
            except Exception:
                ctx.setdefault("ttv2_sessions_kpis", {})
                ctx.setdefault("ttv2_sessions_mtd_rows", [])
                ctx.setdefault("ttv2_sessions_students", [])

        # v2 counselors page: DB-accurate KPIs + dynamic leaderboard from FollowUpStatus.
        if (ctx.get("ttv2_page") or "").strip().lower() == "counselors":
            try:
                import calendar
                from django.db import models as _models
                from django.db.models import Count, Q
                from django.db.models.functions import Coalesce, TruncDate
                from django.utils import timezone as _tz
                from app.models import Results

                institute = ctx.get("institute")
                if not institute:
                    slug = kwargs.get("slug")
                    institute = get_object_or_404(Institute, slug=slug) if slug else None
                if not institute:
                    raise Exception("no institute")

                counselor_ids = list(
                    Counselor.qs_for_institute(institute).values_list("id", flat=True)
                )
                sm_ids = list(
                    StudentManagement.objects.filter(institute=institute).values_list("id", flat=True)
                )
                student_user_ids = list(
                    StudentManagement.objects.filter(institute=institute).values_list("student_id", flat=True)
                )

                fu = (
                    FollowUpStatus.objects.filter(
                        counselor_id__in=counselor_ids,
                        student_id__in=sm_ids,
                    )
                    .annotate(
                        _sess_day=Coalesce(
                            "last_follow_up_date",
                            TruncDate("created"),
                            output_field=_models.DateField(),
                        )
                    )
                )

                counselors_n = int(len(counselor_ids))
                sessions_logged = int(fu.count())
                students_counseled = int(
                    fu.filter(follow_up_status__iexact="completed").values("student_id").distinct().count()
                )
                total_institute_students = int(len(sm_ids))
                students_counselled_pct = (
                    int(round((100.0 * float(students_counseled) / float(total_institute_students)), 0))
                    if total_institute_students
                    else 0
                )
                followups_sent = int(sessions_logged)
                avg_sessions = round((float(sessions_logged) / float(counselors_n)), 1) if counselors_n else 0
                ctx["ttv2_counselors_kpis"] = {
                    "counselors": counselors_n,
                    "sessions_logged": sessions_logged,
                    "students_counseled": students_counseled,
                    "students_counselled_total": total_institute_students,
                    "students_counselled_pct": students_counselled_pct,
                    "followups_sent": followups_sent,
                    "avg_sessions": avg_sessions,
                }

                today = _tz.localdate()
                week_start = today - timedelta(days=today.weekday())
                week_end = week_start + timedelta(days=6)
                month_first = today.replace(day=1)
                month_last = today.replace(day=calendar.monthrange(today.year, today.month)[1])

                # Weekly activity heatmap: sessions + tests (test1/2/3 Results) in current week.
                try:
                    sess_by_day = {
                        r["_sess_day"]: int(r["n"] or 0)
                        for r in fu.filter(_sess_day__gte=week_start, _sess_day__lte=week_end)
                        .values("_sess_day")
                        .annotate(n=Count("id"))
                    }
                except Exception:
                    sess_by_day = {}

                try:
                    tests_qs = Results.objects.filter(
                        user_id__in=student_user_ids,
                        test_paper__in=["test1", "test2", "test3"],
                        modified__date__gte=week_start,
                        modified__date__lte=week_end,
                    )
                    test_by_day = {
                        r["d"]: int(r["n"] or 0)
                        for r in tests_qs.annotate(d=TruncDate("modified"))
                        .values("d")
                        .annotate(n=Count("id"))
                    }
                except Exception:
                    test_by_day = {}

                week_days = []
                max_activity = 0
                for i in range(7):
                    d = week_start + timedelta(days=i)
                    sess_n = int(sess_by_day.get(d, 0) or 0)
                    test_n = int(test_by_day.get(d, 0) or 0)
                    total = sess_n + test_n
                    max_activity = max(max_activity, total)
                    week_days.append(
                        {
                            "date": d.isoformat(),
                            "label": d.strftime("%a"),
                            "sessions": sess_n,
                            "tests": test_n,
                            "total": total,
                        }
                    )
                # Add intensity 0..1 for UI
                for r in week_days:
                    r["intensity"] = (float(r["total"]) / float(max_activity)) if max_activity else 0.0
                ctx["ttv2_counselors_week_activity"] = {
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "days": week_days,
                }

                base = list(
                    fu.values("counselor_id", "counselor__counselor_name")
                    .annotate(
                        sessions=Count("id"),
                        this_mo=Count("id", filter=Q(_sess_day__gte=month_first, _sess_day__lte=month_last)),
                        completed=Count("id", filter=Q(follow_up_status__iexact="completed")),
                        students=Count("student_id", distinct=True),
                        with_next=Count("id", filter=Q(next_follow_up_date__isnull=False)),
                        overdue=Count("id", filter=Q(next_follow_up_date__isnull=False, next_follow_up_date__lt=today)),
                    )
                    .order_by("-sessions", "counselor__counselor_name")
                )

                max_sessions = 0
                for r in base:
                    max_sessions = max(max_sessions, int(r.get("sessions") or 0))

                leaderboard = []
                for idx, r in enumerate(base, start=1):
                    sessions = int(r.get("sessions") or 0)
                    students = int(r.get("students") or 0)
                    completed = int(r.get("completed") or 0)
                    with_next = int(r.get("with_next") or 0)
                    overdue = int(r.get("overdue") or 0)
                    completion_pct = int(round((100.0 * completed / sessions), 0)) if sessions else 0
                    followup_pct = int(round((100.0 * with_next / sessions), 0)) if sessions else 0
                    on_time_pct = int(round((100.0 * (with_next - overdue) / with_next), 0)) if with_next else 0
                    load_pct = int(round((100.0 * sessions / max_sessions), 0)) if max_sessions else 0
                    # Impact score: weighted blend of volume + completion + coverage.
                    impact = int(
                        min(
                            99,
                            round(
                                (sessions / max_sessions * 60.0 if max_sessions else 0.0)
                                + (completion_pct * 0.25)
                                + (min(100, students) * 0.15),
                                0,
                            ),
                        )
                    )
                    leaderboard.append(
                        {
                            "rank": idx,
                            "counselor_id": r.get("counselor_id"),
                            "counselor": r.get("counselor__counselor_name") or "Counselor",
                            "impact": impact,
                            "sessions": sessions,
                            "this_mo": int(r.get("this_mo") or 0),
                            "csat": None,
                            "on_time": on_time_pct,
                            "follow_up": followup_pct,
                            "avg_min": None,
                            "load_pct": load_pct,
                        }
                    )

                ctx["ttv2_counselors_leaderboard"] = leaderboard

                # --- Screen 1: roster table + monthly session buckets + coverage (Chart.js payload)
                # --- Screen 2: weekly performance scorecard (DB-backed where models exist)
                from datetime import date as _date
                from django.db.models import Prefetch

                from core.ttv2_dashboard_analytics import _psych_and_risk

                counselors_pref = (
                    Counselor.qs_for_institute(institute)
                    .order_by("counselor_name")
                    .prefetch_related(
                        Prefetch(
                            "students",
                            queryset=StudentManagement.objects.filter(institute=institute),
                        )
                    )
                )

                def _avg_minutes_between_followups(cfu_qs):
                    """
                    Mean minutes between consecutive FollowUpStatus.created timestamps for one counselor.
                    Used when true 'session duration' is not stored on the model.
                    """
                    times = list(cfu_qs.order_by("created").values_list("created", flat=True))
                    if len(times) < 2:
                        return None
                    deltas = []
                    for i in range(1, len(times)):
                        try:
                            dt = (times[i] - times[i - 1]).total_seconds() / 60.0
                        except Exception:
                            continue
                        if 1.0 <= dt <= 60.0 * 24.0 * 7.0:
                            deltas.append(dt)
                    if not deltas:
                        return None
                    return int(round(sum(deltas) / float(len(deltas))))

                roster = []
                for c in counselors_pref:
                    assigned_ids = [int(x) for x in c.students.values_list("id", flat=True)]
                    assigned_n = len(assigned_ids)
                    cfu = fu.filter(counselor_id=c.id)
                    sessions_total = int(cfu.count())
                    if assigned_n:
                        stu_any = int(
                            cfu.filter(student_id__in=assigned_ids)
                            .values("student_id")
                            .distinct()
                            .count()
                        )
                        stu_done = int(
                            cfu.filter(student_id__in=assigned_ids, follow_up_status__iexact="completed")
                            .values("student_id")
                            .distinct()
                            .count()
                        )
                        cov_den = assigned_n
                    else:
                        stu_any = int(cfu.exclude(student_id__isnull=True).values("student_id").distinct().count())
                        stu_done = int(
                            cfu.filter(follow_up_status__iexact="completed")
                            .exclude(student_id__isnull=True)
                            .values("student_id")
                            .distinct()
                            .count()
                        )
                        cov_den = max(stu_any, 1)
                    joined_s = ""
                    try:
                        cr = getattr(c, "created", None)
                        if cr:
                            joined_s = cr.strftime("%d/%m/%Y")
                    except Exception:
                        joined_s = ""
                    nm = (getattr(c, "counselor_name", None) or "").strip() or f"Counselor {c.id}"
                    em = (getattr(c, "counselor_email", None) or "").strip() or ""
                    gap_min = _avg_minutes_between_followups(cfu)
                    avg_lbl = f"{gap_min} min" if gap_min is not None else "—"
                    roster.append(
                        {
                            "id": int(c.id),
                            "label": f"{nm}" + (f" · {em}" if em else ""),
                            "email": em or "—",
                            "joined": joined_s or "—",
                            "sessions_total": sessions_total,
                            "students_covered_num": stu_any,
                            "students_covered_den": cov_den,
                            "students_counselled": stu_done,
                            "followups": sessions_total,
                            "avg_session_label": avg_lbl,
                            "status": "Active",
                        }
                    )
                roster.sort(key=lambda r: (-int(r.get("sessions_total") or 0), (r.get("email") or "")))
                for i, row in enumerate(roster, start=1):
                    row["row_num"] = i
                ctx["ttv2_counselors_roster"] = roster

                raw_focus = (request.GET.get("focus_counselor") or "").strip()
                focus_cid = None
                if raw_focus.isdigit():
                    cand = int(raw_focus)
                    if cand in counselor_ids:
                        focus_cid = cand
                if focus_cid is None and roster:
                    focus_cid = int(roster[0]["id"])
                ctx["ttv2_counselors_focus_id"] = focus_cid

                focus_name = "Counselor"
                if focus_cid:
                    try:
                        focus_name = (
                            Counselor.objects.filter(id=focus_cid).values_list("counselor_name", flat=True).first()
                            or focus_name
                        )
                    except Exception:
                        pass

                def _counselors_chart_range_bounds(req, today_d, _date_cls):
                    from django.utils.dateparse import parse_date as _parse_date

                    rk = (req.GET.get("counselors_range") or "30d").strip().lower()
                    if rk not in ("today", "week", "30d", "year", "custom"):
                        rk = "30d"
                    lab = {
                        "today": "Today",
                        "week": "Last 7 days",
                        "30d": "Last 30 days",
                        "year": "Last 365 days",
                        "custom": "Custom range",
                    }.get(rk, "Last 30 days")
                    if rk == "today":
                        return today_d, today_d, rk, lab
                    if rk == "week":
                        return today_d - timedelta(days=6), today_d, rk, lab
                    if rk == "30d":
                        return today_d - timedelta(days=29), today_d, rk, lab
                    if rk == "year":
                        return today_d - timedelta(days=364), today_d, rk, lab
                    fs = _parse_date((req.GET.get("counselors_from") or "").strip())
                    te = _parse_date((req.GET.get("counselors_to") or "").strip())
                    if fs and te:
                        if te < fs:
                            fs, te = te, fs
                        if (te - fs).days > 730:
                            te = fs + timedelta(days=730)
                        return fs, te, rk, f"{fs:%d %b %Y} – {te:%d %b %Y}"
                    return today_d - timedelta(days=29), today_d, "30d", lab.get("30d", "Last 30 days")

                def _counselors_line_buckets(fu_qs, start_d, end_d):
                    labels, vals = [], []
                    if start_d > end_d:
                        return labels, vals
                    num_days = (end_d - start_d).days + 1
                    if num_days < 1:
                        return labels, vals
                    if num_days <= 31:
                        d = start_d
                        while d <= end_d:
                            labels.append(d.strftime("%d %b"))
                            vals.append(int(fu_qs.filter(_sess_day=d).count()))
                            d += timedelta(days=1)
                        return labels, vals
                    n_b = 12
                    step = max(1, (num_days + n_b - 1) // n_b)
                    d = start_d
                    while d <= end_d:
                        d2 = min(d + timedelta(days=step - 1), end_d)
                        if d == d2:
                            labels.append(d.strftime("%d %b %Y"))
                        else:
                            labels.append(f"{d:%d %b} – {d2:%d %b %Y}")
                        vals.append(int(fu_qs.filter(_sess_day__gte=d, _sess_day__lte=d2).count()))
                        d = d2 + timedelta(days=1)
                    return labels, vals

                range_start, range_end, range_key, range_label = _counselors_chart_range_bounds(
                    request, today, _date
                )
                ctx["ttv2_counselors_chart_controls"] = {
                    "range_key": range_key,
                    "range_label": range_label,
                    "from_iso": range_start.isoformat(),
                    "to_iso": range_end.isoformat(),
                }

                fu_focus = fu.filter(counselor_id=focus_cid) if focus_cid else fu.none()
                fu_focus_r = fu_focus.filter(_sess_day__gte=range_start, _sess_day__lte=range_end)
                line_labels, line_vals = _counselors_line_buckets(fu_focus_r, range_start, range_end)
                line_table = [{"period": lbl, "count": int(v)} for lbl, v in zip(line_labels, line_vals)]

                range_caption = f"{range_start:%d %b %Y} – {range_end:%d %b %Y}"
                charts_payload = {
                    "line": {
                        "title": "Session activity",
                        "subtitle": range_caption,
                        "labels": line_labels,
                        "values": line_vals,
                    },
                    "line_table": line_table,
                    "donut": {"counselled": 0, "not_counselled": 0},
                    "donut_table": [],
                    "focus_name": focus_name,
                    "range_key": range_key,
                    "range_label": range_label,
                    "range_from": range_start.isoformat(),
                    "range_to": range_end.isoformat(),
                }
                ctx["ttv2_counselors_charts"] = charts_payload

                if focus_cid:
                    try:
                        fc = Counselor.objects.filter(id=focus_cid).first()
                        if fc:
                            aset = list(
                                fc.students.filter(institute=institute).values_list("id", flat=True)
                            )
                            f_fu = fu.filter(counselor_id=focus_cid)
                            f_fu_r = f_fu.filter(
                                _sess_day__gte=range_start,
                                _sess_day__lte=range_end,
                            )
                            if aset:
                                done_n = int(
                                    f_fu_r.filter(
                                        student_id__in=aset, follow_up_status__iexact="completed"
                                    )
                                    .values("student_id")
                                    .distinct()
                                    .count()
                                )
                                tot_n = len(aset)
                            else:
                                done_n = int(
                                    f_fu_r.filter(follow_up_status__iexact="completed")
                                    .exclude(student_id__isnull=True)
                                    .values("student_id")
                                    .distinct()
                                    .count()
                                )
                                tot_n = max(done_n, 1)
                            other_n = max(0, tot_n - done_n)
                            ctx["ttv2_counselors_charts"]["donut"] = {
                                "counselled": done_n,
                                "not_counselled": other_n,
                            }
                            ctx["ttv2_counselors_charts"]["donut_table"] = [
                                {"segment": "Counselled in period", "count": done_n},
                                {"segment": "Remaining on roster", "count": other_n},
                            ]
                    except Exception:
                        pass

                # Scorecard: current Mon–Sun week vs previous week
                week_prev_start = week_start - timedelta(days=7)
                week_prev_end = week_end - timedelta(days=7)

                def _fu_week(cid, ws, we):
                    if not cid:
                        return fu.none()
                    return (
                        fu.filter(counselor_id=cid)
                        .filter(_sess_day__gte=ws, _sess_day__lte=we)
                    )

                sc_counselor = Counselor.objects.filter(id=focus_cid).first() if focus_cid else None
                scorecard = None
                if sc_counselor:
                    uid_list = [
                        int(x)
                        for x in sc_counselor.students.filter(institute=institute).values_list(
                            "student_id", flat=True
                        )
                        if x
                    ]
                    assigned_sm_n = len(
                        list(sc_counselor.students.filter(institute=institute).values_list("id", flat=True))
                    )
                    psych_done, psych_total, _on_track, clarity_avg = _psych_and_risk(uid_list)
                    psych_pct = int(round(100.0 * float(psych_done) / float(psych_total))) if psych_total else 0

                    fu_w = _fu_week(focus_cid, week_start, week_end)
                    fu_pw = _fu_week(focus_cid, week_prev_start, week_prev_end)
                    sess_w = int(fu_w.count())
                    sess_pw = int(fu_pw.count())

                    def _distinct_contacted(qs):
                        return int(qs.exclude(student_id__isnull=True).values("student_id").distinct().count())

                    contacted_w = _distinct_contacted(fu_w)
                    contacted_pw = _distinct_contacted(fu_pw)

                    if assigned_sm_n:
                        contacted_target_den = assigned_sm_n
                    else:
                        contacted_target_den = max(contacted_w, 1)

                    try:
                        from careers.models import CareerShortlist

                        car_w = int(
                            CareerShortlist.objects.filter(
                                user_id__in=uid_list,
                                created__date__gte=week_start,
                                created__date__lte=week_end,
                            ).count()
                        )
                        car_pw = int(
                            CareerShortlist.objects.filter(
                                user_id__in=uid_list,
                                created__date__gte=week_prev_start,
                                created__date__lte=week_prev_end,
                            ).count()
                        )
                    except Exception:
                        car_w, car_pw = 0, 0

                    try:
                        psych_att_w = int(
                            Results.objects.filter(
                                user_id__in=uid_list,
                                test_paper__in=["test1", "test2", "test3"],
                                modified__date__gte=week_start,
                                modified__date__lte=week_end,
                            ).count()
                        )
                        psych_att_pw = int(
                            Results.objects.filter(
                                user_id__in=uid_list,
                                test_paper__in=["test1", "test2", "test3"],
                                modified__date__gte=week_prev_start,
                                modified__date__lte=week_prev_end,
                            ).count()
                        )
                    except Exception:
                        psych_att_w, psych_att_pw = 0, 0

                    target_sessions = max(4, sess_pw)
                    met_sess = sess_w >= target_sessions
                    score_sess = "10/10" if sess_w >= target_sessions else f"{min(10, int(round(10 * sess_w / max(target_sessions, 1))))}/10"

                    t_cont = f"{contacted_target_den}/{contacted_target_den}"
                    a_cont = f"{contacted_w}/{contacted_target_den}"
                    met_cont = contacted_w >= contacted_target_den and contacted_target_den > 0
                    score_cont = "100%" if met_cont else (f"{int(round(100.0 * contacted_w / max(contacted_target_den, 1)))}%" if contacted_target_den else "0%")

                    met_psych = psych_pct >= 75
                    score_psych = "Exceeded" if psych_pct >= 100 else ("Met" if psych_pct >= 75 else f"{psych_pct}%")

                    met_clar = float(clarity_avg) < 15.0
                    score_clar = "Exceeded" if met_clar else ("Met" if float(clarity_avg) < 20.0 else "Below")

                    met_car = 2 <= car_w <= 3 or car_w >= 3
                    score_car = "Met" if met_car else ("Close" if car_w >= 1 else "Low")

                    rows_sc = [
                        {
                            "metric": "Sessions conducted",
                            "target": str(target_sessions),
                            "achieved": str(sess_w),
                            "score": score_sess,
                            "vs_prev": f"+{sess_w - sess_pw}" if sess_w >= sess_pw else str(sess_w - sess_pw),
                            "rating": 5 if met_sess else max(1, min(4, 2 + sess_w)),
                            "ok": bool(met_sess),
                        },
                        {
                            "metric": "Students contacted",
                            "target": t_cont,
                            "achieved": a_cont,
                            "score": score_cont,
                            "vs_prev": (
                                f"+{contacted_w - contacted_pw}"
                                if contacted_w != contacted_pw
                                else "0"
                            ),
                            "rating": 5 if met_cont else 3,
                            "ok": bool(met_cont),
                        },
                        {
                            "metric": "Psychometric completion",
                            "target": "75–100%",
                            "achieved": f"{psych_pct}%",
                            "score": score_psych,
                            "vs_prev": f"+{psych_att_w - psych_att_pw}" if psych_att_w != psych_att_pw else "0",
                            "rating": 5 if met_psych else 3,
                            "ok": bool(met_psych),
                        },
                        {
                            "metric": "Clarity gap reduction",
                            "target": "<15%",
                            "achieved": f"{clarity_avg}%",
                            "score": score_clar,
                            "vs_prev": "—",
                            "rating": 5 if met_clar else 4,
                            "ok": bool(met_clar),
                        },
                        {
                            "metric": "Career paths shortlisted",
                            "target": "2–3",
                            "achieved": f"{car_w} paths",
                            "score": score_car,
                            "vs_prev": f"+{car_w - car_pw}" if car_w != car_pw else "0",
                            "rating": 5 if (2 <= car_w <= 3) else (4 if car_w >= 2 else 2),
                            "ok": bool(met_car),
                        },
                        {
                            "metric": "Avg session duration",
                            "target": "30 min",
                            "achieved": "—",
                            "score": "—",
                            "vs_prev": "—",
                            "rating": 0,
                            "ok": True,
                            "na": True,
                        },
                    ]
                    all_ok = all(bool(r.get("ok")) for r in rows_sc if not r.get("na"))
                    scorecard = {
                        "counselor_id": focus_cid,
                        "email": (getattr(sc_counselor, "counselor_email", None) or "").strip(),
                        "week_label": f"{week_start:%d}–{week_end:%d %b}",
                        "week_start": week_start.isoformat(),
                        "week_end": week_end.isoformat(),
                        "all_targets_met": bool(all_ok),
                        "rows": rows_sc,
                    }
                ctx["ttv2_counselors_scorecard"] = scorecard
            except Exception:
                ctx["ttv2_counselors_kpis"] = {
                    "counselors": 0,
                    "sessions_logged": 0,
                    "students_counseled": 0,
                    "students_counselled_total": 0,
                    "students_counselled_pct": 0,
                    "followups_sent": 0,
                    "avg_sessions": 0,
                }
                ctx["ttv2_counselors_leaderboard"] = []
                ctx["ttv2_counselors_week_activity"] = {
                    "week_start": "",
                    "week_end": "",
                    "days": [],
                }
                ctx["ttv2_counselors_roster"] = []
                ctx["ttv2_counselors_chart_controls"] = {
                    "range_key": "30d",
                    "range_label": "Last 30 days",
                    "from_iso": "",
                    "to_iso": "",
                }
                ctx["ttv2_counselors_charts"] = {
                    "line": {"title": "", "subtitle": "", "labels": [], "values": []},
                    "line_table": [],
                    "donut": {"counselled": 0, "not_counselled": 0},
                    "donut_table": [],
                    "focus_name": "",
                    "range_key": "30d",
                    "range_label": "",
                    "range_from": "",
                    "range_to": "",
                }
                ctx["ttv2_counselors_focus_id"] = None
                ctx["ttv2_counselors_scorecard"] = None

        # v2 session plan page: dummy data for now (form disabled when empty).
        if (ctx.get("ttv2_page") or "").strip().lower() == "session_plan":
            ctx.setdefault("ttv2_session_plan_is_dummy", False)
            ctx.setdefault("ttv2_session_plan_rows", [])

        # v2 "Streams & capacity" page: counts per stream vs configured seat capacity on Institute.
        if (ctx.get("ttv2_page") or "").strip().lower() == "streams_capacity":
            inst = ctx.get("institute")
            stu_qs = ctx.get("stu")
            cap_map = {
                "PCM": int(getattr(inst, "pcm", 0) or 0) if inst else 0,
                "CBM": int(getattr(inst, "cbm", 0) or 0) if inst else 0,
                "COMM": int(getattr(inst, "comm", 0) or 0) if inst else 0,
                "HME": int(getattr(inst, "hme", 0) or 0) if inst else 0,
                "HMB": int(getattr(inst, "hmb", 0) or 0) if inst else 0,
            }

            def _norm_stream_code(raw):
                v = (raw or "").strip().upper()
                if not v:
                    return ""
                alias = {
                    "CB": "CBM",
                    "MCOM": "COMM",
                    "HUM": "HME",
                    "HM": "HMB",
                }
                return alias.get(v, v)

            stream_counts = {}
            if hasattr(stu_qs, "exclude"):
                try:
                    for row in (
                        stu_qs.exclude(class_and_section__stream__isnull=True)
                        .exclude(class_and_section__stream__exact="")
                        .values("class_and_section__stream")
                        .annotate(n=Count("id"))
                    ):
                        key = _norm_stream_code(row.get("class_and_section__stream"))
                        if key:
                            stream_counts[key] = int(row.get("n") or 0)
                except Exception:
                    stream_counts = {}

            rows = []
            seen = set()
            for code, cap in cap_map.items():
                enrolled = int(stream_counts.get(code, 0))
                rows.append(
                    {
                        "code": code,
                        "label": {"PCM": "PCM", "CBM": "CB", "COMM": "MCOM", "HME": "HUM", "HMB": "HM"}.get(code, code),
                        "enrolled": enrolled,
                        "capacity": int(cap),
                        "remaining": max(0, int(cap) - enrolled) if cap else 0,
                    }
                )
                seen.add(code)

            for code, enrolled in sorted(stream_counts.items(), key=lambda x: x[0]):
                if code in seen:
                    continue
                rows.append(
                    {
                        "code": code,
                        "label": code,
                        "enrolled": int(enrolled),
                        "capacity": 0,
                        "remaining": 0,
                    }
                )

            ctx["ttv2_streams_capacity_is_dummy"] = False
            ctx["ttv2_streams_capacity"] = rows

            classes = ["11th class", "12th class"]
            class_stream_counts = {}
            if hasattr(stu_qs, "values") and hasattr(stu_qs, "exclude"):
                try:
                    for r in (
                        stu_qs.exclude(class_and_section__stream__isnull=True)
                        .exclude(class_and_section__stream__exact="")
                        .exclude(class_and_section__class_and_section__isnull=True)
                        .exclude(class_and_section__class_and_section__exact="")
                        .values("class_and_section__class_and_section", "class_and_section__stream")
                        .annotate(n=Count("id"))
                    ):
                        cls_raw = (r.get("class_and_section__class_and_section") or "").strip().lower()
                        if "11" in cls_raw:
                            cls_key = "11th class"
                        elif "12" in cls_raw:
                            cls_key = "12th class"
                        else:
                            continue
                        sc = _norm_stream_code(r.get("class_and_section__stream"))
                        if not sc:
                            continue
                        class_stream_counts[(cls_key, sc)] = int(r.get("n") or 0)
                except Exception:
                    class_stream_counts = {}

            streams_meta = [
                {"code": "PCM", "label": "PCM"},
                {"code": "CBM", "label": "CB"},
                {"code": "COMM", "label": "MCOM"},
                {"code": "HME", "label": "HUM"},
                {"code": "HMB", "label": "HM"},
            ]

            class_rows = []
            total_filled = 0
            cap_per_class = sum(int(v or 0) for v in cap_map.values())
            for idx, cls in enumerate(classes, start=1):
                filled = 0
                per_stream = {}
                for sm in streams_meta:
                    code = sm["code"]
                    n = int(class_stream_counts.get((cls, code), 0))
                    per_stream[code] = {"cap": int(cap_map.get(code, 0) or 0), "filled": n}
                    filled += n
                total = int(cap_per_class)
                available = max(0, total - filled)
                pct = (float(filled) / float(total) * 100.0) if total else 0.0
                total_filled += filled
                class_rows.append(
                    {
                        "idx": idx,
                        "class_label": cls,
                        "streams": per_stream,
                        "total": total,
                        "filled": int(filled),
                        "available": int(available),
                        "fill_pct": round(pct, 1),
                    }
                )

            total_capacity = int(cap_per_class) * len(classes)
            open_seats = max(0, total_capacity - total_filled)
            fill_rate = (float(total_filled) / float(total_capacity) * 100.0) if total_capacity else 0.0

            occ_by_stream = []
            for sm in streams_meta:
                code = sm["code"]
                cap_total = int(cap_map.get(code, 0) or 0) * len(classes)
                filled_stream = sum(int(class_stream_counts.get((cls, code), 0)) for cls in classes)
                occ_pct = (float(filled_stream) / float(cap_total) * 100.0) if cap_total else 0.0
                occ_by_stream.append(
                    {"code": code, "label": sm["label"], "filled": int(filled_stream), "capacity": int(cap_total), "pct": round(occ_pct, 2)}
                )

            ctx["ttv2_streams_capacity_payload"] = {
                "kpis": {
                    "total_capacity": total_capacity,
                    "seats_filled": int(total_filled),
                    "open_seats": int(open_seats),
                    "fill_rate_pct": round(fill_rate, 2),
                    "streams_count": len(streams_meta),
                    "classes_count": len(classes),
                    "capacity_per_stream_default": int(max(cap_map.values()) if cap_map else 0),
                },
                "streams_meta": streams_meta,
                "classes": classes,
                "cap_map": cap_map,
                "class_rows": class_rows,
                "occupancy_by_stream": occ_by_stream,
            }

        payments_partial = _render_ttv2_tieup_payments_partial(request, ctx)
        if payments_partial is not None:
            return payments_partial

        # v2 partial rendering for fast AJAX shell boot
        try:
            template_version = (Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1").strip()
        except Exception:
            template_version = "v1"
        if template_version == "v2" and request_wants_ttv2_dashboard_body_partial(request):
            return render(request, "template_v2/dashboard_unified_body.html", ctx)

        return render(request, _dashboard_primary_template_name(self), ctx )
    
    def _results_aux_maps_by_user_id(self, user_ids):
        """Batch-fetch test rows for institute student table; dict keys are user_id (int)."""
        tcm, pmm, rmap = {}, {}, {}
        if not user_ids:
            return tcm, pmm, rmap
        from app.models import TestCompletion, Results
        from app_post_matric.models import TestSession as PostMatricTestSession
        try:
            uids = list({int(x) for x in user_ids if x is not None})
        except (TypeError, ValueError):
            uids = []
        if not uids:
            return tcm, pmm, rmap
        for tc in TestCompletion.objects.filter(user_id__in=uids).select_related("user"):
            tcm[tc.user_id] = tc
        for s in PostMatricTestSession.objects.filter(user_id__in=uids).select_related("user", "test", "result"):
            pmm.setdefault(s.user_id, []).append(s)
        for r in Results.objects.filter(user_id__in=uids).select_related("user"):
            rmap.setdefault(r.user_id, []).append(r)
        return tcm, pmm, rmap

    def _build_results_data_for_managements(self, sm_list, tcm, pmm, rmap):
        out = {}
        for stu in sm_list:
            if not stu.student_id or not stu.student:
                continue
            user = stu.student
            out[user.id] = self._get_student_test_result_optimized(
                user,
                stu,
                tcm.get(stu.student_id),
                pmm.get(stu.student_id) or [],
                rmap.get(stu.student_id) or [],
            )
        return out

    def get_student_table_context_ajax(self, request, *args, **kwargs):
        """
        Lightweight context for the AJAX student table.
        When the "Test taken" filter is off, paginate first and only build test/result
        data for the current page (avoids N× work for large institutes).

        Either pass ``slug`` (single-institute dashboard) **or** ``stu_manage`` +
        ``institute`` (multi-school dashboards: marketing / institute-group).
        """
        stu_manage_kw = kwargs.get("stu_manage")
        institute_kw = kwargs.get("institute")
        if stu_manage_kw is not None:
            stu_manage = stu_manage_kw
            institute = institute_kw
        else:
            slug = kwargs.get("slug")
            institute = get_object_or_404(Institute, slug=slug)
            stu_manage = (
                get_students_by_role(request.user, institute=institute)
                .select_related("student", "class_and_section", "institute", "counselor")
                .prefetch_related("counselors")
            )

        stream_filter = request.GET.get("stream", "")
        test_taken_filter = request.GET.get("test_taken", "").strip()

        class_and_sections = get_class_and_sections_by_role(request.user, stu_manage)
        class_counts = get_class_counts(stu_manage)
        unique_streams = get_unique_streams_by_role(request.user, stu_manage)

        # Class / name: DB; do not require results_data yet.
        filtered_students = apply_student_filters(stu_manage, request, results_data=None)
        if stream_filter:
            if hasattr(filtered_students, "filter"):
                filtered_students = filtered_students.filter(
                    class_and_section__stream=stream_filter
                )
            else:
                filtered_students = [
                    s
                    for s in filtered_students
                    if hasattr(s, "class_and_section")
                    and s.class_and_section
                    and s.class_and_section.stream == stream_filter
                ]

        # Grid (cards) view fills a 3-column grid best with 12 per page (4 rows × 3).
        # Use 12 as the default when no explicit per_page is supplied and we're in cards mode.
        _display_param = (request.GET.get("display") or "").strip().lower()
        _is_cards = _display_param == "cards"
        _default_pp = "12" if _is_cards else "10"
        per_page_param = request.GET.get("per_page", _default_pp)
        if per_page_param == "all":
            per_page_value = 10000
        else:
            try:
                per_page_value = int(per_page_param)
            except (ValueError, TypeError):
                per_page_value = 12 if _is_cards else 10

        page_number = request.GET.get("page", 1)
        if test_taken_filter:
            if hasattr(filtered_students, "order_by"):
                sm_all = list(
                    filtered_students.select_related(
                        "student", "class_and_section", "institute"
                    ).order_by("-created")
                )
            else:
                sm_all = sorted(
                    list(filtered_students), key=lambda x: x.created, reverse=True
                )
            uids_all = [sm.student_id for sm in sm_all if sm.student_id]
            tcm, pmm, rmap = self._results_aux_maps_by_user_id(uids_all)
            full_results = self._build_results_data_for_managements(
                sm_all, tcm, pmm, rmap
            )
            kept = []
            for sm in sm_all:
                if not sm.student:
                    continue
                tr = full_results.get(sm.student_id, {})
                ts = tr.get("test_status", "no_tests")
                if test_taken_filter == "Yes" and ts == "completed":
                    kept.append(sm)
                elif test_taken_filter == "No" and ts == "no_tests":
                    kept.append(sm)
                elif test_taken_filter == "In Progress" and ts == "in_progress":
                    kept.append(sm)
            pages = Paginator(kept, per_page_value)
        else:
            if isinstance(filtered_students, list):
                pages = Paginator(
                    sorted(filtered_students, key=lambda x: x.created, reverse=True),
                    per_page_value,
                )
            else:
                pages = Paginator(filtered_students.order_by("-created"), per_page_value)

        try:
            total_students = pages.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            total_students = pages.get_page(1)

        if test_taken_filter:
            page_list = list(total_students.object_list)
            results_data = {
                sm.student_id: full_results[sm.student_id]
                for sm in page_list
                if sm.student_id in full_results
            }
        else:
            page_list = list(total_students.object_list)
            page_uids = [sm.student_id for sm in page_list if sm.student_id]
            tcm, pmm, rmap = self._results_aux_maps_by_user_id(page_uids)
            results_data = self._build_results_data_for_managements(
                page_list, tcm, pmm, rmap
            )

        # Latest counselling status per student (for roster cards).
        # Keyed by StudentManagement.id (sm.id) to match templates.
        followup_latest_map = {}
        try:
            from counselor.models import FollowUpStatus
            from django.db.models.functions import Coalesce, TruncDate
            from django.db import models as _models

            sm_ids_page = [int(sm.id) for sm in page_list if getattr(sm, "id", None)]
            if sm_ids_page:
                try:
                    today = timezone.localdate()
                except Exception:
                    today = datetime.now().date()
                try:
                    tomorrow = today + timedelta(days=1)
                except Exception:
                    tomorrow = today

                # Sort by the most relevant date available.
                fu_qs = FollowUpStatus.objects.filter(student_id__in=sm_ids_page).select_related("counselor")
                fu_qs = fu_qs.annotate(
                    _sort_date=Coalesce(
                        "last_follow_up_date",
                        "next_follow_up_date",
                        TruncDate("created"),
                        output_field=_models.DateField(),
                    )
                ).order_by("-_sort_date", "-created")

                for fu in fu_qs:
                    sid = getattr(fu, "student_id", None)
                    if not sid:
                        continue
                    sid = int(sid)
                    if sid in followup_latest_map:
                        continue

                    last_dt = getattr(fu, "last_follow_up_date", None)
                    next_dt = getattr(fu, "next_follow_up_date", None)
                    status_raw = (getattr(fu, "follow_up_status", "") or "").strip().lower()
                    is_done = bool(getattr(fu, "is_followed_up", False)) or (status_raw == "completed")
                    is_pending = not is_done

                    smart_key = "not_scheduled"
                    smart_label = "Not scheduled"
                    smart_btn_label = ""
                    smart_btn_variant = ""
                    show_followup_btn = False

                    # Pending follow-up buckets (drives label).
                    if is_pending and next_dt:
                        if next_dt < today:
                            smart_key = "overdue"
                            smart_label = "Overdue"
                            show_followup_btn = True
                            smart_btn_variant = "danger"
                            smart_btn_label = f"Date: {next_dt.strftime('%d/%m/%Y')}"
                        elif next_dt == today:
                            smart_key = "due_today"
                            smart_label = "Due today"
                            show_followup_btn = True
                            smart_btn_variant = "warning"
                            smart_btn_label = "Due today"
                        elif next_dt <= tomorrow:
                            smart_key = "upcoming"
                            smart_label = "Upcoming follow-up"
                            show_followup_btn = True
                            smart_btn_variant = "warning"
                            smart_btn_label = f"Date: {next_dt.strftime('%d/%m/%Y')}"
                        else:
                            smart_key = "scheduled_future"
                            smart_label = "Next"
                    elif is_done:
                        # If completed recently, show completed.
                        try:
                            done_day = last_dt or getattr(fu, "created", None).date()
                        except Exception:
                            done_day = last_dt
                        if done_day == today:
                            smart_key = "completed_today"
                            smart_label = "Completed"
                        else:
                            smart_key = "completed"
                            smart_label = "Completed"

                    followup_latest_map[sid] = {
                        "smart_key": smart_key,
                        "smart_label": smart_label,
                        "smart_btn_label": smart_btn_label,
                        "smart_btn_variant": smart_btn_variant,
                        "show_followup_btn": show_followup_btn,
                        "is_followed_up": bool(is_done),
                        "when": (last_dt.strftime("%d/%m/%Y") if last_dt else ""),
                        "next": (next_dt.strftime("%d/%m/%Y") if next_dt else ""),
                        "next_raw": (next_dt.isoformat() if next_dt else ""),
                        "counselor_name": (
                            (getattr(getattr(fu, "counselor", None), "counselor_name", None) or "").strip()
                            if getattr(fu, "counselor", None)
                            else ""
                        ),
                    }
        except Exception:
            followup_latest_map = {}

        stu_value = (
            filtered_students
            if hasattr(filtered_students, "filter")
            else filtered_students
        )
        if institute:
            counselor_opts = [
                _ttv2_counselor_dropdown_row(c.id, getattr(c, "counselor_name", "") or "")
                for c in Counselor.qs_for_institute(institute).only(
                    "id", "counselor_name"
                ).order_by(Lower("counselor_name"))
            ]
            bulk_counselor_opts = [
                {**row, "institute_id": institute.id} for row in counselor_opts
            ]
        else:
            counselor_opts = []
            bulk_counselor_opts = []
            _slug_scope = (request.GET.get("institute_slug") or "").strip()
            if _slug_scope:
                try:
                    _inst_scope = Institute.objects.filter(slug=_slug_scope).first()
                    if _inst_scope:
                        bulk_counselor_opts = [
                            _ttv2_counselor_dropdown_row(
                                c.id,
                                getattr(c, "counselor_name", "") or "",
                                institute_id=_inst_scope.id,
                            )
                            for c in Counselor.qs_for_institute(_inst_scope)
                            .only("id", "counselor_name")
                            .order_by(Lower("counselor_name"))
                        ]
                except Exception:
                    bulk_counselor_opts = []
            else:
                iids_set = set()
                try:
                    if hasattr(filtered_students, "values_list"):
                        iids_set = {
                            int(x)
                            for x in filtered_students.values_list(
                                "institute_id", flat=True
                            ).distinct()[:800]
                            if x is not None
                        }
                    elif isinstance(filtered_students, list):
                        for sm in filtered_students:
                            iid = getattr(sm, "institute_id", None)
                            if iid:
                                iids_set.add(int(iid))
                except Exception:
                    iids_set = set()
                if not iids_set:
                    try:
                        for sm in page_list or []:
                            iid = getattr(sm, "institute_id", None)
                            if iid:
                                iids_set.add(int(iid))
                    except Exception:
                        pass
                if iids_set:
                    try:
                        i_sorted = sorted(iids_set)
                        placement_q = (
                            Q(counselor_admin_id__in=i_sorted)
                            | Q(institute_placements__id__in=i_sorted)
                        )
                        for c in (
                            Counselor.objects.filter(placement_q)
                            .select_related("counselor_admin")
                            .prefetch_related("institute_placements")
                            .only("id", "counselor_name", "counselor_admin_id")
                            .distinct()
                            .order_by(Lower("counselor_name"), "id")
                        ):
                            placements_out = []
                            aid = c.counselor_admin_id
                            if aid and aid in iids_set:
                                placements_out.append((aid, c.counselor_admin))
                            for inst in c.institute_placements.all():
                                if inst.id in iids_set and inst.id != aid:
                                    placements_out.append((inst.id, inst))
                            if not placements_out:
                                continue
                            for iid, admin in placements_out:
                                iname = getattr(admin, "name", "") or "—"
                                bulk_counselor_opts.append(
                                    _ttv2_counselor_dropdown_row(
                                        c.id,
                                        getattr(c, "counselor_name", None),
                                        institute_id=iid,
                                        institute_nm_suffix=iname,
                                    )
                                )
                    except Exception:
                        bulk_counselor_opts = []

        pkg_ctx = {}
        from institute.psychometric_packages import (
            build_institute_package_dashboard_ctx,
            build_roster_assessment_map,
            get_student_package_labels_for_institute,
            get_student_package_labels_for_user_ids,
            institute_package_mode_active,
        )
        from core.assessment_access import packages_enabled

        pkg_ctx["student_roster_assessments"] = build_roster_assessment_map(
            page_list, results_data
        )
        pkg_ctx["psychometric_packages_enabled"] = packages_enabled()
        if institute:
            pkg_ctx.update(build_institute_package_dashboard_ctx(institute))
            pkg_ctx["student_psychometric_packages"] = get_student_package_labels_for_institute(
                institute
            )
        else:
            page_student_ids = [sm.student_id for sm in page_list if sm.student_id]
            pkg_ctx["student_psychometric_packages"] = get_student_package_labels_for_user_ids(
                page_student_ids
            )
            # Multi-school roster (marketing / institute-group): keep package column
            # and card badges available whenever the feature flag is on.
            pkg_ctx["institute_package_mode"] = bool(packages_enabled()) and (
                any(
                    institute_package_mode_active(getattr(sm, "institute", None))
                    for sm in page_list
                )
                or bool(pkg_ctx["student_psychometric_packages"])
            )

        return {
            "total_students": total_students,
            "total_students_count": stu_manage.count(),
            # Rows matching current filters (before pagination); used to refresh the v2 roster header via AJAX.
            "roster_filtered_total": pages.count,
            "class_and_sections": class_and_sections,
            "class_counts": class_counts,
            "unique_streams": unique_streams,
            "results_data": results_data,
            "stu": stu_value,
            "institute": institute,
            "ttv2_counselor_options": counselor_opts,
            "ttv2_counselors_by_institute_id": _ttv2_counselor_options_by_institute_id(page_list),
            "ttv2_bulk_counselor_options": bulk_counselor_opts,
            "ttv2_followup_latest_map": followup_latest_map,
            **pkg_ctx,
        }
    
    def post(self, request, *args, **kwargs):
        slug=kwargs.get("slug")
        institute=get_object_or_404(Institute,slug=slug)
        if getattr(institute, "is_system_demo", False):
            messages.error(request, "Demo institute: cannot add new students.")
            ctx = self.get_context(request, *args, **kwargs)
            return render(request, _dashboard_primary_template_name(self), ctx)
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        class_section=request.POST.get("class_section")
        email=request.POST.get("student_email")
        filter_emails=email.replace(" ","").replace("\r\n",'')
        email_list=filter_emails.split(",")
        ctx=self.get_context(request, *args, **kwargs)
        error_list=[]
        for semail in email_list:
            em=re.match(evalid,semail)
            user_exist=User.objects.filter(email=semail).exists()
            if institute.is_valid_credit_count() and class_section and em and not user_exist:
                cas=get_object_or_404(ClassAndSection,id=class_section)
                import random
                password=''.join([str(random.randint(0,10)) for _ in range(6)])
                student=User.objects.create_user(email=semail, password=password)
                student.save()
                stu_manage=StudentManagement(institute=institute,student=student,class_and_section=cas)
                stu_manage.save()
                from institute.psychometric_packages import maybe_assign_package_from_post
                maybe_assign_package_from_post(request, institute, student)
                update_student_data.delay(institute.id,institute.name)
                create_student_and_send_mail.delay(stu_manage.id,semail,password,institute.name,institute.logo.url)
                # messages.success(request, "{} Created".format(semail))
            else:
                if user_exist:
                    messages.error(request,"{} Already Exist !!".format(semail))
                    error_list.append(semail)
                elif not em:
                    messages.error(request,"{} Invalid Email !!".format(semail))
                    error_list.append(semail)
                elif not institute.is_valid_credit_count():
                    messages.info(request,"No remaining credits")
                    error_list.append(semail)
                elif not class_section:
                    messages.info(request,"Class Not Selected")
                else:
                    messages.error(request,"{} Something Went Wrong !!".format(semail))
                    error_list.append(semail)
        ctx["error_list"]=error_list
        create_institute_log.delay(institute.id,error_list,len(email_list))
        return render(request, _dashboard_primary_template_name(self), ctx)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(institute_authenticated_user_only, name='dispatch')
class AssignStudentPackageView(View):
    """Assign a psychometric package to an existing institute student."""

    def post(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        institute = get_object_or_404(Institute, slug=slug)
        sm_id = request.POST.get("student_management_id")
        package_code = (request.POST.get("psychometric_package") or "").strip()

        try:
            sm_id = int(sm_id)
        except (TypeError, ValueError):
            messages.error(request, "Invalid student.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

        sm = get_object_or_404(StudentManagement, id=sm_id, institute=institute)
        student = sm.student
        if not student:
            messages.error(request, "Student account not found.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

        from institute.psychometric_packages import try_assign_package_code

        ok, message = try_assign_package_code(
            institute,
            student,
            package_code,
            assigned_by=request.user,
        )
        if ok:
            messages.success(request, f"Package assigned to {student.email}.")
        else:
            messages.error(request, message or "Could not assign package.")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(institute_authenticated_user_only, name='dispatch')
class AssignStudentToCounselorView(View):
    """
    AJAX endpoint: assign a StudentManagement row to a counselor (M2M Counselor.students).
    """

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        sm_id = payload.get("student_management_id")
        counselor_id = payload.get("counselor_id")
        slug = kwargs.get("slug")

        try:
            sm_id = int(sm_id)
            counselor_id = int(counselor_id)
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_params"}, status=400)

        institute = get_object_or_404(Institute, slug=slug)
        counselor = get_object_or_404(
            Counselor.qs_for_institute(institute), id=counselor_id
        )
        sm = get_object_or_404(StudentManagement, id=sm_id, institute=institute)

        try:
            counselor.students.add(sm)
        except Exception:
            return JsonResponse({"ok": False, "error": "assign_failed"}, status=500)

        # Notify counselor (in-app + email) about assignment.
        try:
            counselor_user = getattr(counselor, "coun_user", None)
            if counselor_user and getattr(counselor_user, "email", None):
                from notifications.services import emit_notification
                from notifications.models import NotificationCategory
                from communication.com_service import ComService

                student_user = getattr(sm, "student", None)
                student_name = getattr(student_user, "name", None) or getattr(student_user, "email", None) or "Student"
                student_email = getattr(student_user, "email", None) or ""
                inst_name = getattr(institute, "name", None) or "Institute"

                emit_notification(
                    event_type="institute.student_assigned",
                    title="New student assigned",
                    body=f"A new student {student_name} ({student_email}) was assigned to you by {inst_name}.",
                    recipients=[counselor_user],
                    category=NotificationCategory.INSTITUTE,
                    payload={
                        "student_management_id": sm.id,
                        "student_id": getattr(sm, "student_id", None),
                        "institute_id": institute.id,
                        "counselor_id": counselor.id,
                    },
                    source_obj=sm,
                    dedupe_key=f"institute.student_assigned:sm{sm.id}:u{counselor_user.id}",
                )

                # Email (best-effort)
                try:
                    cs = ComService()
                    subject = cs.build_email_subject("New student assigned")
                    html = (
                        f"<p>Hello {getattr(counselor, 'counselor_name', '') or 'Counselor'},</p>"
                        f"<p><strong>{student_name}</strong> ({student_email}) has been assigned to you by <strong>{inst_name}</strong>.</p>"
                        f"<p>Please login to your counselor dashboard to view details.</p>"
                    )
                    to_list = []
                    try:
                        if counselor_user.email:
                            to_list.append(str(counselor_user.email).strip())
                    except Exception:
                        pass
                    try:
                        if getattr(counselor, "counselor_email", None):
                            to_list.append(str(getattr(counselor, "counselor_email")).strip())
                    except Exception:
                        pass
                    # de-dupe
                    to_list = [x for i, x in enumerate(to_list) if x and x not in to_list[:i]]
                    if to_list:
                        cs.send_mail(subject, to_list, html, html)
                except Exception:
                    pass
        except Exception:
            pass

        return JsonResponse({"ok": True})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(institute_authenticated_user_only, name='dispatch')
class SetStudentCounselorView(View):
    """
    AJAX endpoint: change/unassign counselor for a StudentManagement row.

    Payload:
      - student_management_id: int
      - counselor_id: int | null | ''   (if empty -> unassign)
    """

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        sm_id = payload.get("student_management_id")
        counselor_id = payload.get("counselor_id")
        slug = kwargs.get("slug")

        try:
            sm_id = int(sm_id)
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_params"}, status=400)

        # counselor_id can be empty for unassign
        counselor_id_int = None
        try:
            if counselor_id is not None and str(counselor_id).strip() != "":
                counselor_id_int = int(counselor_id)
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_params"}, status=400)

        institute = get_object_or_404(Institute, slug=slug)
        sm = get_object_or_404(StudentManagement, id=sm_id, institute=institute)

        # Remove from any counselors of this institute (avoid cross-institute bleed)
        try:
            for c in Counselor.qs_for_institute(institute).filter(students=sm):
                c.students.remove(sm)
        except Exception:
            return JsonResponse({"ok": False, "error": "unassign_failed"}, status=500)

        try:
            sm.counselor = None
            sm.save(update_fields=["counselor"])
        except Exception:
            pass

        # Assign to new counselor if provided
        if counselor_id_int is not None:
            counselor = get_object_or_404(
                Counselor.qs_for_institute(institute), id=counselor_id_int
            )
            try:
                counselor.students.add(sm)
            except Exception:
                return JsonResponse({"ok": False, "error": "assign_failed"}, status=500)

            try:
                sm.counselor = counselor
                sm.save(update_fields=["counselor"])
            except Exception:
                pass

            # Notify counselor about assignment (same as assign endpoint)
            try:
                counselor_user = getattr(counselor, "coun_user", None)
                if counselor_user and getattr(counselor_user, "email", None):
                    from notifications.services import emit_notification
                    from notifications.models import NotificationCategory
                    from communication.com_service import ComService

                    student_user = getattr(sm, "student", None)
                    student_name = getattr(student_user, "name", None) or getattr(student_user, "email", None) or "Student"
                    student_email = getattr(student_user, "email", None) or ""
                    inst_name = getattr(institute, "name", None) or "Institute"

                    emit_notification(
                        event_type="institute.student_assigned",
                        title="New student assigned",
                        body=f"A new student {student_name} ({student_email}) was assigned to you by {inst_name}.",
                        recipients=[counselor_user],
                        category=NotificationCategory.INSTITUTE,
                        payload={
                            "student_management_id": sm.id,
                            "student_id": getattr(sm, "student_id", None),
                            "institute_id": institute.id,
                            "counselor_id": counselor.id,
                        },
                        source_obj=sm,
                        dedupe_key=f"institute.student_assigned:sm{sm.id}:u{counselor_user.id}",
                    )

                    # Email (best-effort)
                    try:
                        cs = ComService()
                        subject = cs.build_email_subject("New student assigned")
                        html = (
                            f"<p>Hello {getattr(counselor, 'counselor_name', '') or 'Counselor'},</p>"
                            f"<p><strong>{student_name}</strong> ({student_email}) has been assigned to you by <strong>{inst_name}</strong>.</p>"
                            f"<p>Please login to your counselor dashboard to view details.</p>"
                        )
                        to_list = []
                        try:
                            if counselor_user.email:
                                to_list.append(str(counselor_user.email).strip())
                        except Exception:
                            pass
                        try:
                            if getattr(counselor, "counselor_email", None):
                                to_list.append(str(getattr(counselor, "counselor_email")).strip())
                        except Exception:
                            pass
                        to_list = [x for i, x in enumerate(to_list) if x and x not in to_list[:i]]
                        if to_list:
                            cs.send_mail(subject, to_list, html, html)
                    except Exception:
                        pass
            except Exception:
                pass

        return JsonResponse({"ok": True})


class InstituteMasterDashboardView(InstituteDashboardView):
    """Institute master dashboard at /institute/<slug>/dashboard/ (heatmap + shell)."""

    template_name = "template20/institute/institute_master_dashboard.html"

    def html_head(self):
        name = "Institute Master Dashboard"
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        stu_q = ctx.get("stu")
        rows = []
        if stu_q is not None:
            try:
                rows = list(
                    stu_q.select_related("student", "class_and_section").order_by("-created")[:40]
                )
            except Exception:
                rows = []
        ctx["master_student_rows"] = rows

        tsc = ctx.get("total_students_count")
        n_total = tsc if isinstance(tsc, int) else (len(tsc) if tsc is not None else 0)
        ctx["master_n_students"] = n_total

        sessions_week = 0
        try:
            for block in json.loads(ctx.get("sessions_data_json") or "[]"):
                for day in block.get("sessions") or []:
                    sessions_week += int(day.get("session_count") or 0)
        except (TypeError, ValueError, KeyError):
            sessions_week = 0
        ctx["master_sessions_week_total"] = sessions_week

        trc = ctx.get("test_result_count") or 0
        if n_total:
            ctx["master_psychometric_pct"] = min(100, int(round(100 * float(trc) / float(n_total))))
        else:
            ctx["master_psychometric_pct"] = 0

        cc = ctx.get("class_counts") or {}
        ctx["master_active_classes"] = len(cc) if isinstance(cc, dict) else 0

        inst = ctx.get("institute")
        if inst:
            try:
                ctx["master_credits_remaining"] = int(inst.get_current_credits_count())
            except Exception:
                ctx["master_credits_remaining"] = 0
            ctx["master_credits_total"] = int(inst.credit_counts or 0)
        else:
            ctx["master_credits_remaining"] = 0
            ctx["master_credits_total"] = 0

        streams = ctx.get("streams") or {}
        ctx["master_stream_keys"] = list(streams.keys()) if isinstance(streams, dict) else []
        ctx["master_stream_vals"] = list(streams.values()) if isinstance(streams, dict) else []
        return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class InstituteApproveView(View):
    """
    View to approve an institute by changing its status from pending to approved.
    """
    def get(self, request, id):
        referer = request.META.get('HTTP_REFERER') or reverse('institute:marketinggroupdashboard')
        try:
            institute = Institute.objects.get(id=id)
        except Institute.DoesNotExist:
            messages.error(request, "Institute not found.")
            return HttpResponseRedirect(referer)
        if not request.user.is_superuser:
            mg = institute.marketing_group
            if not mg or mg.marketing_group_admin_id != request.user.id:
                messages.error(
                    request,
                    "You can only approve institutes that belong to your marketing group.",
                )
                return HttpResponseRedirect(referer)
        institute.institute_status = choices.InstituteStatus.APPROVED
        institute.save()
        messages.success(request, f"Institute '{institute.name}' has been approved successfully.")
        return HttpResponseRedirect(referer)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(marketing_group_user_only, name='dispatch')
class InstituteRejectView(View):
    """
    View to reject an institute by changing its status from pending to rejected.
    """
    def get(self, request, id):
        referer = request.META.get('HTTP_REFERER') or reverse('institute:marketinggroupdashboard')
        try:
            institute = Institute.objects.get(id=id)
        except Institute.DoesNotExist:
            messages.error(request, "Institute not found.")
            return HttpResponseRedirect(referer)
        if not request.user.is_superuser:
            mg = institute.marketing_group
            if not mg or mg.marketing_group_admin_id != request.user.id:
                messages.error(
                    request,
                    "You can only reject institutes that belong to your marketing group.",
                )
                return HttpResponseRedirect(referer)
        institute.institute_status = choices.InstituteStatus.REJECTED
        institute.save()
        messages.success(request, f"Institute '{institute.name}' has been rejected.")
        return HttpResponseRedirect(referer)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(marketing_group_user_only, name='dispatch')
class InstituteHardDeleteView(View):
    """
    Permanently remove an institute from the database when it has no student registrations.
    Allowed for superuser or the institute's marketing_group marketing_group_admin.
    """

    http_method_names = ['post']

    def post(self, request, id, *args, **kwargs):
        referer = request.META.get('HTTP_REFERER') or reverse('institute:marketinggroupdashboard')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        def respond_error(message, status=400):
            if is_ajax:
                return JsonResponse({'success': False, 'error': message}, status=status)
            messages.error(request, message)
            return HttpResponseRedirect(referer)

        def respond_success(message):
            if is_ajax:
                return JsonResponse({'success': True, 'message': message})
            messages.success(request, message)
            return HttpResponseRedirect(referer)

        try:
            institute = Institute.objects.get(id=id)
        except Institute.DoesNotExist:
            return respond_error('Institute not found.', 404)

        if getattr(institute, 'is_system_demo', False):
            return respond_error('System demo institutes cannot be deleted.', 403)

        if not request.user.is_superuser:
            mg = institute.marketing_group
            if not mg or mg.marketing_group_admin_id != request.user.id:
                return respond_error(
                    'You can only delete institutes that belong to your marketing group.',
                    403,
                )

        name = institute.name
        try:
            with transaction.atomic():
                locked = Institute.objects.select_for_update().get(pk=institute.pk)
                if StudentManagement.objects.complete().filter(institute_id=locked.pk).exists():
                    return respond_error(
                        'Cannot delete: this institute has student registrations (including inactive rows).',
                    )
                locked.delete(hard_delete=True)
        except Institute.DoesNotExist:
            return respond_error('Institute not found.', 404)
        except Exception:
            return respond_error('Could not delete this institute.', 500)

        return respond_success(f"Institute '{name}' was permanently deleted.")


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_user_only,name='dispatch')
class InstituteStudentCreateView(TemplateView):

    def post(self, request, *args, **kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        mvalid = r'^(\+91|0)?[6789]\d{9}$'

        institute_id=request.POST.get("institute")
        stu_name=request.POST.get("stu_name")
        class_section=request.POST.get("class_section")
        stu_email=request.POST.get("stu_email")
        stu_mobile=request.POST.get("mobile")
        stu_profile=request.FILES.get("profile_pic")
        institute=get_object_or_404(Institute,id=institute_id)
        if getattr(institute, "is_system_demo", False):
            messages.error(request, "Demo institute: cannot add new students.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
        if stu_name and stu_email and stu_mobile and stu_profile:
            stu_exist=User.objects.filter(email=stu_email).exists()
            stu_em=re.match(evalid,stu_email)
            stu_mob=re.match(mvalid,stu_mobile)
            if institute.is_valid_credit_count() and stu_em and stu_mob and class_section and not stu_exist:                
                if class_section:
                    cas,_cas=_resolve_class_and_section(class_section)
                else:
                    cas=get_object_or_404(ClassAndSection,id=class_section)               

                import random
                password=''.join([str(random.randint(0,10)) for _ in range(6)])                
                user_dict={'name':stu_name,'mobile':stu_mobile,'image':stu_profile,'email':stu_email,'password':password}
                student=User.create_user(**user_dict)
                stu_manage=StudentManagement(institute=institute,student=student,class_and_section=cas)
                stu_manage.save()
                from institute.psychometric_packages import maybe_assign_package_from_post
                maybe_assign_package_from_post(request, institute, student)
                update_student_data.delay(institute.id,institute.name)
                create_student_and_send_mail.delay(stu_manage.id,stu_email,password,institute.name,institute.logo.url)
            else:
                if stu_exist:
                    messages.error(request,"{} Already Exist !!".format(stu_email))
                elif not institute.is_valid_credit_count():
                    messages.error(request,"No remaining credits")
                elif not stu_em:
                    messages.error(request,"{} Invalid Email !!".format(stu_email))
                elif not stu_mob:
                    messages.error(request,"Invalid Mobile Number !!")
                elif not class_section:
                    messages.error(request,"Class Not Selected")
                else:
                    messages.error(request,"Something Went Wrong !!")
        else:
            messages.error(request,"Not saved")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class InstituteCsvStudentCreateView(TemplateView):

    def post(self, request, *args, **kwargs):
        import csv
        import random
        import re

        referer = request.META.get("HTTP_REFERER") or reverse("institute:institutegroupdashboard")
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        raw_inst = (request.POST.get("institute") or "").strip()
        if not raw_inst.isdigit():
            messages.error(request, "Please select an institute before uploading.")
            return HttpResponseRedirect(referer)

        institute = get_object_or_404(Institute, id=int(raw_inst))
        if not user_can_bulk_upload_students_for_institute(request, institute):
            messages.error(
                request,
                "You don't have permission to upload students for this institute.",
            )
            return HttpResponseRedirect(referer)

        from core.ttv2_institute_credits import institute_bulk_upload_block_reason

        _block = institute_bulk_upload_block_reason(institute)
        if _block:
            messages.error(request, _block)
            return HttpResponseRedirect(referer)

        csv_file = request.FILES.get("stu_file")
        if not csv_file:
            messages.error(request, "No file uploaded")
            return HttpResponseRedirect(referer)

        file_content = csv_file.read()
        try:
            csvfile = file_content.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            try:
                csvfile = file_content.decode("utf-8-sig").splitlines()
            except Exception:
                csvfile = file_content.decode("latin-1").splitlines()

        stu_file = csv.reader(csvfile)

        try:
            header_raw = next(stu_file)
            header = [h.strip().lower() for h in header_raw]
        except StopIteration:
            messages.error(request, "CSV file is empty")
            return HttpResponseRedirect(referer)

        required_headers = ["name", "mobile", "class_and_section"]
        missing_headers = [h for h in required_headers if h not in header]
        if missing_headers:
            messages.error(
                request,
                "CSV file is missing required columns: "
                + ", ".join(missing_headers)
                + ". Required columns are: name, mobile, class_and_section. Email is optional.",
            )
            return HttpResponseRedirect(referer)

        error_list = []
        email_list = []
        row_number = 1
        imported_ok = 0
        default_package_code = (request.POST.get('psychometric_package') or '').strip()

        for stu in stu_file:
            row_number += 1
            if not any(stu) or len(stu) == 0:
                continue

            email_list.append(stu)
            stu_d = {
                header[i]: s.strip() if s and s.strip() else None
                for i, s in enumerate(stu)
                if i < len(header)
            }
            stu_name = stu_d.get("name")
            stu_mobile_norm = _normalize_csv_mobile_digits(stu_d.get("mobile"))
            stu_email = stu_d.get("email")
            class_section = stu_d.get("class_and_section")

            if not stu_email:
                random_number = str(random.randint(1000, 9999))
                if stu_name:
                    stu_email = (
                        f"{stu_name.lower().replace(' ', '_')}_{random_number}@yopmail.com"
                    )
                else:
                    stu_email = f"student_{random_number}@yopmail.com"

            if stu_name and stu_email and stu_mobile_norm and class_section:
                stu_exist = User.objects.filter(email=stu_email).exists()
                stu_em = re.match(evalid, stu_email)
                stu_mob_ok = _csv_indian_mobile_ok(stu_mobile_norm)
                if (
                    institute.is_valid_credit_count()
                    and stu_em
                    and stu_mob_ok
                    and class_section
                    and not stu_exist
                ):
                    cas, _cas = _resolve_class_and_section(class_section)

                    password = "".join([str(random.randint(0, 10)) for _ in range(6)])
                    user_dict = {
                        "name": stu_name,
                        "mobile": stu_mobile_norm,
                        "email": stu_email,
                        "password": password,
                    }
                    student = User.create_user(**user_dict)
                    stu_manage = StudentManagement(
                        institute=institute,
                        student=student,
                        class_and_section=cas,
                    )
                    stu_manage.save()
                    package_code = (
                        stu_d.get('package_code')
                        or stu_d.get('psychometric_package')
                        or default_package_code
                        or ''
                    ).strip()
                    from institute.psychometric_packages import try_assign_package_code
                    ok_pkg, pkg_msg = try_assign_package_code(
                        institute, student, package_code, assigned_by=request.user
                    )
                    if not ok_pkg and pkg_msg:
                        messages.error(request, f'{stu_email}: {pkg_msg}')
                    update_student_data.delay(institute.id, institute.name)
                    create_student_and_send_mail.delay(
                        stu_manage.id,
                        stu_email,
                        password,
                        institute.name,
                        _institute_logo_url_safe(institute),
                    )
                    imported_ok += 1
                else:
                    if stu_exist:
                        messages.error(request, "{} Already Exist !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not institute.is_valid_credit_count():
                        messages.error(request, "No remaining credits")
                        error_list.append(stu_email)
                    elif not stu_em:
                        messages.error(request, "{} Invalid Email !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not stu_mob_ok:
                        messages.error(
                            request,
                            "Invalid mobile number (row %s): use 10 digits starting 6–9, or +91 prefix."
                            % row_number,
                        )
                        error_list.append(str(stu_mobile_norm))
                    elif not class_section:
                        messages.error(request, "Class Not Selected")
                        error_list.append(stu_email)
                    else:
                        messages.error(request, "Something Went Wrong !!")
                        error_list.append(stu_email)
            else:
                missing_fields = []
                if not stu_name:
                    missing_fields.append("name")
                if not stu_mobile_norm:
                    missing_fields.append("mobile")
                if not class_section:
                    missing_fields.append("class_and_section")

                error_msg = (
                    f"Row {row_number}: Missing required fields - "
                    + ", ".join(missing_fields)
                )
                messages.error(request, error_msg)
                error_list.append(f"Row {row_number}: {error_msg}")

        create_institute_log.delay(institute.id, error_list, len(email_list))
        if imported_ok:
            messages.success(
                request,
                "Successfully imported %s student(s)." % imported_ok,
            )
        elif email_list:
            messages.error(
                request,
                "No students were imported. Fix the CSV errors above and try again.",
            )

        return HttpResponseRedirect(referer)


# Post-Matric csv upload

def get_gender_value(gender_str):
    if not gender_str:
        return choices.GenderChoices.UNKNOWN
    gender_str = gender_str.strip().lower()
    if gender_str in ['m', 'male']:
        return choices.GenderChoices.MALE
    elif gender_str in ['f', 'female']:
        return choices.GenderChoices.FEMALE
    else:
        return choices.GenderChoices.UNKNOWN
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class InstitutePostMatricCsvStudentCreateView(TemplateView):

    def post(self, request, *args, **kwargs):
        import csv
        import random
        import re

        referer = request.META.get("HTTP_REFERER") or reverse("institute:institutegroupdashboard")
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        raw_inst = (request.POST.get("institute") or "").strip()
        if not raw_inst.isdigit():
            messages.error(request, "Please select an institute before uploading.")
            return HttpResponseRedirect(referer)

        institute = get_object_or_404(Institute, id=int(raw_inst))
        if not user_can_bulk_upload_students_for_institute(request, institute):
            messages.error(
                request,
                "You don't have permission to upload students for this institute.",
            )
            return HttpResponseRedirect(referer)

        from core.ttv2_institute_credits import institute_bulk_upload_block_reason

        _block = institute_bulk_upload_block_reason(institute)
        if _block:
            messages.error(request, _block)
            return HttpResponseRedirect(referer)

        csv_file = request.FILES.get("stu_file")
        if not csv_file:
            messages.error(request, "No file uploaded")
            return HttpResponseRedirect(referer)

        file_content = csv_file.read()
        try:
            csvfile = file_content.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            try:
                csvfile = file_content.decode("utf-8-sig").splitlines()
            except Exception:
                csvfile = file_content.decode("latin-1").splitlines()

        stu_file = csv.reader(csvfile)

        try:
            header_raw = next(stu_file)
            header = [h.strip().lower() for h in header_raw]
        except StopIteration:
            messages.error(request, "CSV file is empty")
            return HttpResponseRedirect(referer)

        required_headers = ["name", "mobile", "class_and_section"]
        missing_headers = [h for h in required_headers if h not in header]
        if missing_headers:
            messages.error(
                request,
                "CSV file is missing required columns: "
                + ", ".join(missing_headers)
                + ". Required columns are: name, mobile, class_and_section. Email and gender are optional.",
            )
            return HttpResponseRedirect(referer)

        error_list = []
        email_list = []
        row_number = 1
        imported_ok = 0
        default_package_code = (request.POST.get('psychometric_package') or '').strip()

        for stu in stu_file:
            row_number += 1
            if not any(stu) or len(stu) == 0:
                continue

            email_list.append(stu)
            stu_d = {
                header[i]: s.strip() if s and s.strip() else None
                for i, s in enumerate(stu)
                if i < len(header)
            }
            stu_name = stu_d.get("name")
            stu_mobile_norm = _normalize_csv_mobile_digits(stu_d.get("mobile"))
            stu_email = stu_d.get("email")
            stu_gender = stu_d.get("gender")
            class_section_stream = stu_d.get("stream")
            class_section = stu_d.get("class_and_section")

            if not stu_email:
                random_number = str(random.randint(1000, 9999))
                if stu_name:
                    stu_email = (
                        f"{stu_name.lower().replace(' ', '_')}_{random_number}@yopmail.com"
                    )
                else:
                    stu_email = f"student_{random_number}@yopmail.com"

            if stu_name and stu_email and stu_mobile_norm and class_section:
                stu_exist = User.objects.filter(email=stu_email).exists()
                stu_em = re.match(evalid, stu_email)
                stu_mob_ok = _csv_indian_mobile_ok(stu_mobile_norm)
                if (
                    institute.is_valid_credit_count()
                    and stu_em
                    and stu_mob_ok
                    and class_section
                    and not stu_exist
                ):
                    cas, _cas = _resolve_class_and_section(class_section, class_section_stream)

                    password = "".join([str(random.randint(0, 10)) for _ in range(6)])
                    user_dict = {
                        "name": stu_name,
                        "mobile": stu_mobile_norm,
                        "email": stu_email,
                        "password": password,
                    }
                    student = User.create_user(**user_dict)
                    user_profile, _created = UserProfile.objects.get_or_create(user=student)
                    if stu_gender:
                        stu_gender_raw = stu_d.get("gender")
                        gv = get_gender_value(stu_gender_raw)
                        user_profile.gender = gv
                        user_profile.save()
                    stu_manage = StudentManagement(
                        institute=institute,
                        student=student,
                        class_and_section=cas,
                    )
                    stu_manage.save()
                    package_code = (
                        stu_d.get('package_code')
                        or stu_d.get('psychometric_package')
                        or default_package_code
                        or ''
                    ).strip()
                    from institute.psychometric_packages import try_assign_package_code
                    ok_pkg, pkg_msg = try_assign_package_code(
                        institute, student, package_code, assigned_by=request.user
                    )
                    if not ok_pkg and pkg_msg:
                        messages.error(request, f'{stu_email}: {pkg_msg}')
                    update_student_data.delay(institute.id, institute.name)
                    create_student_and_send_mail.delay(
                        stu_manage.id,
                        stu_email,
                        password,
                        institute.name,
                        _institute_logo_url_safe(institute),
                    )
                    imported_ok += 1
                else:
                    if stu_exist:
                        messages.error(request, "{} Already Exist !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not institute.is_valid_credit_count():
                        messages.error(request, "No remaining credits")
                        error_list.append(stu_email)
                    elif not stu_em:
                        messages.error(request, "{} Invalid Email !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not stu_mob_ok:
                        messages.error(
                            request,
                            "Invalid mobile number (row %s): use 10 digits starting 6–9, or +91 prefix."
                            % row_number,
                        )
                        error_list.append(str(stu_mobile_norm))
                    elif not class_section:
                        messages.error(request, "Class Not Selected")
                        error_list.append(stu_email)
                    else:
                        messages.error(request, "Something Went Wrong !!")
                        error_list.append(stu_email)
            else:
                missing_fields = []
                if not stu_name:
                    missing_fields.append("name")
                if not stu_mobile_norm:
                    missing_fields.append("mobile")
                if not class_section:
                    missing_fields.append("class_and_section")

                error_msg = (
                    f"Row {row_number}: Missing required fields - "
                    + ", ".join(missing_fields)
                )
                messages.error(request, error_msg)
                error_list.append(f"Row {row_number}: {error_msg}")

        create_institute_log.delay(institute.id, error_list, len(email_list))
        if imported_ok:
            messages.success(
                request,
                "Successfully imported %s student(s)." % imported_ok,
            )
        elif email_list:
            messages.error(
                request,
                "No students were imported. Fix the CSV errors above and try again.",
            )

        return HttpResponseRedirect(referer)



@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_update_delete_student_only,name='dispatch')
class InstituteStudentUpdateView(TemplateView):
    def post(self, request, *args, **kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        mvalid = r'^(\+91|0)?[6789]\d{9}$'
        id=request.POST.get("user_id")
        
        print("id",id)
        user=get_object_or_404(User,id=id)
        upd_name=request.POST.get("upd_name")
        upd_email=request.POST.get("upd_email")
        upd_class=request.POST.get("class_section")
        upd_mobile=request.POST.get("upd_mobile")
        upd_profile_pic=request.FILES.get("upd_profile_pic")
        upd_em=re.match(evalid,upd_email)
        upd_mob=re.match(mvalid,upd_mobile)
        upd_exist=User.objects.filter(email=upd_email).exists()
        if (upd_name or upd_em or upd_mob or upd_profile_pic or upd_class):
            if upd_name:
                user.name=upd_name
            if upd_em and not upd_exist:         
                user.email=upd_email
            if upd_mob:
                user.mobile=upd_mobile
            if upd_profile_pic:
                user.image=upd_profile_pic
            if upd_class:
                stu=get_object_or_404(StudentManagement,student=user)
                cas=get_object_or_404(ClassAndSection,id=upd_class)
                stu.class_and_section=cas
                stu.save()
            user.save()
        else:
            if upd_exist:
                messages.error(request,"Try another email")
            else:
                messages.error(request,"Something Went Wrong !!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_update_delete_student_only,name='dispatch')
class InstituteStudentDeleteView(TemplateView):
    def post(self, request, *args, **kwargs):

        
        id=request.POST.get("user_id")
        user=get_object_or_404(User,id=id)
        stu_manage=get_object_or_404(StudentManagement,student=user)
        stu_manage.delete()
        user.delete()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_change_student_password_only,name='dispatch')  
class InstituteStudentChangePasswordView(TemplateView):
    def post(self, request, *args, **kwargs):
        id=request.POST.get("password_id")
        password=request.POST.get("change_password")
        user=get_object_or_404(User,id=id)
        user.set_password(password)
        user.save()
        send_new_student_credential.delay(user.email,password)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(change_counselor_password_only,name='dispatch')  
class CounselorChangePasswordView(TemplateView):
    def post(self, request, *args, **kwargs):
        cid = (
            request.POST.get("counselor_id")
            or request.POST.get("coun_password_id")
            or request.POST.get("password_id")
        )
        counselor = get_object_or_404(Counselor, id=cid)
        new_password = (
            request.POST.get("new_password")
            or request.POST.get("change_password")
            or ""
        ).strip()
        confirm = (
            request.POST.get("confirm_password")
            or request.POST.get("change_password")
            or ""
        ).strip()
        if len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")
        if new_password != confirm:
            messages.error(request, "Passwords do not match.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")
        coun_user = counselor.coun_user
        if not coun_user:
            messages.error(request, "Counselor has no login user.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")
        coun_user.set_password(new_password)
        coun_user.save()
        messages.success(request, "Password updated.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER') or "/")


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(institute_group_user_only, name='dispatch')
class InstituteGroupBulkAssignCounselorView(View):
    """POST JSON { counselor_id }: clone/link counselor identity to every institute in the group."""

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}
        try:
            cid = int(payload.get("counselor_id"))
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_counselor"}, status=400)
        src = get_object_or_404(Counselor, id=cid)
        if not _counselor_belongs_to_institute_group_admin(src, request.user):
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        institutes = Institute.objects.filter(
            institute_group__institute_group_admin=request.user
        ).distinct()
        canon_pk = _canonical_counselor_row(src).pk
        created = 0
        reused = 0
        with transaction.atomic():
            for ins in institutes.iterator():
                canon = Counselor.objects.get(pk=canon_pk)
                before = canon.serves_institute(ins)
                _ensure_counselor_clone_for_institute(canon, ins)
                if before:
                    reused += 1
                else:
                    created += 1
        return JsonResponse({"ok": True, "created": created, "reused": reused})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(institute_group_user_only, name='dispatch')
class InstituteGroupInstituteCounselorView(View):
    """POST JSON assign/unassign counselor on one institute."""

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}
        action = (payload.get("action") or "").strip().lower()
        slug = (payload.get("institute_slug") or "").strip()
        institute = get_object_or_404(Institute, slug=slug)
        if getattr(institute.institute_group, "institute_group_admin_id", None) != request.user.id:
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

        if action == "assign":
            try:
                cid = int(payload.get("counselor_id"))
            except Exception:
                return JsonResponse({"ok": False, "error": "invalid_counselor"}, status=400)
            src = get_object_or_404(Counselor, id=cid)
            if not _counselor_belongs_to_institute_group_admin(src, request.user):
                return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
            row = _ensure_counselor_clone_for_institute(src, institute)
            return JsonResponse(
                {
                    "ok": True,
                    "counselor_id": row.id,
                    "counselor_name": row.counselor_name or "",
                }
            )

        if action == "unassign":
            try:
                cid = int(payload.get("counselor_id"))
            except Exception:
                return JsonResponse({"ok": False, "error": "invalid_counselor"}, status=400)
            coun = get_object_or_404(Counselor.qs_for_institute(institute), id=cid)
            if not _counselor_belongs_to_institute_group_admin(coun, request.user):
                return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
            if coun.students.exists():
                return JsonResponse(
                    {"ok": False, "error": "students_assigned"},
                    status=400,
                )

            gid = getattr(institute, "institute_group_id", None)
            group_inst_ids = list(
                Institute.objects.filter(institute_group_id=gid).values_list(
                    "id", flat=True
                )
            )
            assigned = (
                _counselor_group_assigned_institute_ids(coun, group_inst_ids)
                if group_inst_ids
                else set()
            )

            uid_chk = coun.coun_user_id
            email_chk = (coun.counselor_email or "").strip()
            if (uid_chk or email_chk) and group_inst_ids and len(assigned) <= 1:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "last_placement",
                        "message": (
                            "This advisor must stay linked to at least one institute "
                            "in your group. Assign them to another school first, then "
                            "remove them from this one."
                        ),
                    },
                    status=400,
                )

            ig = getattr(institute, "institute_group", None)
            with transaction.atomic():
                if coun.counselor_admin_id != institute.id:
                    coun.institute_placements.remove(institute)
                elif len(assigned) > 1:
                    others = sorted(x for x in assigned if x != institute.id)
                    new_primary = Institute.objects.get(pk=others[0])
                    coun.counselor_admin = new_primary
                    if coun.institute_placements.filter(pk=new_primary.pk).exists():
                        coun.institute_placements.remove(new_primary)
                    coun.save(update_fields=["counselor_admin"])
                else:
                    StudentManagement.objects.filter(counselor=coun).update(counselor=None)
                    coun.students.clear()
                    if group_inst_ids:
                        g_pl = list(
                            coun.institute_placements.filter(pk__in=group_inst_ids)
                        )
                        if g_pl:
                            coun.institute_placements.remove(*g_pl)
                    coun.counselor_admin = None
                    coun.detached_from_institute_group = ig
                    coun.save(
                        update_fields=[
                            "counselor_admin",
                            "detached_from_institute_group",
                        ]
                    )
            return JsonResponse({"ok": True, "counselor_id": cid})

        return JsonResponse({"ok": False, "error": "bad_action"}, status=400)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class InstituteGroupCounselorProfileUpdateView(View):
    """POST form: edit counselor profile (institute owner or institute-group admin)."""

    def post(self, request, *args, **kwargs):
        try:
            cid = int(request.POST.get("counselor_id"))
        except Exception:
            messages.error(request, "Invalid counselor.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")
        counselor = get_object_or_404(Counselor, id=cid)
        if not _counselor_profile_editable_by_user(request.user, counselor):
            messages.error(request, "Not allowed.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")
        name = (request.POST.get("counselor_name") or "").strip()
        address = (request.POST.get("counselor_address") or "").strip()
        contact = (request.POST.get("counselor_contact_info") or "").strip()
        education = (request.POST.get("counselor_education") or "").strip()
        if name:
            counselor.counselor_name = name[:250]
        counselor.counselor_address = address[:350] if address else None
        counselor.counselor_contact_info = contact[:250] if contact else None
        counselor.counselor_education = education[:250] if education else None
        counselor.save(
            update_fields=[
                "counselor_name",
                "counselor_address",
                "counselor_contact_info",
                "counselor_education",
            ]
        )
        messages.success(request, "Counselor updated.")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_block_student_only,name='dispatch')  
class InstituteStudentBlockView(TemplateView):
    def get(self,request,*args,**kwargs):
        id=kwargs.get("id")
        stu=get_object_or_404(User,id=id)
        if stu.user_status==choices.UserStatus.UNBLOCK:
            stu.user_status=choices.UserStatus.BLOCK
            stu.save()
        else:
            stu.user_status=choices.UserStatus.UNBLOCK
            stu.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class UpdateSeatCapacityView(View):
    """View to update seat capacity for an institute via AJAX"""
    
    def post(self, request, *args, **kwargs):
        try:
            institute_id = request.POST.get('institute_id')
            pcm = request.POST.get('pcm')
            cbm = request.POST.get('cbm')
            comm = request.POST.get('comm')
            hme = request.POST.get('hme')
            hmb = request.POST.get('hmb')
            
            if not institute_id:
                return JsonResponse({'success': False, 'error': 'Institute ID is required'}, status=400)
            
            # Get the institute
            institute = get_object_or_404(Institute, id=institute_id)
            
            # Verify the institute belongs to the user's marketing group
            group_admin = request.user
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=group_admin
            ).first()
            
            if not marketing_group or institute.marketing_group != marketing_group:
                return JsonResponse({'success': False, 'error': 'Unauthorized access'}, status=403)
            
            # Update seat capacity fields
            if pcm is not None:
                institute.pcm = int(pcm)
            if cbm is not None:
                institute.cbm = int(cbm)
            if comm is not None:
                institute.comm = int(comm)
            if hme is not None:
                institute.hme = int(hme)
            if hmb is not None:
                institute.hmb = int(hmb)
            
            institute.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Seat capacity updated successfully',
                'data': {
                    'pcm': institute.pcm,
                    'cbm': institute.cbm,
                    'comm': institute.comm,
                    'hme': institute.hme,
                    'hmb': institute.hmb
                }
            })
            
        except ValueError as e:
            return JsonResponse({'success': False, 'error': f'Invalid value: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch') 
class InstituteProfileEditView(TemplateView):
    def post(self,request,*args,**kwargs):
        ins_id=request.POST.get("institute_id")
        ins_name=request.POST.get("institute_name")
        ins_address=request.POST.get("institute_address")
        ins_contact=request.POST.get("institute_contact")
        ins_admin=request.POST.get("institute_admin")
        ins_credits=request.POST.get("upd_credits")
        ins_group=request.POST.get("institute_group")
        ins_logo=request.FILES.get("institute_logo")
        ins=get_object_or_404(Institute,id=ins_id)
        if ins_name or ins_address or ins_contact or ins_admin or ins_logo or ins_credits or ins_group:
            if ins_name:
                update_student_data.delay(ins.id,ins_name)
                ins.name=ins_name
            if ins_address:
                ins.address=ins_address
            if ins_contact:
                ins.contact_info=ins_contact
            if ins_admin:
                ins.administrator_contact=ins_admin
            if ins_credits and (0<=int(ins_credits)<=(ins.credit_counts+get_global_remain_credits())):
                ins.credit_counts=ins_credits
            if ins_group:
                institute_group=get_object_or_404(InstituteGroup,id=ins_group)
                ins.institute_group=institute_group
            if ins_logo:
                ins.logo=ins_logo
            ins.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_profile_update_delete,name='dispatch') 
class InstituteDeletionView(TemplateView):
    def post(self,request,*args,**kwargs):
        ins_id=request.POST.get("institute_id")
        ins=get_object_or_404(Institute,id=ins_id)
        ins_reason=request.POST.get("ins_reason")
        if ins and ins_reason:
            ins_del=InstituteAccountDeletion(institute=ins,reason=ins_reason)
            ins_del.save()
            institute_deletion_request.delay(ins_id,ins.name,ins_reason)
            messages.success(request, "Sent Account Deletion Request")
        else:
            messages.error(request,"Something Went Wrong !!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class CreateClassSectionView(TemplateView):
    def post(self,request,*args,**kwargs):
        cl=request.POST.get("create_class")
        cas=ClassAndSection(class_and_section=cl)
        cas.save()
        messages.success(request, "New Class Created")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_authenticated_user_only,name='dispatch')
class InstituteHistoryLogView(TemplateView):
    # Uses the v2 dashboard shell (sidebar + topbar) — legacy template removed.
    template_name = "template_v2/institute/institute_history_log.html"

    def html_head(self):
        name = 'Institute Logs'
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        institute = Institute.objects.filter(slug=slug).first() if slug else None
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["institute"] = institute
        ctx["institute_logs"] = InstituteLog.objects.filter(institute__slug=slug).order_by("-created")
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(marketing_group_user_only, name='dispatch')
class MarketingGroupHeatmapView(TemplateView):
    """
    Dedicated Heatmap page for Marketing Group users.
    Reuses the same heatmap UI/JS as the dashboard, but on its own page.
    """
    template_name = "template20/institute/marketing_group_heatmap.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/marketing_group_heatmap.html",
                "template_v2/institute/marketing_group_heatmap.html",
            )
        ]

    def html_head(self):
        name = "Heatmap | Marketing Group"
        return build_html_head(title=name, description=name)

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        try:
            template_version = (
                Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
            ).strip()
        except Exception:
            template_version = "v1"
        if template_version == "v2" and request_wants_ttv2_dashboard_body_partial(request):
            return render(request, "template_v2/institute/marketing_group_heatmap_body.html", ctx)
        return render(request, _dashboard_primary_template_name(self), ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["html_head"] = self.html_head()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
@method_decorator(institute_group_user_only, name="dispatch")
class InstituteGroupHeatmapView(TemplateView):
    """Dedicated heatmap page for institute-group admins (aggregated group data)."""

    template_name = "template20/institute/institute_group_heatmap.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_group_heatmap.html",
                "template_v2/institute/institute_group_heatmap.html",
            )
        ]

    def html_head(self):
        name = "Heatmap | Institute Group"
        return build_html_head(title=name, description=name)

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        try:
            template_version = (
                Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
            ).strip()
        except Exception:
            template_version = "v1"
        if template_version == "v2" and request_wants_ttv2_dashboard_body_partial(request):
            return render(request, "template_v2/institute/institute_group_heatmap_body.html", ctx)
        return render(request, _dashboard_primary_template_name(self), ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["html_head"] = self.html_head()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
@method_decorator(institute_authenticated_user_only, name="dispatch")
class InstituteHeatmapView(TemplateView):
    """Dedicated heatmap page for a single institute (scoped by URL slug)."""

    template_name = "template20/institute/institute_heatmap.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_heatmap.html",
                "template_v2/institute/institute_heatmap.html",
            )
        ]

    def html_head(self):
        return build_html_head(
            title="Heatmap | Institute",
            description="Career education analytics heatmap.",
        )

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        try:
            template_version = (
                Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
            ).strip()
        except Exception:
            template_version = "v1"
        # v2 uses the unified institute dashboard pages (so sidebar AJAX nav works everywhere).
        if template_version == "v2":
            try:
                return redirect(
                    "institute:institutedashboard_page",
                    slug=kwargs.get("slug"),
                    page="heatmap",
                )
            except Exception:
                pass
        if template_version == "v2" and request_wants_ttv2_dashboard_body_partial(request):
            return render(request, "template_v2/institute/institute_heatmap_body.html", ctx)
        return render(request, _dashboard_primary_template_name(self), ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")
        ctx["institute"] = get_object_or_404(Institute, slug=slug)
        ctx["html_head"] = self.html_head()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class StudentData(APIView):
    def post(self,request,*args,**kwargs):
        id=request.POST.get("id")
        stu = StudentManagement.objects.filter(student__id=id).select_related(
            'institute', 'student', 'class_and_section'
        ).first()
        if not stu:
            return JsonResponse({"success": "false", "error": "Not found"}, status=404)
        if not user_manages_institute_for_api(request.user, stu.institute):
            return JsonResponse({"success": "false", "error": "Forbidden"}, status=403)
        if stu.class_and_section is not None:
            response={"success":"true","name":stu.student.name,"email":stu.student.email,"mobile":stu.student.mobile,"class_id":stu.class_and_section.id,"class":stu.class_and_section.class_and_section}
        else:
            response={"success":"true","name":stu.student.name,"email":stu.student.email,"mobile":stu.student.mobile,"class":"Not Selected"}
        return JsonResponse(response)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class InstituteData(APIView):
    def post(self,request,*args,**kwargs):
        id=request.POST.get("id")
        ins = Institute.objects.filter(id=id).select_related(
            'institute_group', 'marketing_group', 'created_by'
        ).first()
        if not ins:
            return JsonResponse({"success": "false", "error": "Not found"}, status=404)
        if not user_manages_institute_for_api(request.user, ins):
            return JsonResponse({"success": "false", "error": "Forbidden"}, status=403)
        response={"success":"true","name":ins.name,"address":ins.address,"contact_info":ins.contact_info,"admin_contact":ins.administrator_contact,"credits":ins.credit_counts}
        if ins.institute_group:
            response["ins_group"]=ins.institute_group.group_name
            response["ins_group_id"]=ins.institute_group.id
        return JsonResponse(response)
    
def students_csv_sample_file(request):
    import os
    try:
        # Try multiple possible locations for the CSV file
        base_dir = settings.BASE_DIR
        possible_paths = [
            os.path.join(base_dir, "student_sample_data.csv"),
            os.path.join(base_dir, "scripts", "student_sample_data.csv"),
            os.path.join(base_dir, "static", "student_sample_data.csv"),
            os.path.join(base_dir, "demo-topteens", "student_sample_data.csv"),
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            # Create a sample CSV if file doesn't exist
            sample_content = "Email,Name,Mobile,class_and_section\nstudent1@example.com,Student One,9876543210,10th A\nstudent2@example.com,Student Two,9876543211,10th B"
            response = HttpResponse(sample_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Student sample data.csv"'
            return response
        
        with open(file_path, 'r', encoding='utf-8') as file:
            response = HttpResponse(file.read(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Student sample data.csv"'
            return response
    except Exception as e:
        print("---Error downloading student sample CSV----", e)
        # Return a basic sample CSV even if file read fails
        sample_content = "Email,Name,Mobile,class_and_section\nstudent1@example.com,Student One,9876543210,10th A\nstudent2@example.com,Student Two,9876543211,10th B"
        response = HttpResponse(sample_content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="Student sample data.csv"'
        return response
    
def post_matric_student_sample_data(request):
    import os
    try:
        # Try multiple possible locations for the CSV file
        base_dir = settings.BASE_DIR
        possible_paths = [
            os.path.join(base_dir, "post_matric_student_sample_data.csv"),
            os.path.join(base_dir, "scripts", "post_matric_student_sample_data.csv"),
            os.path.join(base_dir, "static", "post_matric_student_sample_data.csv"),
            os.path.join(base_dir, "demo-topteens", "post_matric_student_sample_data.csv"),
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            # Create a sample CSV if file doesn't exist
            sample_content = "Email,Name,Mobile,class_and_section,Stream,Gender\nstudent1@example.com,Student One,9876543210,11th,PCM,M\nstudent2@example.com,Student Two,9876543211,12th,COMM,F"
            response = HttpResponse(sample_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Post Matric Student sample data.csv"'
            return response
        
        with open(file_path, 'r', encoding='utf-8') as file:
            response = HttpResponse(file.read(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Post Matric Student sample data.csv"'
            return response
    except Exception as e:
        print("---Error downloading post-matric sample CSV----", e)
        # Return a basic sample CSV even if file read fails
        sample_content = "Email,Name,Mobile,class_and_section,Stream,Gender\nstudent1@example.com,Student One,9876543210,11th,PCM,M\nstudent2@example.com,Student Two,9876543211,12th,COMM,F"
        response = HttpResponse(sample_content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="Post Matric Student sample data.csv"'
        return response
    
# def CounselorDashboard(request):    
#     return render(request, 'topteenfrontend/user/app/counselor_dashboard.html')

# def CounselorCourse(request):    
#     return render(request, 'topteenfrontend/user/app/counselor-course.html')

# old code not in use - start
# New isolated views for institute authentication frontend
# old code not in use - end

class InstituteRegisterView(TemplateView):
    """
    View to render institute registration page
    """
    template_name = 'institute/register.html'
    
    def html_head(self):
        name = 'Institute Registration'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
        # old code not in use - start
        # Add marketing groups and institute types for dropdowns
        # old code not in use - end
        from institute.models import InstituteMarketingGroup
        context['marketing_groups'] = InstituteMarketingGroup.objects.all()
        context['institute_types'] = choices.InstituteType.CHOICES
        return context


class InstituteLoginView(TemplateView):
    """
    View to render institute login page
    """
    template_name = 'institute/login.html'
    
    def html_head(self):
        name = 'Institute Login'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
        from users.demo_accounts import (
            get_demo_institute_login_context,
            empty_demo_login_context,
            should_show_demo_accounts,
        )

        if should_show_demo_accounts():
            context.update(get_demo_institute_login_context(self.request))
        else:
            context.update(empty_demo_login_context())
        return context


# old code not in use - start
# New isolated views for marketing authentication frontend
# old code not in use - end

class MarketingRegisterView(TemplateView):
    """
    View to render marketing registration page
    """
    template_name = 'marketing/register.html'
    
    def html_head(self):
        name = 'Marketing Registration'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
        return context


class MarketingLoginView(TemplateView):
    """
    View to render marketing login page
    """
    template_name = 'marketing/login.html'
    
    def html_head(self):
        name = 'Marketing Login'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
        from users.demo_accounts import (
            get_demo_login_context,
            empty_demo_login_context,
            should_show_demo_accounts,
        )
        from core import choices

        if should_show_demo_accounts():
            context.update(get_demo_login_context(
                self.request,
                user_types=[choices.UserType.MARKETINGGROUPADMIN],
            ))
        else:
            context.update(empty_demo_login_context())
        return context


@login_required(login_url=reverse_lazy('users:login'))
def get_heatmap_data_api(request):
    """
    API endpoint to get heatmap data for institute, marketing group, or individual institute
    """
    try:
        user = request.user
        demographic_type = request.GET.get('demographic_type', 'grade')  # grade, section, or stream
        institute_slug = request.GET.get('institute_slug', None)  # For individual institute
        
        # If institute_slug is provided, get data for that specific institute
        if institute_slug:
            try:
                institute = Institute.objects.get(slug=institute_slug)
                # Verify user has access to this institute
                if not (institute.created_by == user or 
                       (institute.institute_group and institute.institute_group.institute_group_admin == user) or
                       (institute.marketing_group and institute.marketing_group.marketing_group_admin == user)):
                    return JsonResponse({'error': 'Unauthorized access to institute'}, status=403)
                
                heatmap_data = get_heatmap_data_for_institute(institute, demographic_type)
                return JsonResponse(heatmap_data, safe=False)
            except Institute.DoesNotExist:
                return JsonResponse({'error': 'Institute not found'}, status=404)
        
        # Otherwise, check for group admin
        # Check if user is institute group admin
        institute_group = InstituteGroup.objects.filter(institute_group_admin=user).first()
        if institute_group:
            group_type = 'institute'
        else:
            # Check if user is marketing group admin
            marketing_group = InstituteMarketingGroup.objects.filter(marketing_group_admin=user).first()
            if marketing_group:
                group_type = 'marketing'
            else:
                # Check if user is an institute user (individual institute)
                institute = Institute.objects.filter(created_by=user).first()
                if institute:
                    heatmap_data = get_heatmap_data_for_institute(institute, demographic_type)
                    return JsonResponse(heatmap_data, safe=False)
                # Marketing / institute-group dashboards load this API before an org row may exist
                ut = getattr(user, 'user_type', None)
                if ut == choices.UserType.MARKETINGGROUPADMIN or ut == choices.UserType.INSTITUTEGROUPADMIN:
                    return JsonResponse(get_empty_heatmap_data(), safe=False)
                return JsonResponse({'error': 'User is not authorized'}, status=403)
        
        # Get heatmap data for group
        heatmap_data = get_heatmap_data_for_group(user, group_type, demographic_type)
        
        return JsonResponse(heatmap_data, safe=False)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)