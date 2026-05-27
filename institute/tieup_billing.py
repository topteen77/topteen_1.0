"""
Institute B2B tie-up billing: orders, coupons, Razorpay checkout, manual mark-received.
"""
from decimal import Decimal
import uuid

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core import choices
from institute.models import (
    Institute,
    InstituteDiscountCoupon,
    InstituteTieUpLineItem,
    InstituteTieUpOrder,
)

_PRODUCT_TYPE_MAP = {
    "student_test_credits": choices.TieUpProductType.STUDENT_TEST_CREDITS,
    "counselor_course_seats": choices.TieUpProductType.COUNSELOR_COURSE_SEATS,
    "career_readiness_skilllab": choices.TieUpProductType.CAREER_READINESS_SKILLLAB,
}

_APPLIES_TO_PRODUCT = {
    choices.CouponAppliesTo.STUDENT_TEST_CREDITS: choices.TieUpProductType.STUDENT_TEST_CREDITS,
    choices.CouponAppliesTo.COUNSELOR_COURSE_SEATS: choices.TieUpProductType.COUNSELOR_COURSE_SEATS,
    choices.CouponAppliesTo.CAREER_READINESS_SKILLLAB: choices.TieUpProductType.CAREER_READINESS_SKILLLAB,
}

_PRODUCT_LABELS = dict(choices.TieUpProductType.CHOICES)
_STATUS_LABELS = dict(choices.TieUpPaymentStatus.CHOICES)


def _product_key(product_type_int):
    for k, v in _PRODUCT_TYPE_MAP.items():
        if v == product_type_int:
            return k
    return ""


def parse_exam_credits_qty_from_post(post):
    """
    Exam credits on the institute record match student test credits qty in tie-up billing.
    Returns (qty, error_message). Legacy forms may still post ``ins_credits``.
    """
    raw = (post.get("tieup_student_test_credits_qty") or post.get("ins_credits") or "").strip()
    if not raw:
        return None, "Enter exam credits (quantity)."
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        return None, "Enter a valid number for exam credits."
    if qty < 0:
        return None, "Exam credits cannot be negative."
    return qty, None


def get_tieup_billing_form_initial(institute):
    """Pre-fill tie-up billing fields on marketing edit institute modal."""
    initial = {
        "tieup_student_test_credits_qty": "",
        "tieup_student_test_credits_price": "",
        "tieup_counselor_seats_qty": "",
        "tieup_counselor_seats_price": "",
        "tieup_skilllab_qty": "",
        "tieup_skilllab_price": "",
    }
    if not institute:
        return initial
    order = (
        InstituteTieUpOrder.objects.filter(
            institute=institute, status=choices.TieUpOrderStatus.ACTIVE
        )
        .prefetch_related("line_items")
        .order_by("-created")
        .first()
    )
    field_map = {
        "student_test_credits": (
            "tieup_student_test_credits_qty",
            "tieup_student_test_credits_price",
        ),
        "counselor_course_seats": (
            "tieup_counselor_seats_qty",
            "tieup_counselor_seats_price",
        ),
        "career_readiness_skilllab": ("tieup_skilllab_qty", "tieup_skilllab_price"),
    }
    if order:
        for li in order.line_items.all():
            key = _product_key(li.product_type)
            names = field_map.get(key)
            if not names:
                continue
            initial[names[0]] = li.quantity
            initial[names[1]] = li.unit_price
    elif int(institute.credit_counts or 0) > 0:
        initial["tieup_student_test_credits_qty"] = institute.credit_counts
    return initial


@transaction.atomic
def sync_institute_tieup_from_post(institute, actor, post):
    """
    Replace pending tie-up line items from marketing edit form.
    Received/paid lines are left unchanged.
    """
    if not institute or not actor:
        return None
    raw_qty = (
        post.get("tieup_student_test_credits_qty") or post.get("upd_credits") or ""
    ).strip()
    credit_counts = None
    if raw_qty:
        credit_counts, credits_err = parse_exam_credits_qty_from_post(post)
        if credits_err:
            raise ValueError(credits_err)
        institute.credit_counts = credit_counts
        institute.save(update_fields=["credit_counts", "modified"])

    line_items = parse_line_items_from_post(post)
    if not line_items and credit_counts and credit_counts > 0:
        line_items = tieup_lines_for_institute_create(post, credit_counts)
    if not line_items:
        return None

    order = (
        InstituteTieUpOrder.objects.filter(
            institute=institute, status=choices.TieUpOrderStatus.ACTIVE
        )
        .prefetch_related("line_items")
        .order_by("-created")
        .first()
    )
    coupon_code = (post.get("tieup_coupon_code") or "").strip() or None
    if not order:
        return create_tieup_order(
            institute, actor, line_items, coupon_code=coupon_code
        )

    order.line_items.filter(
        payment_status=choices.TieUpPaymentStatus.PENDING
    ).delete()
    line_discounts = _allocate_order_discount(line_items, Decimal("0"))
    for ln, line_disc in zip(line_items, line_discounts):
        InstituteTieUpLineItem.objects.create(
            order=order,
            product_type=ln["product_type"],
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            line_discount=line_disc,
            payment_status=choices.TieUpPaymentStatus.PENDING,
        )
    pending_lines = list(
        order.line_items.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    )
    if coupon_code:
        apply_coupon_to_pending_order(order, coupon_code)
    else:
        order.coupon = None
        order.discount_amount = Decimal("0")
        order.subtotal = _pending_lines_subtotal(pending_lines)
        order.total_amount = order.subtotal
        order.save(
            update_fields=[
                "coupon",
                "discount_amount",
                "subtotal",
                "total_amount",
                "modified",
            ]
        )
        for ln in pending_lines:
            ln.line_discount = Decimal("0")
            ln.save(update_fields=["line_discount", "total_amount", "modified"])
    if credit_counts is not None:
        sync_student_test_credits(
            institute,
            next(
                (
                    ln["quantity"]
                    for ln in line_items
                    if ln["product_type"]
                    == choices.TieUpProductType.STUDENT_TEST_CREDITS
                ),
                credit_counts,
            ),
        )
    return order


def tieup_lines_for_institute_create(post, credit_counts):
    """
    Line items from tie-up billing fields; if only exam credits qty is set, create one exam-credits line.
    """
    lines = parse_line_items_from_post(post)
    if lines:
        return lines
    try:
        qty = int(credit_counts or 0)
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        return []
    try:
        unit_price = Decimal(str(post.get("tieup_student_test_credits_price") or "0"))
    except Exception:
        unit_price = Decimal("0")
    if unit_price < 0:
        unit_price = Decimal("0")
    return [
        {
            "product_type": _PRODUCT_TYPE_MAP["student_test_credits"],
            "quantity": qty,
            "unit_price": unit_price.quantize(Decimal("0.01")),
        }
    ]


def parse_line_items_from_post(post):
    """Parse tie-up line items from POST dict. Returns list of {product_type, quantity, unit_price}."""
    specs = [
        ("student_test_credits", "tieup_student_test_credits_qty", "tieup_student_test_credits_price"),
        ("counselor_course_seats", "tieup_counselor_seats_qty", "tieup_counselor_seats_price"),
        ("career_readiness_skilllab", "tieup_skilllab_qty", "tieup_skilllab_price"),
    ]
    lines = []
    for key, qty_field, price_field in specs:
        qty_raw = (post.get(qty_field) or "").strip()
        if not qty_raw:
            continue
        try:
            qty = int(qty_raw)
        except (TypeError, ValueError):
            continue
        if qty < 0:
            continue
        if qty == 0:
            continue
        try:
            unit_price = Decimal(str(post.get(price_field) or "0"))
        except Exception:
            unit_price = Decimal("0")
        if unit_price < 0:
            unit_price = Decimal("0")
        lines.append(
            {
                "product_type": _PRODUCT_TYPE_MAP[key],
                "quantity": qty,
                "unit_price": unit_price.quantize(Decimal("0.01")),
            }
        )
    return lines


def user_can_access_tieup_institute(user, institute):
    """Institute owner, marketing group admin for this institute, or institute-group admin."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if institute.created_by_id == user.id:
        return True
    mg = getattr(institute, "marketing_group", None)
    if mg and mg.marketing_group_admin_id == user.id:
        return True
    ig = getattr(institute, "institute_group", None)
    if ig and ig.institute_group_admin_id == user.id:
        return True
    return False


def user_can_create_tieup_coupons(user, institute):
    """Marketing or institute-group admin for this institute (or superuser)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    mg = getattr(institute, "marketing_group", None)
    if mg and mg.marketing_group_admin_id == user.id:
        return True
    ig = getattr(institute, "institute_group", None)
    if ig and ig.institute_group_admin_id == user.id:
        return True
    return False


def user_can_download_tieup_invoice(user, payment):
    """Payer, institute portal user, or marketing admin for the institute's tie-up order."""
    if not user or not getattr(user, "is_authenticated", False) or not payment:
        return False
    if user.is_superuser:
        return True
    if payment.user_id == user.id:
        return True
    if payment.obj_type != choices.PaymentObjectType.INSTITUTE_TIEUP:
        return False
    try:
        order = InstituteTieUpOrder.objects.select_related("institute").get(pk=payment.obj_id)
    except InstituteTieUpOrder.DoesNotExist:
        return False
    institute = order.institute
    if user_can_access_tieup_institute(user, institute):
        return True
    return user_can_create_tieup_coupons(user, institute)


def _is_payable_amount(amount):
    """True when tie-up amount due is strictly greater than zero (Pay Now / gateway)."""
    try:
        return Decimal(str(amount or 0)) > Decimal("0")
    except Exception:
        return False


def _pending_lines_subtotal(pending_lines):
    return sum((ln.line_subtotal or Decimal("0")) for ln in pending_lines).quantize(
        Decimal("0.01")
    )


def _pending_product_lines(pending_lines):
    return [
        {
            "product_type": ln.product_type,
            "quantity": ln.quantity,
            "unit_price": ln.unit_price,
        }
        for ln in pending_lines
    ]


def _coupon_display_label(coupon):
    applies = dict(choices.CouponAppliesTo.CHOICES).get(coupon.applies_to, coupon.applies_to)
    if coupon.discount_type == choices.CouponDiscountType.PERCENT:
        return "{} — {}% off ({})".format(coupon.code, coupon.value, applies)
    return "{} — ₹{} off ({})".format(coupon.code, coupon.value, applies)


def _merge_group_coupon_context(institutes_qs):
    """All active / used coupons across institutes in a group (for Accounts + Payments lists)."""
    all_available = []
    all_used = []
    for inst in institutes_qs.order_by("name"):
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
        ctx = get_tieup_pay_coupon_context(inst, pending_objs)
        for row in ctx.get("coupons_available", []):
            item = dict(row)
            item["institute_name"] = inst.name
            item["institute_slug"] = inst.slug
            all_available.append(item)
        for row in ctx.get("coupons_used", []):
            item = dict(row)
            item["institute_name"] = inst.name
            item["institute_slug"] = inst.slug
            all_used.append(item)
    return {
        "applicable_coupons": [],
        "coupons_available": all_available,
        "coupons_used": all_used,
    }


def get_tieup_pay_coupon_context(institute, pending_line_objs):
    """Unified coupon data for institute and group institute payment UI."""
    from institute.accounts_analytics import list_institute_coupons

    pending_line_objs = pending_line_objs or []
    applicable = (
        list_applicable_coupons(institute, pending_line_objs) if pending_line_objs else []
    )
    available, used = list_institute_coupons(institute, pending_line_objs)
    return {
        "applicable_coupons": applicable,
        "coupons_available": available,
        "coupons_used": used,
    }


def list_applicable_coupons(institute, pending_lines):
    """Active coupons the user may apply to the current pending order (validated per code)."""
    pending_lines = pending_lines or []
    product_lines = _pending_product_lines(pending_lines) if pending_lines else []
    subtotal = _pending_lines_subtotal(pending_lines) if pending_lines else Decimal("0")

    out = []
    for coupon in InstituteDiscountCoupon.objects.filter(
        institute=institute, is_active=True
    ).order_by("code"):
        if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
            continue
        if not pending_lines:
            out.append(
                {
                    "code": coupon.code,
                    "label": _coupon_display_label(coupon),
                    "discount_type": coupon.discount_type,
                    "value": str(coupon.value),
                    "applies_to": coupon.applies_to,
                    "discount_amount": "0",
                    "final_amount": "0",
                }
            )
            continue
        discount, err = validate_institute_coupon(
            coupon.code, institute, product_lines, subtotal
        )
        if err and subtotal <= 0 and "greater than zero" in (err or "").lower():
            out.append(
                {
                    "code": coupon.code,
                    "label": _coupon_display_label(coupon),
                    "discount_type": coupon.discount_type,
                    "value": str(coupon.value),
                    "applies_to": coupon.applies_to,
                    "discount_amount": "0",
                    "final_amount": str(subtotal),
                }
            )
            continue
        if err:
            continue
        out.append(
            {
                "code": coupon.code,
                "label": _coupon_display_label(coupon),
                "discount_type": coupon.discount_type,
                "value": str(coupon.value),
                "applies_to": coupon.applies_to,
                "discount_amount": str(discount),
                "final_amount": str(
                    max(subtotal - discount, Decimal("0")).quantize(Decimal("0.01"))
                ),
            }
        )
    return out


def apply_coupon_to_pending_order(order, coupon_code):
    """
    Validate coupon and persist order + line discounts on pending line items.
    Returns (discount_amount, error_message).
    """
    institute = order.institute
    pending_lines = list(
        order.line_items.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    )
    if not pending_lines:
        return Decimal("0"), "No pending line items."
    if not coupon_code or not str(coupon_code).strip():
        order.coupon = None
        order.discount_amount = Decimal("0")
        order.subtotal = _pending_lines_subtotal(pending_lines)
        order.total_amount = order.subtotal
        order.save(
            update_fields=["coupon", "discount_amount", "subtotal", "total_amount", "modified"]
        )
        for ln in pending_lines:
            ln.line_discount = Decimal("0")
            ln.save(update_fields=["line_discount", "total_amount", "modified"])
        return Decimal("0"), None

    product_lines = _pending_product_lines(pending_lines)
    subtotal = _pending_lines_subtotal(pending_lines)
    discount_amount, err = validate_institute_coupon(
        coupon_code, institute, product_lines, subtotal
    )
    if err:
        return Decimal("0"), err
    coupon = InstituteDiscountCoupon.objects.filter(
        code__iexact=str(coupon_code).strip().upper(), institute=institute
    ).first()
    order.coupon = coupon
    order.discount_amount = discount_amount
    order.subtotal = subtotal
    order.total_amount = max(subtotal - discount_amount, Decimal("0")).quantize(Decimal("0.01"))
    order.save(
        update_fields=["coupon", "discount_amount", "subtotal", "total_amount", "modified"]
    )
    shares = _allocate_order_discount(product_lines, discount_amount)
    for ln, share in zip(pending_lines, shares):
        ln.line_discount = share
        ln.save(update_fields=["line_discount", "total_amount", "modified"])
    return discount_amount, None


def validate_institute_coupon(code, institute, product_lines, subtotal):
    """
    Port of counselor_project _validate_coupon for institute tie-up scope.
    Returns (discount_amount, error_message).
    """
    if not code or not str(code).strip():
        return Decimal("0"), None
    code = str(code).strip().upper()
    coupon = InstituteDiscountCoupon.objects.filter(
        code__iexact=code, institute=institute
    ).first()
    if not coupon:
        return Decimal("0"), "Invalid coupon code."
    if not coupon.is_active:
        return Decimal("0"), "This coupon is no longer active."
    if coupon.applies_to != choices.CouponAppliesTo.ALL:
        allowed_pt = _APPLIES_TO_PRODUCT.get(coupon.applies_to)
        line_types = {ln["product_type"] for ln in product_lines}
        if allowed_pt is not None and allowed_pt not in line_types:
            return Decimal("0"), "This coupon is not valid for these products."
    now = timezone.now()
    if coupon.valid_from and now < coupon.valid_from:
        return Decimal("0"), "This coupon is not yet valid."
    if coupon.valid_until and now > coupon.valid_until:
        return Decimal("0"), "This coupon has expired."
    if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
        return Decimal("0"), "This coupon has reached its usage limit."
    price = Decimal(str(subtotal))
    if price <= 0:
        return Decimal("0"), "Order total must be greater than zero to apply a coupon."
    if coupon.discount_type == choices.CouponDiscountType.PERCENT:
        if coupon.value > 100:
            return Decimal("0"), "Percentage discount cannot exceed 100%."
        discount = (price * coupon.value / 100).quantize(Decimal("0.01"))
    else:
        fixed_val = Decimal(str(coupon.value))
        discount = min(fixed_val, price).quantize(Decimal("0.01"))
    discount = min(discount, price)
    if discount <= 0:
        return Decimal("0"), None
    return discount, None


def _allocate_order_discount(line_items_data, order_discount):
    """Proportionally allocate order-level discount to lines."""
    subtotal = sum(
        (Decimal(str(ln["quantity"])) * Decimal(str(ln["unit_price"])))
        for ln in line_items_data
    )
    if subtotal <= 0 or order_discount <= 0:
        return [Decimal("0")] * len(line_items_data)
    shares = []
    allocated = Decimal("0")
    for i, ln in enumerate(line_items_data):
        line_sub = Decimal(str(ln["quantity"])) * Decimal(str(ln["unit_price"]))
        if i == len(line_items_data) - 1:
            share = order_discount - allocated
        else:
            share = (order_discount * line_sub / subtotal).quantize(Decimal("0.01"))
            allocated += share
        shares.append(share)
    return shares


@transaction.atomic
def create_tieup_order(institute, created_by, line_items, coupon_code=None, notes=""):
    """Create tie-up order + line items. line_items: list of dicts with product_type, quantity, unit_price."""
    if not line_items:
        raise ValueError("At least one tie-up line item is required.")
    subtotal = sum(
        Decimal(str(ln["quantity"])) * Decimal(str(ln["unit_price"])) for ln in line_items
    ).quantize(Decimal("0.01"))
    discount_amount = Decimal("0")
    coupon = None
    if coupon_code:
        discount_amount, err = validate_institute_coupon(
            coupon_code, institute, line_items, subtotal
        )
        if err:
            raise ValueError(err)
        coupon = InstituteDiscountCoupon.objects.filter(
            code__iexact=str(coupon_code).strip().upper(), institute=institute
        ).first()
    total_amount = max(subtotal - discount_amount, Decimal("0")).quantize(Decimal("0.01"))
    order = InstituteTieUpOrder.objects.create(
        institute=institute,
        created_by=created_by,
        status=choices.TieUpOrderStatus.ACTIVE,
        notes=notes or "",
        coupon=coupon,
        discount_amount=discount_amount,
        subtotal=subtotal,
        total_amount=total_amount,
    )
    line_discounts = _allocate_order_discount(line_items, discount_amount)
    for ln, line_disc in zip(line_items, line_discounts):
        InstituteTieUpLineItem.objects.create(
            order=order,
            product_type=ln["product_type"],
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            line_discount=line_disc,
            payment_status=choices.TieUpPaymentStatus.PENDING,
        )
    return order


def tieup_payment_result_url(payment):
    """Signed success/fail URL for an institute tie-up Payment, or None."""
    if not payment or payment.obj_type != choices.PaymentObjectType.INSTITUTE_TIEUP:
        return None
    from django.core.signing import Signer
    from django.urls import reverse

    enc = Signer().sign_object({"enc_id": payment.id})
    if payment.is_success == choices.YesNoChoices.YES:
        return reverse("institute:institute_tieup_payment_success", kwargs={"enc_id": enc})
    return reverse("institute:institute_tieup_payment_fail", kwargs={"enc_id": enc})


def get_pending_pay_institutes(institutes_qs):
    """Institutes with pending tie-up orders — for group-admin Pay Now selector."""
    from django.urls import reverse

    result = []
    for inst in institutes_qs.order_by("name"):
        active_order = (
            InstituteTieUpOrder.objects.filter(
                institute=inst, status=choices.TieUpOrderStatus.ACTIVE
            )
            .prefetch_related("line_items")
            .order_by("-created")
            .first()
        )
        if not active_order:
            continue
        pending_lines = [
            li
            for li in active_order.line_items.all()
            if li.payment_status == choices.TieUpPaymentStatus.PENDING
        ]
        if not pending_lines:
            continue
        pending_total = sum(li.total_amount for li in pending_lines)
        if not _is_payable_amount(pending_total):
            continue
        slug = inst.slug
        result.append(
            {
                "slug": slug,
                "name": inst.name,
                "order_id": active_order.id,
                "pending_total": pending_total,
                "create_order_url": reverse(
                    "institute:institute_tieup_create_order", kwargs={"slug": slug}
                ),
                "coupon_preview_url": reverse(
                    "institute:institute_tieup_coupon_preview", kwargs={"slug": slug}
                ),
                "list_coupons_url": reverse(
                    "institute:institute_tieup_list_coupons", kwargs={"slug": slug}
                ),
                "pay_url": reverse("institute:institute_tieup_pay", kwargs={"slug": slug}),
            }
        )
    return result


def _format_dt(dt):
    if not dt:
        return "—"
    try:
        from django.utils import formats

        return formats.date_format(dt, "d M Y, g:i A")
    except Exception:
        return str(dt)


def _line_row(line_item, institute=None):
    from django.urls import reverse

    inst = institute or line_item.order.institute
    pay = line_item.payment
    order = line_item.order
    txn = "-"
    txn_url = None
    if pay and getattr(pay, "gateway_payment_id", None):
        txn = pay.gateway_payment_id
    elif pay and getattr(pay, "gateway_order_id", None):
        txn = pay.gateway_order_id
    if pay:
        txn_url = tieup_payment_result_url(pay)

    invoice_number = None
    invoice_id = None
    invoice_url = None
    if pay:
        inv = getattr(pay, "invoice", None)
        if inv:
            invoice_number = inv.invoice_number
            invoice_id = inv.id
            if pay.is_success == choices.YesNoChoices.YES:
                invoice_url = reverse(
                    "institute:institute_tieup_invoice_download", args=[invoice_id]
                )

    gateway_label = "—"
    if pay:
        gateway_label = dict(choices.GatewayChoices.CHOICES).get(pay.gateway, "—")

    coupon_code = ""
    if order and order.coupon_id:
        coupon_code = getattr(order.coupon, "code", "") or ""

    paid_at = None
    if pay:
        paid_at = pay.transaction_date or pay.modified or pay.created

    return {
        "line_id": line_item.id,
        "order_id": line_item.order_id,
        "order_ref": "ORD-{}".format(line_item.order_id),
        "date": _format_dt(line_item.created),
        "paid_at": _format_dt(paid_at),
        "coupon_code": coupon_code,
        "gateway": gateway_label,
        "invoice_number": invoice_number or "—",
        "invoice_id": invoice_id,
        "invoice_url": invoice_url,
        "institute_id": inst.id,
        "institute_name": inst.name,
        "institute_slug": inst.slug,
        "product": _PRODUCT_LABELS.get(line_item.product_type, str(line_item.product_type)),
        "product_type": line_item.product_type,
        "quantity": line_item.quantity,
        "unit_price": line_item.unit_price,
        "line_subtotal": line_item.line_subtotal,
        "discount": line_item.line_discount,
        "total": line_item.total_amount,
        "status": _STATUS_LABELS.get(line_item.payment_status, "—"),
        "status_key": line_item.payment_status,
        "transaction": txn,
        "transaction_url": txn_url,
        "payment_id": pay.id if pay else None,
        "can_mark_received": line_item.payment_status == choices.TieUpPaymentStatus.PENDING,
        "can_pay": line_item.payment_status == choices.TieUpPaymentStatus.PENDING,
    }


def build_marketing_payments_rows(
    marketing_admin, status_filter=None, institute_slug=None
):
    status_filter = normalize_tieup_status_filter(status_filter)
    institutes = Institute.objects.filter(
        marketing_group__marketing_group_admin=marketing_admin
    )
    if institute_slug:
        institutes = institutes.filter(slug=institute_slug)
    qs = (
        InstituteTieUpLineItem.objects.filter(order__institute__in=institutes)
        .select_related("order", "order__institute", "payment", "order__coupon", "payment__invoice")
        .order_by("-created")
    )
    if status_filter == "pending":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    elif status_filter == "received":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.RECEIVED)
    elif status_filter == "failed":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.FAILED)
    return [_line_row(li) for li in qs[:500]]


def build_institute_group_billing_ctx(
    group_admin, status_filter=None, institute_slug=None
):
    status_filter = normalize_tieup_status_filter(status_filter)
    institutes = Institute.objects.filter(
        institute_group__institute_group_admin=group_admin
    )
    if institute_slug:
        institutes = institutes.filter(slug=institute_slug)
    for inst in institutes:
        ensure_pending_tieup_order_for_institute(inst, group_admin)
    qs = (
        InstituteTieUpLineItem.objects.filter(order__institute__in=institutes)
        .select_related("order", "order__institute", "payment", "order__coupon", "payment__invoice")
        .order_by("-created")
    )
    if status_filter == "pending":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    elif status_filter == "received":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.RECEIVED)
    elif status_filter == "failed":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.FAILED)
    rows = [_line_row(li) for li in qs[:500]]
    pending_total = sum(
        r["total"] for r in rows if r["status_key"] == choices.TieUpPaymentStatus.PENDING
    )
    pending_pay_institutes = get_pending_pay_institutes(institutes)
    first_pending = pending_pay_institutes[0] if pending_pay_institutes else None
    coupon_ctx = _merge_group_coupon_context(institutes)
    first_inst = None
    first_slug = None
    list_coupons_url = ""
    if first_pending:
        first_slug = first_pending["slug"]
        first_inst = institutes.filter(slug=first_slug).first()
        if first_inst:
            from django.urls import reverse

            order = InstituteTieUpOrder.objects.filter(pk=first_pending["order_id"]).first()
            if order:
                pending_line_objs = list(
                    order.line_items.filter(
                        payment_status=choices.TieUpPaymentStatus.PENDING
                    )
                )
                pay_ctx = get_tieup_pay_coupon_context(first_inst, pending_line_objs)
                coupon_ctx["applicable_coupons"] = pay_ctx.get("applicable_coupons", [])
            list_coupons_url = reverse(
                "institute:institute_tieup_list_coupons", kwargs={"slug": first_slug}
            )
    tieup_can_create_coupon = (
        user_can_create_tieup_coupons(group_admin, first_inst)
        if group_admin and first_inst
        else False
    )
    pending_order_lines = [
        r for r in rows if r["status_key"] == choices.TieUpPaymentStatus.PENDING
    ]
    return {
        "rows": rows,
        "tieup_payment_rows": rows,
        "pending_order_lines": pending_order_lines,
        "pending_total": pending_total,
        "has_pending": bool(pending_order_lines),
        "tieup_amount_payable": _is_payable_amount(pending_total),
        "is_group_view": True,
        "pending_pay_institutes": pending_pay_institutes,
        "pay_order_id": first_pending["order_id"] if first_pending else None,
        "create_order_url": first_pending["create_order_url"] if first_pending else "",
        "coupon_preview_url": first_pending["coupon_preview_url"] if first_pending else "",
        "list_coupons_url": list_coupons_url,
        "institute_slug": first_slug or "",
        "tieup_can_pay": True,
        "tieup_can_create_coupon": tieup_can_create_coupon,
        **coupon_ctx,
    }


def normalize_tieup_status_filter(status_filter):
    """Map URL status params to tie-up line payment_status filters."""
    s = (status_filter or "").strip().lower()
    if not s:
        return None
    if s in ("success", "successful", "received"):
        return "received"
    if s in ("fail", "failed"):
        return "failed"
    if s == "pending":
        return "pending"
    return None


def build_institute_billing_ctx(institute, user=None, status_filter=None):
    status_filter = normalize_tieup_status_filter(status_filter)
    qs = (
        InstituteTieUpLineItem.objects.filter(order__institute=institute)
        .select_related("order", "payment", "order__coupon", "payment__invoice")
        .order_by("-created")
    )
    if status_filter == "pending":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    elif status_filter == "received":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.RECEIVED)
    elif status_filter == "failed":
        qs = qs.filter(payment_status=choices.TieUpPaymentStatus.FAILED)
    rows = [_line_row(li, institute) for li in qs]
    pending_lines = [r for r in rows if r["status_key"] == choices.TieUpPaymentStatus.PENDING]
    pending_total = sum(r["total"] for r in pending_lines)
    active_order = (
        InstituteTieUpOrder.objects.filter(
            institute=institute, status=choices.TieUpOrderStatus.ACTIVE
        )
        .prefetch_related("line_items")
        .order_by("-created")
        .first()
    )
    pay_order = None
    pending_line_objs = []
    if active_order and any(
        li.payment_status == choices.TieUpPaymentStatus.PENDING
        for li in active_order.line_items.all()
    ):
        pay_order = active_order
        pending_line_objs = [
            li
            for li in active_order.line_items.all()
            if li.payment_status == choices.TieUpPaymentStatus.PENDING
        ]
    if not pay_order and pending_lines:
        pending_li = (
            InstituteTieUpLineItem.objects.filter(
                order__institute=institute,
                payment_status=choices.TieUpPaymentStatus.PENDING,
            )
            .select_related("order")
            .order_by("-created")
            .first()
        )
        if pending_li:
            pay_order = pending_li.order
            pending_line_objs = list(
                InstituteTieUpLineItem.objects.filter(
                    order=pay_order,
                    payment_status=choices.TieUpPaymentStatus.PENDING,
                )
            )
    coupon_ctx = get_tieup_pay_coupon_context(institute, pending_line_objs)
    return {
        "rows": rows,
        "tieup_payment_rows": rows,
        "pending_order_lines": pending_lines,
        "pending_total": pending_total,
        "has_pending": bool(pending_lines),
        "tieup_amount_payable": _is_payable_amount(pending_total),
        "pay_order": pay_order,
        "pay_order_id": pay_order.id if pay_order and _is_payable_amount(pending_total) else None,
        "is_group_view": False,
        "institute_slug": institute.slug,
        "tieup_can_pay": user_can_access_tieup_institute(user, institute) if user else False,
        "tieup_can_create_coupon": user_can_create_tieup_coupons(user, institute) if user else False,
        **coupon_ctx,
    }


def ensure_pending_tieup_order_for_institute(institute, actor):
    """
    Institutes approved with exam credits but no pending tie-up order yet (legacy creates)
    get a zero-amount pending line so Pay Now / payments UI can open.
    """
    if not institute or int(institute.credit_counts or 0) <= 0:
        return None
    if InstituteTieUpLineItem.objects.filter(
        order__institute=institute,
        payment_status=choices.TieUpPaymentStatus.PENDING,
    ).exists():
        return None
    actor_user = actor if getattr(actor, "is_authenticated", False) else institute.created_by
    if not actor_user:
        return None
    lines = [
        {
            "product_type": choices.TieUpProductType.STUDENT_TEST_CREDITS,
            "quantity": int(institute.credit_counts),
            "unit_price": Decimal("0"),
        }
    ]
    try:
        return create_tieup_order(institute, actor_user, lines)
    except ValueError:
        return None


def tieup_pay_cta_for_institute(institute, user):
    """Header / topbar Pay now CTA when the institute has an unpaid tie-up order."""
    if not institute or not user or not getattr(user, "is_authenticated", False):
        return None
    if not user_can_access_tieup_institute(user, institute):
        return None
    ensure_pending_tieup_order_for_institute(institute, user)
    billing = build_institute_billing_ctx(institute, user)
    pay_order_id = billing.get("pay_order_id")
    pending_total = billing.get("pending_total") or 0
    if not pay_order_id or not billing.get("has_pending") or not _is_payable_amount(
        pending_total
    ):
        return None
    from django.urls import reverse

    slug = institute.slug
    return {
        "show": True,
        "is_group": False,
        "institute_name": institute.name,
        "institute_slug": slug,
        "pending_total": pending_total,
        "pay_order_id": pay_order_id,
        "payments_url": reverse(
            "institute:institutedashboard_page", args=[slug, "payments"]
        ),
    }


def tieup_pay_cta_for_group_admin(user):
    """Topbar Pay now for institute-group admins when any institute has pending tie-up payment."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if user.is_superuser:
        institutes = Institute.objects.all()
    elif getattr(user, "user_type", None) == choices.UserType.INSTITUTEGROUPADMIN:
        institutes = Institute.objects.filter(
            institute_group__institute_group_admin=user
        )
    else:
        return None
    for inst in institutes:
        ensure_pending_tieup_order_for_institute(inst, user)
    pending_list = get_pending_pay_institutes(institutes)
    if not pending_list:
        return None
    from django.urls import reverse

    total_pending = sum(p.get("pending_total") or 0 for p in pending_list)
    if not _is_payable_amount(total_pending):
        return None
    first = pending_list[0]
    return {
        "show": True,
        "is_group": True,
        "institute_name": first.get("name") or "",
        "institute_slug": first.get("slug") or "",
        "pending_total": total_pending,
        "pending_institute_count": len(pending_list),
        "pay_order_id": first.get("order_id"),
        "payments_url": reverse(
            "institute:institutegroupdashboard_page", args=["payments"]
        ),
    }


def resolve_tieup_pay_cta(request, institute=None):
    """Pick institute vs group Pay now CTA for the current user and optional institute."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    if institute:
        return tieup_pay_cta_for_institute(institute, user)
    ut = getattr(user, "user_type", None)
    if ut == choices.UserType.INSTITUTE:
        from institute.models import Institute as InstModel

        inst = (
            InstModel.objects.filter(created_by=user).order_by("-id").first()
        )
        if inst:
            return tieup_pay_cta_for_institute(inst, user)
    if ut == choices.UserType.INSTITUTEGROUPADMIN or user.is_superuser:
        return tieup_pay_cta_for_group_admin(user)
    return None


def attach_institute_tieup_payment_ctx(ctx, institute, user, status_filter=None):
    """Merge billing + Pay now CTA into a dashboard template context dict."""
    if not institute:
        return ctx
    from django.urls import reverse

    ensure_pending_tieup_order_for_institute(institute, user)
    billing = build_institute_billing_ctx(institute, user, status_filter=status_filter)
    slug = institute.slug
    ctx.update(billing)
    ctx["create_order_url"] = reverse(
        "institute:institute_tieup_create_order", kwargs={"slug": slug}
    )
    ctx["verify_url"] = reverse("institute:institute_tieup_payment_verify")
    ctx["coupon_preview_url"] = reverse(
        "institute:institute_tieup_coupon_preview", kwargs={"slug": slug}
    )
    ctx["list_coupons_url"] = reverse(
        "institute:institute_tieup_list_coupons", kwargs={"slug": slug}
    )
    ctx["tieup_pay_url"] = reverse("institute:institute_tieup_pay", kwargs={"slug": slug})
    payments_url = reverse("institute:institutedashboard_page", args=[slug, "payments"])
    ctx["ttv2_tieup_payments_url"] = payments_url
    if billing.get("tieup_amount_payable") and billing.get("pay_order_id"):
        ctx["ttv2_tieup_pending_banner"] = True
    ctx["tieup_payment_rows"] = billing.get("tieup_payment_rows") or billing.get("rows") or []
    ctx["ttv2_tieup_payments"] = ctx["tieup_payment_rows"]
    ctx["pending_order_lines"] = billing.get("pending_order_lines") or []
    ctx["tieup_hide_coupon_ui"] = False
    ctx["is_modern_payments"] = True
    cta = tieup_pay_cta_for_institute(institute, user)
    if cta:
        ctx["ttv2_tieup_pay_cta"] = cta
    else:
        ctx.pop("ttv2_tieup_pay_cta", None)
    return ctx


def attach_group_tieup_payment_ctx(
    ctx, user, status_filter=None, institute_slug=None
):
    """Merge group billing + Pay now CTA for institute-group dashboards."""
    if not user:
        return ctx
    from django.urls import reverse

    billing = build_institute_group_billing_ctx(
        user, status_filter=status_filter, institute_slug=institute_slug
    )
    ctx.update(billing)
    ctx["verify_url"] = reverse("institute:institute_tieup_payment_verify")
    ctx["ttv2_tieup_payments_url"] = reverse(
        "institute:institutegroupdashboard_page", args=["payments"]
    )
    if billing.get("tieup_amount_payable") and billing.get("pay_order_id"):
        ctx["ttv2_tieup_pending_banner"] = True
    ctx["tieup_payment_rows"] = billing.get("tieup_payment_rows") or billing.get("rows") or []
    ctx["ttv2_tieup_payments"] = ctx["tieup_payment_rows"]
    ctx["pending_order_lines"] = billing.get("pending_order_lines") or []
    ctx["tieup_hide_coupon_ui"] = False
    institutes_qs = Institute.objects.filter(
        institute_group__institute_group_admin=user
    ).order_by("name")
    ctx["tieup_coupon_institutes"] = list(
        institutes_qs.values("id", "name", "slug")
    )
    ctx["coupon_create_url"] = reverse("institute:marketing_tieup_coupon_create")
    ctx["mark_received_url"] = reverse("institute:marketing_tieup_mark_received")
    ctx["show_tieup_coupon_create"] = bool(ctx["tieup_coupon_institutes"])
    ctx["show_tieup_mark_received"] = True
    cta = tieup_pay_cta_for_group_admin(user)
    if cta:
        ctx["ttv2_tieup_pay_cta"] = cta
    else:
        ctx.pop("ttv2_tieup_pay_cta", None)
    return ctx


def sync_student_test_credits(institute, quantity):
    """Set institute credit_counts when student_test_credits line is received."""
    institute.credit_counts = int(quantity)
    institute.save(update_fields=["credit_counts", "modified"])


@transaction.atomic
def mark_line_item_received(line_item, user):
    if line_item.payment_status == choices.TieUpPaymentStatus.RECEIVED:
        return line_item
    line_item.payment_status = choices.TieUpPaymentStatus.RECEIVED
    line_item.received_by = user
    line_item.received_at = timezone.now()
    line_item.save(
        update_fields=["payment_status", "received_by", "received_at", "modified"]
    )
    institute = line_item.order.institute
    if line_item.product_type == choices.TieUpProductType.STUDENT_TEST_CREDITS:
        sync_student_test_credits(institute, line_item.quantity)
    order = line_item.order
    if order.coupon_id and _order_fully_received(order):
        _increment_coupon_usage(order.coupon)
    return line_item


def _order_fully_received(order):
    return not order.line_items.exclude(
        payment_status=choices.TieUpPaymentStatus.RECEIVED
    ).exists()


def _increment_coupon_usage(coupon):
    if not coupon:
        return
    InstituteDiscountCoupon.objects.filter(pk=coupon.pk).update(
        times_used=F("times_used") + 1
    )


def _finalize_order_lines(order, payment, success):
    institute = order.institute
    for line in order.line_items.all():
        if success:
            line.payment_status = choices.TieUpPaymentStatus.RECEIVED
            line.received_at = timezone.now()
            if line.product_type == choices.TieUpProductType.STUDENT_TEST_CREDITS:
                sync_student_test_credits(institute, line.quantity)
        else:
            line.payment_status = choices.TieUpPaymentStatus.FAILED
        if payment:
            line.payment = payment
        line.save(
            update_fields=["payment_status", "payment", "received_at", "modified"]
        )
    if success and order.coupon_id:
        _increment_coupon_usage(order.coupon)


@transaction.atomic
def finalize_tieup_payment(payment):
    """Called after Razorpay verify success or reconciliation."""
    from payments.models import Payment

    if payment.obj_type != choices.PaymentObjectType.INSTITUTE_TIEUP:
        return False
    if payment.is_success != choices.YesNoChoices.YES:
        return False
    try:
        order = InstituteTieUpOrder.objects.prefetch_related("line_items").get(
            pk=payment.obj_id
        )
    except InstituteTieUpOrder.DoesNotExist:
        return False
    if _order_fully_received(order):
        return True
    _finalize_order_lines(order, payment, success=True)
    return True


def create_checkout_for_tieup_order(order, user, coupon_code=None):
    """
    Re-validate coupon, create Payment, and start checkout on the configured gateway
    (ICICI Eazypay preferred when configured, else Razorpay).

    Returns dict with ``gateway`` = ``razorpay`` | ``eazypay`` and gateway-specific fields.
    """
    from django.conf import settings

    from core.utils import get_preferred_payment_gateway, is_gateway_available
    from payments.models import Payment
    from payments.payment.icicieazypay import IciciEazyPayService
    from payments.payment.razorpay import RazorpayService

    institute = order.institute
    pending_lines = list(
        order.line_items.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    )
    if not pending_lines:
        raise ValueError("No pending line items to pay.")

    line_items_data = [
        {
            "product_type": ln.product_type,
            "quantity": ln.quantity,
            "unit_price": ln.unit_price,
        }
        for ln in pending_lines
    ]
    subtotal = _pending_lines_subtotal(pending_lines)
    discount_amount = Decimal("0")
    if coupon_code and str(coupon_code).strip():
        discount_amount, err = apply_coupon_to_pending_order(order, coupon_code)
        if err:
            raise ValueError(err)
    elif order.coupon_id:
        discount_amount = order.discount_amount or Decimal("0")
        subtotal = order.subtotal or subtotal

    final_amount = (order.total_amount or max(subtotal - discount_amount, Decimal("0"))).quantize(
        Decimal("0.01")
    )
    amount_inr = int(final_amount)
    if amount_inr <= 0:
        raise ValueError("Order total must be greater than zero.")

    gateway_receipt = f"tieup_{order.id}_{uuid.uuid4().hex[:12]}"
    preferred_gateway = get_preferred_payment_gateway()
    if (
        preferred_gateway == choices.GatewayChoices.ICICIEAZYPAY
        and not is_gateway_available(choices.GatewayChoices.ICICIEAZYPAY)
    ):
        preferred_gateway = choices.GatewayChoices.RAZORPAY
    if preferred_gateway == choices.GatewayChoices.RAZORPAY and not is_gateway_available(
        choices.GatewayChoices.RAZORPAY
    ):
        raise ValueError("No payment gateway is configured. Contact support.")

    payment_record = Payment.objects.create(
        user=user,
        gateway_receipt=gateway_receipt,
        gateway=preferred_gateway,
        obj_id=order.id,
        obj_type=choices.PaymentObjectType.INSTITUTE_TIEUP,
        is_success=choices.YesNoChoices.NO,
        amount=amount_inr,
        currency=choices.Currency.IND,
    )

    from django.core.signing import Signer

    enc = Signer().sign_object({"enc_id": payment_record.id})
    base = {
        "gateway": (
            "eazypay"
            if payment_record.gateway == choices.GatewayChoices.ICICIEAZYPAY
            else "razorpay"
        ),
        "payment_record_id": payment_record.id,
        "final_amount": str(final_amount),
        "discount_applied": str(discount_amount),
        "enc_id": enc,
    }

    if payment_record.gateway == choices.GatewayChoices.ICICIEAZYPAY:
        ezypy = IciciEazyPayService()
        eazypay_url = ezypy.get_encrypt_payment_url(
            reference_no=str(payment_record.id),
            sub_merchant_id=str(user.id),
            transaction_amount=str(amount_inr),
            email=(user.email or "billing@topteen.in"),
            login_user_id=str(user.id),
            mobile_no=(getattr(user, "mobile", None) or "1111111111"),
            remarks=gateway_receipt,
            purchase_item="Institute tie-up billing",
        )
        if not eazypay_url:
            raise ValueError("Failed to start ICICI Eazypay checkout.")
        return {**base, "payment_url": eazypay_url}

    rsvc = RazorpayService()
    razorpay_order_id = rsvc.create_order(
        order_amount=amount_inr * 100,
        order_receipt=gateway_receipt,
    )
    if not razorpay_order_id:
        raise ValueError("Failed to create Razorpay order.")
    payment_record.gateway_order_id = razorpay_order_id
    payment_record.save(update_fields=["gateway_order_id", "modified"])

    return {
        **base,
        "order_id": razorpay_order_id,
        "amount_paise": amount_inr * 100,
        "key": getattr(settings, "RAZORPAY_KEY", "") or getattr(settings, "RAZORPAY_API_KEY", ""),
    }


def create_razorpay_checkout_for_order(order, user, coupon_code=None):
    """Backward-compatible alias."""
    return create_checkout_for_tieup_order(order, user, coupon_code=coupon_code)
