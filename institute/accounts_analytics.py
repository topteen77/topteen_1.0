"""
Role-specific accounts / business analytics for marketing, institute, and group admins.
"""
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from core import choices
from institute.models import (
    Institute,
    InstituteDiscountCoupon,
    InstituteTieUpLineItem,
    InstituteTieUpOrder,
)
from institute.tieup_billing import (
    _coupon_display_label,
    _PRODUCT_LABELS,
    list_applicable_coupons,
)

PRODUCT_FILTER_KEYS = {
    "all": None,
    "psychometric": choices.TieUpProductType.STUDENT_TEST_CREDITS,
    "counselor_seats": choices.TieUpProductType.COUNSELOR_COURSE_SEATS,
    "career_readiness": choices.TieUpProductType.CAREER_READINESS_SKILLLAB,
}

PRODUCT_FILTER_LABELS = {
    "all": "All products",
    "psychometric": "Psychometric / test credits",
    "counselor_seats": "Counsellor Course",
    "career_readiness": "College & Career Readiness",
}

PERIOD_LABELS = {
    "this_month": "This month",
    "6months": "Past 6 months",
    "lifetime": "Lifetime",
    "custom": "Custom range",
    "30days": "Last 30 days",
    "90days": "Last 90 days",
}


def parse_accounts_period(request, default="this_month"):
    """Return (period_key, start_dt, end_dt, label)."""
    period = (request.GET.get("period") or default).strip().lower()
    now = timezone.now()
    end = now

    if period == "custom":
        raw_from = (request.GET.get("date_from") or "").strip()
        raw_to = (request.GET.get("date_to") or "").strip()
        start = end = None
        try:
            if raw_from:
                start = timezone.make_aware(
                    datetime.strptime(raw_from, "%Y-%m-%d").replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                )
            if raw_to:
                end = timezone.make_aware(
                    datetime.strptime(raw_to, "%Y-%m-%d").replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    )
                )
        except (TypeError, ValueError):
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not start:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label = PERIOD_LABELS["custom"]
        if raw_from and raw_to:
            label = "{} – {}".format(raw_from, raw_to)
        return period, start, end, label

    if period == "this_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return period, start, end, PERIOD_LABELS["this_month"]

    if period == "6months":
        start = now - timedelta(days=183)
        return period, start, end, PERIOD_LABELS["6months"]

    if period == "lifetime" or period == "alltime":
        return "lifetime", None, None, PERIOD_LABELS["lifetime"]

    if period == "30days":
        return period, now - timedelta(days=30), end, PERIOD_LABELS.get("30days", "Last 30 days")

    if period == "90days":
        return period, now - timedelta(days=90), end, PERIOD_LABELS.get("90days", "Last 90 days")

    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return "this_month", start, end, PERIOD_LABELS["this_month"]


def _parse_product_filter(request):
    key = (request.GET.get("product") or "all").strip().lower()
    if key not in PRODUCT_FILTER_KEYS:
        key = "all"
    return key, PRODUCT_FILTER_KEYS[key]


def _filter_line_qs(qs, start, end, product_type):
    if start is not None:
        qs = qs.filter(created__gte=start, created__lte=end)
    if product_type is not None:
        qs = qs.filter(product_type=product_type)
    return qs


def _decimal_sum(val):
    return Decimal(str(val or 0)).quantize(Decimal("0.01"))


def _aggregate_tieup_lines(line_qs):
    """KPIs and per-product rows from tie-up line items."""
    received_qs = line_qs.filter(payment_status=choices.TieUpPaymentStatus.RECEIVED)
    pending_qs = line_qs.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    failed_qs = line_qs.filter(payment_status=choices.TieUpPaymentStatus.FAILED)

    collected = _decimal_sum(received_qs.aggregate(t=Sum("total_amount"))["t"])
    pending_business = _decimal_sum(pending_qs.aggregate(t=Sum("total_amount"))["t"])
    failed_amount = _decimal_sum(failed_qs.aggregate(t=Sum("total_amount"))["t"])

    product_rows = []
    for pt, label in choices.TieUpProductType.CHOICES:
        base = line_qs.filter(product_type=pt)
        rec = base.filter(payment_status=choices.TieUpPaymentStatus.RECEIVED)
        pen = base.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
        product_rows.append(
            {
                "product_type": pt,
                "product": label,
                "filter_key": next(
                    (k for k, v in PRODUCT_FILTER_KEYS.items() if v == pt),
                    "all",
                ),
                "qty_sold": int(
                    rec.aggregate(t=Sum("quantity"))["t"] or 0
                ),
                "qty_pending": int(pen.aggregate(t=Sum("quantity"))["t"] or 0),
                "revenue": str(_decimal_sum(rec.aggregate(t=Sum("total_amount"))["t"])),
                "pending": str(_decimal_sum(pen.aggregate(t=Sum("total_amount"))["t"])),
            }
        )

    return {
        "collected": str(collected),
        "pending_business": str(pending_business),
        "failed_amount": str(failed_amount),
        "success_count": received_qs.count(),
        "pending_count": pending_qs.count(),
        "failed_count": failed_qs.count(),
        "product_rows": product_rows,
    }


def _monthly_tieup_trend(institute_ids, months=6):
    """Last N months collected revenue (received lines)."""
    now = timezone.now()
    out = []
    for i in range(months - 1, -1, -1):
        d = now - timedelta(days=30 * i)
        y, m = d.year, d.month
        last_day = monthrange(y, m)[1]
        start = timezone.make_aware(datetime(y, m, 1, 0, 0, 0))
        end = timezone.make_aware(datetime(y, m, last_day, 23, 59, 59))
        qs = InstituteTieUpLineItem.objects.filter(
            order__institute_id__in=institute_ids,
            payment_status=choices.TieUpPaymentStatus.RECEIVED,
            created__gte=start,
            created__lte=end,
        )
        amt = _decimal_sum(qs.aggregate(t=Sum("total_amount"))["t"])
        out.append(
            {
                "label": start.strftime("%b %Y"),
                "amount": str(amt),
                "amount_float": float(amt),
            }
        )
    return out


def _student_payment_breakdown(institute_ids, start, end, product_key):
    """B2C payments from students under scoped institutes."""
    from payments.models import Payment
    from psychometric_tests.models import PsychometricTestPayment
    from skilllab.models import SkilllabCoursePayment

    try:
        from institute.models import StudentManagement

        uids = list(
            StudentManagement.objects.filter(institute_id__in=institute_ids)
            .values_list("student_id", flat=True)
            .distinct()
        )
        uids = [int(x) for x in uids if x]
    except Exception:
        uids = []

    if not uids:
        return []

    def _date_filter(qs):
        if start is None:
            return qs
        return qs.filter(created__gte=start, created__lte=end)

    rows = []

    def _row(name, key, success_qs, pending_qs=None):
        rev = _decimal_sum(success_qs.aggregate(t=Sum("amount"))["t"])
        cnt = success_qs.count()
        pend = 0
        if pending_qs is not None:
            pend = pending_qs.count()
        return {
            "name": name,
            "filter_key": key,
            "qty_sold": cnt,
            "revenue": str(rev),
            "pending_count": pend,
        }

    if product_key in ("all", "psychometric"):
        ptp_ok = _date_filter(
            PsychometricTestPayment.objects.filter(
                user_id__in=uids, is_success=choices.YesNoChoices.YES
            )
        )
        ptp_no = _date_filter(
            PsychometricTestPayment.objects.filter(
                user_id__in=uids, is_success=choices.YesNoChoices.NO
            )
        )
        rows.append(_row("Psychometric tests (students)", "psychometric", ptp_ok, ptp_no))

    if product_key in ("all", "career_readiness"):
        slp_ok = _date_filter(
            SkilllabCoursePayment.objects.filter(
                user_id__in=uids, is_success=choices.YesNoChoices.YES
            )
        )
        slp_no = _date_filter(
            SkilllabCoursePayment.objects.filter(
                user_id__in=uids, is_success=choices.YesNoChoices.NO
            )
        )
        rows.append(_row("Skilllab / career courses (students)", "career_readiness", slp_ok, slp_no))

    if product_key in ("all", "counselor_seats"):
        pay_ok = _date_filter(
            Payment.objects.filter(
                user_id__in=uids,
                is_success=choices.YesNoChoices.YES,
                obj_type=choices.PaymentObjectType.COUNSELOR,
            )
        )
        pay_no = _date_filter(
            Payment.objects.filter(
                user_id__in=uids,
                is_success=choices.YesNoChoices.NO,
                obj_type=choices.PaymentObjectType.COUNSELOR,
            )
        )
        rows.append(_row("Counselor courses (students)", "counselor_seats", pay_ok, pay_no))

    return rows


def list_marketing_coupons(marketing_user):
    """Coupons created under marketing scope — show created & used counts."""
    from django.db.models import Q

    qs = (
        InstituteDiscountCoupon.objects.filter(
            Q(institute__marketing_group__marketing_group_admin=marketing_user)
            | Q(marketing_group__marketing_group_admin=marketing_user)
        )
        .select_related("institute")
        .order_by("-created")
    )
    out = []
    for c in qs[:200]:
        max_uses = c.max_uses
        used = int(c.times_used or 0)
        remaining = None
        if max_uses is not None:
            remaining = max(0, int(max_uses) - used)
        out.append(
            {
                "code": c.code,
                "label": _coupon_display_label(c),
                "institute_name": c.institute.name,
                "institute_slug": c.institute.slug,
                "is_active": c.is_active,
                "times_used": used,
                "max_uses": max_uses,
                "uses_remaining": remaining,
                "created": c.created,
            }
        )
    return out


def list_institute_coupons(institute, pending_line_objs=None):
    """Available (applicable now) and used coupons for institute portal."""
    pending_line_objs = pending_line_objs or []
    applicable = list_applicable_coupons(institute, pending_line_objs)
    applicable_codes = {c["code"] for c in applicable}

    all_coupons = InstituteDiscountCoupon.objects.filter(institute=institute).order_by("code")
    available = []
    used_list = []
    for c in all_coupons:
        max_uses = c.max_uses
        times_used = int(c.times_used or 0)
        at_limit = max_uses is not None and times_used >= max_uses
        row = {
            "code": c.code,
            "label": _coupon_display_label(c),
            "is_active": c.is_active,
            "times_used": times_used,
            "max_uses": max_uses,
            "applicable_now": c.code in applicable_codes and c.is_active and not at_limit,
        }
        if c.is_active and not at_limit:
            available.append(row)
        if times_used > 0:
            used_list.append(row)
    return available, used_list


def build_marketing_accounts_ctx(marketing_user, request):
    institutes = Institute.objects.filter(
        marketing_group__marketing_group_admin=marketing_user
    )
    institute_ids = list(institutes.values_list("id", flat=True))
    period, start, end, period_label = parse_accounts_period(request)
    product_key, product_type = _parse_product_filter(request)

    line_qs = InstituteTieUpLineItem.objects.filter(
        order__institute_id__in=institute_ids
    ).select_related("order", "order__institute", "payment")
    line_qs = _filter_line_qs(line_qs, start, end, product_type)
    tieup = _aggregate_tieup_lines(line_qs)

    student_rows = _student_payment_breakdown(institute_ids, start, end, product_key)

    monthly = _monthly_tieup_trend(institute_ids, months=6)
    trend_max = max((m["amount_float"] for m in monthly), default=1.0) or 1.0

    return {
        "role": "marketing",
        "period": period,
        "period_label": period_label,
        "product_key": product_key,
        "product_filter_labels": PRODUCT_FILTER_LABELS,
        "trend_max": trend_max,
        "date_from": (request.GET.get("date_from") or "").strip(),
        "date_to": (request.GET.get("date_to") or "").strip(),
        "tieup": tieup,
        "student_rows": student_rows,
        "monthly_trend": monthly,
        "coupons": list_marketing_coupons(marketing_user),
        "institute_count": len(institute_ids),
        "payments_url": None,
    }


def build_institute_accounts_ctx(institute, user, request):
    period, start, end, period_label = parse_accounts_period(request)
    product_key, product_type = _parse_product_filter(request)

    line_qs = InstituteTieUpLineItem.objects.filter(
        order__institute=institute
    ).select_related("order", "payment")
    line_qs = _filter_line_qs(line_qs, start, end, product_type)
    tieup = _aggregate_tieup_lines(line_qs)

    active_order = (
        InstituteTieUpOrder.objects.filter(
            institute=institute, status=choices.TieUpOrderStatus.ACTIVE
        )
        .prefetch_related("line_items")
        .order_by("-created")
        .first()
    )
    pending_objs = []
    if active_order:
        pending_objs = [
            li
            for li in active_order.line_items.all()
            if li.payment_status == choices.TieUpPaymentStatus.PENDING
        ]
    available, used = list_institute_coupons(institute, pending_objs)

    return {
        "role": "institute",
        "period": period,
        "period_label": period_label,
        "product_key": product_key,
        "product_filter_labels": PRODUCT_FILTER_LABELS,
        "date_from": (request.GET.get("date_from") or "").strip(),
        "date_to": (request.GET.get("date_to") or "").strip(),
        "tieup": tieup,
        "coupons_available": available,
        "coupons_used": used,
        "institute": institute,
    }


def build_group_accounts_ctx(group_admin, request):
    institutes = Institute.objects.filter(
        institute_group__institute_group_admin=group_admin
    )
    institute_ids = list(institutes.values_list("id", flat=True))
    period, start, end, period_label = parse_accounts_period(request)
    product_key, product_type = _parse_product_filter(request)

    line_qs = InstituteTieUpLineItem.objects.filter(
        order__institute_id__in=institute_ids
    ).select_related("order", "order__institute", "payment")
    line_qs = _filter_line_qs(line_qs, start, end, product_type)
    tieup = _aggregate_tieup_lines(line_qs)

    all_available = []
    all_used = []
    for inst in institutes.order_by("name")[:50]:
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
        av, us = list_institute_coupons(inst, pending_objs)
        for row in av:
            row["institute_name"] = inst.name
            all_available.append(row)
        for row in us:
            row["institute_name"] = inst.name
            all_used.append(row)

    return {
        "role": "institute_group",
        "period": period,
        "period_label": period_label,
        "product_key": product_key,
        "product_filter_labels": PRODUCT_FILTER_LABELS,
        "date_from": (request.GET.get("date_from") or "").strip(),
        "date_to": (request.GET.get("date_to") or "").strip(),
        "tieup": tieup,
        "coupons_available": all_available[:100],
        "coupons_used": all_used[:100],
        "institute_count": len(institute_ids),
    }
