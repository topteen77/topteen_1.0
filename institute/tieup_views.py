"""Institute tie-up billing views (Razorpay checkout, marketing approve, mark received)."""
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.signing import Signer
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import TemplateView
from urllib.parse import unquote

from core import choices
from institute.decorators import (
    institute_authenticated_user_only,
    marketing_group_user_only,
)
from institute.models import Institute, InstituteTieUpLineItem, InstituteTieUpOrder
from institute.tieup_billing import (
    apply_coupon_to_pending_order,
    build_institute_billing_ctx,
    create_checkout_for_tieup_order,
    create_tieup_order,
    finalize_tieup_payment,
    list_applicable_coupons,
    mark_line_item_received,
    parse_line_items_from_post,
    resolve_tieup_pay_cta,
    user_can_access_tieup_institute,
    user_can_download_tieup_invoice,
)
from payments.models import Payment


def _marketing_can_manage_institute(user, institute):
    if user.is_superuser:
        return True
    mg = institute.marketing_group
    if mg and mg.marketing_group_admin_id == user.id:
        return True
    ig = getattr(institute, "institute_group", None)
    return bool(ig and ig.institute_group_admin_id == user.id)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
@method_decorator(marketing_group_user_only, name="dispatch")
class InstituteApproveWithBillingView(View):
    """POST: approve institute and create tie-up order from line items."""

    def post(self, request, id):
        referer = request.META.get("HTTP_REFERER") or reverse(
            "institute:marketinggroupdashboard"
        )
        institute = get_object_or_404(Institute, id=id)
        if not _marketing_can_manage_institute(request.user, institute):
            messages.error(request, "You cannot approve this institute.")
            return HttpResponseRedirect(referer)
        line_items = parse_line_items_from_post(request.POST)
        if not line_items:
            messages.error(
                request,
                "Tie-up billing is required before approval. Add at least one line item.",
            )
            return HttpResponseRedirect(referer)
        coupon_code = (request.POST.get("tieup_coupon_code") or "").strip()
        try:
            create_tieup_order(
                institute,
                request.user,
                line_items,
                coupon_code=coupon_code or None,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return HttpResponseRedirect(referer)
        institute.institute_status = choices.InstituteStatus.APPROVED
        institute.save(update_fields=["institute_status", "modified"])
        messages.success(
            request, f"Institute '{institute.name}' approved with tie-up billing."
        )
        return HttpResponseRedirect(referer)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class MarketingTieUpMarkReceivedView(View):
    """POST: marketing / group admin marks a line item as received (offline payment)."""

    def post(self, request):
        referer = request.META.get("HTTP_REFERER") or reverse(
            "institute:marketinggroupdashboard_page", args=["payments"]
        )
        if not request.user.is_authenticated:
            return HttpResponseRedirect(referer)
        ut = getattr(request.user, "user_type", None)
        if ut not in (
            choices.UserType.MARKETINGGROUPADMIN,
            choices.UserType.INSTITUTEGROUPADMIN,
        ) and not request.user.is_superuser:
            messages.error(request, "Not allowed.")
            return HttpResponseRedirect(referer)
        line_id = request.POST.get("line_id")
        if not line_id:
            messages.error(request, "Missing line item.")
            return HttpResponseRedirect(referer)
        line = get_object_or_404(
            InstituteTieUpLineItem.objects.select_related("order__institute"),
            pk=line_id,
        )
        if not _marketing_can_manage_institute(request.user, line.order.institute):
            messages.error(request, "Not allowed to update this line item.")
            return HttpResponseRedirect(referer)
        mark_line_item_received(line, request.user)
        messages.success(request, "Payment marked as received.")
        return HttpResponseRedirect(referer)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
@method_decorator(institute_authenticated_user_only, name="dispatch")
class InstituteTieUpPayView(TemplateView):
    """Checkout page with coupon apply + Pay Now."""

    template_name = "template_v2/institute/pages/institute_tieup_billing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")
        institute = get_object_or_404(Institute, slug=slug)
        billing = build_institute_billing_ctx(institute, self.request.user)
        ctx.update(billing)
        ctx["institute"] = institute
        ctx["checkout_mode"] = True
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
        return ctx


@csrf_exempt
@login_required(login_url=reverse_lazy("users:login"))
@require_http_methods(["POST"])
def institute_tieup_create_order(request, slug):
    institute = get_object_or_404(Institute, slug=slug)
    if not user_can_access_tieup_institute(request.user, institute):
        return JsonResponse({"success": False, "error": "Not allowed."}, status=403)
    order_id = request.POST.get("order_id")
    if not order_id:
        return JsonResponse({"success": False, "error": "Missing order."}, status=400)
    order = get_object_or_404(
        InstituteTieUpOrder, pk=order_id, institute=institute
    )
    coupon_code = (request.POST.get("coupon_code") or "").strip()
    try:
        data = create_checkout_for_tieup_order(
            order, request.user, coupon_code=coupon_code or None
        )
        return JsonResponse({"success": True, **data})
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@login_required(login_url=reverse_lazy("users:login"))
@require_http_methods(["POST"])
def institute_tieup_payment_verify(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    payment_id = data.get("payment_id")
    gateway_payment_id = data.get("gateway_payment_id")
    gateway_order_id = data.get("gateway_order_id")
    gateway_signature = data.get("gateway_signature")
    if not all([payment_id, gateway_payment_id, gateway_order_id, gateway_signature]):
        return JsonResponse(
            {"success": False, "error": "Missing payment details"}, status=400
        )
    payment = get_object_or_404(
        Payment,
        id=payment_id,
        user=request.user,
        obj_type=choices.PaymentObjectType.INSTITUTE_TIEUP,
    )
    if payment.is_success == choices.YesNoChoices.YES:
        return JsonResponse(
            {"success": True, "message": "Already processed", "already_paid": True}
        )
    ok = payment.update_payment(
        gateway_payment_id, gateway_order_id, gateway_signature
    )
    if ok:
        finalize_tieup_payment(payment)
        sign = Signer()
        enc = sign.sign_object({"enc_id": payment.id})
        return JsonResponse(
            {
                "success": True,
                "redirect_url": reverse(
                    "institute:institute_tieup_payment_success",
                    kwargs={"enc_id": enc},
                ),
            }
        )
    return JsonResponse({"success": False, "error": "Verification failed"}, status=400)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class InstituteTieUpPaymentSuccessView(TemplateView):
    template_name = "template_v2/institute/pages/institute_tieup_payment_success.html"

    def get_template_names(self):
        from institute.views import _dashboard_template
        return [
            _dashboard_template(
                "template20/institute/institute_group_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ttv2_page"] = "payments"
        enc_id = kwargs.get("enc_id")
        if enc_id:
            try:
                enc_id = unquote(enc_id)
                payment_id = Signer().unsign_object(enc_id).get("enc_id")
                payment = Payment.objects.filter(
                    id=payment_id,
                    user=self.request.user,
                    obj_type=choices.PaymentObjectType.INSTITUTE_TIEUP,
                ).first()
                ctx["payment"] = payment
                if payment:
                    order = InstituteTieUpOrder.objects.filter(pk=payment.obj_id).first()
                    ctx["order"] = order
                    if order:
                        ctx["institute"] = order.institute
                        ctx["billing_back_url"] = reverse(
                            "institute:institutedashboard_page",
                            args=[order.institute.slug, "payments"],
                        )
            except Exception:
                pass
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class InstituteTieUpPaymentFailView(TemplateView):
    template_name = "template_v2/institute/pages/institute_tieup_payment_fail.html"

    def get_template_names(self):
        from institute.views import _dashboard_template
        return [
            _dashboard_template(
                "template20/institute/institute_group_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        enc_id = kwargs.get("enc_id")
        ctx["retry_url"] = reverse("institute:marketinggroupdashboard")
        if enc_id:
            try:
                payment_id = Signer().unsign_object(unquote(enc_id)).get("enc_id")
                payment = Payment.objects.filter(id=payment_id).first()
                if payment:
                    order = InstituteTieUpOrder.objects.filter(pk=payment.obj_id).first()
                    if order and order.institute:
                        ctx["retry_url"] = reverse(
                            "institute:institute_tieup_pay",
                            kwargs={"slug": order.institute.slug},
                        )
            except Exception:
                pass
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class MarketingTieUpCouponCreateView(View):
    """POST: marketing / institute-group admin creates an institute-scoped coupon."""

    def post(self, request):
        referer = request.META.get("HTTP_REFERER") or reverse(
            "institute:marketinggroupdashboard_page", args=["payments"]
        )
        if not request.user.is_authenticated:
            return HttpResponseRedirect(referer)
        ut = getattr(request.user, "user_type", None)
        if ut not in (
            choices.UserType.MARKETINGGROUPADMIN,
            choices.UserType.INSTITUTEGROUPADMIN,
        ) and not request.user.is_superuser:
            messages.error(request, "Not allowed.")
            return HttpResponseRedirect(referer)
        institute_id = request.POST.get("institute_id")
        code = (request.POST.get("coupon_code") or "").strip().upper()
        discount_type = (request.POST.get("discount_type") or "percent").strip()
        value_raw = (request.POST.get("coupon_value") or "").strip()
        applies_to = (request.POST.get("applies_to") or choices.CouponAppliesTo.ALL).strip()

        if not institute_id or not code or not value_raw:
            messages.error(request, "Institute, code, and value are required.")
            return HttpResponseRedirect(referer)

        institute = get_object_or_404(Institute, pk=institute_id)
        if not _marketing_can_manage_institute(request.user, institute):
            messages.error(request, "Not allowed to create coupons for this institute.")
            return HttpResponseRedirect(referer)

        from decimal import Decimal, InvalidOperation

        try:
            value = Decimal(value_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid coupon value.")
            return HttpResponseRedirect(referer)

        if discount_type not in (
            choices.CouponDiscountType.PERCENT,
            choices.CouponDiscountType.FIXED,
        ):
            discount_type = choices.CouponDiscountType.PERCENT

        from institute.models import InstituteDiscountCoupon

        if InstituteDiscountCoupon.objects.filter(code__iexact=code).exists():
            messages.error(request, "This coupon code already exists.")
            return HttpResponseRedirect(referer)

        coupon = InstituteDiscountCoupon(
            institute=institute,
            marketing_group=institute.marketing_group,
            created_by=request.user,
            code=code,
            discount_type=discount_type,
            value=value,
            applies_to=applies_to,
            is_active=True,
        )
        max_uses_raw = (request.POST.get("max_uses") or "").strip()
        if max_uses_raw.isdigit():
            coupon.max_uses = int(max_uses_raw)
        coupon.save()
        messages.success(request, f"Coupon {code} created for {institute.name}.")
        return HttpResponseRedirect(referer)


@csrf_exempt
@login_required(login_url=reverse_lazy("users:login"))
@require_http_methods(["POST"])
def institute_tieup_coupon_preview(request, slug):
    """AJAX: validate coupon, persist line discounts, return payable total."""
    institute = get_object_or_404(Institute, slug=slug)
    if not user_can_access_tieup_institute(request.user, institute):
        return JsonResponse({"success": False, "error": "Not allowed."}, status=403)
    order_id = request.POST.get("order_id")
    code = (request.POST.get("coupon_code") or "").strip()
    order = get_object_or_404(InstituteTieUpOrder, pk=order_id, institute=institute)
    pending = list(
        order.line_items.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    )
    subtotal = sum((ln.line_subtotal or Decimal("0")) for ln in pending)

    if not code:
        discount, err = apply_coupon_to_pending_order(order, "")
        if err:
            return JsonResponse({"success": False, "error": err}, status=400)
        order.refresh_from_db()
        return JsonResponse(
            {
                "success": True,
                "subtotal": str(subtotal),
                "discount": "0",
                "final_amount": str(order.total_amount),
                "capped": False,
            }
        )

    discount, err = apply_coupon_to_pending_order(order, code)
    if err:
        return JsonResponse({"success": False, "error": err}, status=400)
    order.refresh_from_db()
    coupon_row = order.coupon
    capped = False
    if coupon_row and coupon_row.discount_type == choices.CouponDiscountType.FIXED:
        capped = Decimal(str(coupon_row.value)) > subtotal
    return JsonResponse(
        {
            "success": True,
            "subtotal": str(subtotal),
            "discount": str(discount),
            "final_amount": str(order.total_amount),
            "capped": capped,
            "capped_message": (
                "Discount capped to order total (coupon amount was higher than subtotal)."
                if capped
                else ""
            ),
        }
    )


@login_required(login_url=reverse_lazy("users:login"))
@require_GET
def institute_tieup_invoice_download(request, invoice_id):
    """Download GST invoice PDF for a successful institute tie-up payment."""
    from invoices.models import Invoice
    from invoices.services import ensure_invoice_pdf

    invoice = get_object_or_404(
        Invoice.objects.select_related("payment"),
        pk=invoice_id,
    )
    payment = invoice.payment
    if payment.obj_type != choices.PaymentObjectType.INSTITUTE_TIEUP:
        raise Http404("Not a tie-up invoice.")
    if payment.is_success != choices.YesNoChoices.YES:
        raise Http404("Invoice is available only for successful payments.")
    if not user_can_download_tieup_invoice(request.user, payment):
        return HttpResponse("Not allowed.", status=403)

    content, err = ensure_invoice_pdf(invoice)
    if content is None:
        raise Http404(err or "Invoice PDF not available.")
    filename = "invoice-{}.pdf".format(invoice.invoice_number or invoice_id)
    response = HttpResponse(content, content_type="application/pdf")
    if request.GET.get("view"):
        response["Content-Disposition"] = 'inline; filename="{}"'.format(filename)
    else:
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)
    return response


@login_required(login_url=reverse_lazy("users:login"))
@require_GET
def tieup_pay_status_api(request):
    """JSON for topbar Pay now — institute slug optional (group admins omit slug)."""
    slug = (request.GET.get("slug") or "").strip()
    institute = None
    if slug:
        institute = get_object_or_404(Institute, slug=slug)
        if not user_can_access_tieup_institute(request.user, institute):
            return JsonResponse({"success": False, "error": "Not allowed."}, status=403)
    from django.core.serializers.json import DjangoJSONEncoder

    cta = resolve_tieup_pay_cta(request, institute=institute)
    return JsonResponse(
        {"success": True, "cta": cta}, encoder=DjangoJSONEncoder
    )


@csrf_exempt
@login_required(login_url=reverse_lazy("users:login"))
@require_GET
def institute_tieup_list_coupons(request, slug):
    """AJAX: list coupons applicable to the institute's pending order."""
    institute = get_object_or_404(Institute, slug=slug)
    if not user_can_access_tieup_institute(request.user, institute):
        return JsonResponse({"success": False, "error": "Not allowed."}, status=403)
    order_id = request.GET.get("order_id")
    if not order_id:
        return JsonResponse({"success": False, "error": "Missing order."}, status=400)
    order = get_object_or_404(InstituteTieUpOrder, pk=order_id, institute=institute)
    pending = list(
        order.line_items.filter(payment_status=choices.TieUpPaymentStatus.PENDING)
    )
    coupons = list_applicable_coupons(institute, pending)
    return JsonResponse({"success": True, "coupons": coupons})
