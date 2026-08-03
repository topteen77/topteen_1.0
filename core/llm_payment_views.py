"""
LLM token package shop + Razorpay / ICICI Eazypay checkout.
"""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature, Signer
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from rest_framework.views import APIView

from core import choices
from core.llm_quota import fulfill_package_payment, seed_role_defaults, wallet_summary_for_user
from core.models import LLMTokenPackage, LLMTokenPackagePayment
from core.utils import get_preferred_payment_gateway, is_gateway_available
from payments.models import Payment
from payments.payment.icicieazypay import IciciEazyPayService

logger = logging.getLogger(__name__)


def _seed_default_packages():
    # Catalog prices in USD; INR is computed at checkout from admin FX rate.
    # usage_examples = buyer-facing "what can I do" lines (admin-editable).
    defaults = [
        {
            "code": "test-spark",
            "name": "Test Spark",
            "tagline": "Your free starter AI allowance",
            "description": "Free student/parent starter: 1 AI resume and 2 AI edits.",
            "usage_examples": (
                "1 AI resume\n"
                "2 AI edits\n"
                "Included free for students & parents"
            ),
            "tokens": 0,
            "price_usd": "0.0000",
            "amount": 0,
            "badge_label": "Free starter",
            "sort_order": 0,
            "is_featured": False,
        },
        {
            "code": "spark",
            "name": "AI Spark",
            "tagline": "Try AI once — see the difference",
            "description": "A small starter pack when you need one focused AI boost.",
            "usage_examples": (
                "Build 1 polished AI resume\n"
                "Ask ~10 AI tutor / career chat questions\n"
                "Try reading-level simplify a few times"
            ),
            "tokens": 25000,
            "price_usd": "0.5900",
            "amount": 49,
            "badge_label": "",
            "sort_order": 10,
            "is_featured": False,
        },
        {
            "code": "boost",
            "name": "AI Boost",
            "tagline": "Most students start here",
            "description": "Enough AI help for resume studio plus ongoing career Q&A.",
            "usage_examples": (
                "Build or rewrite ~4 AI resumes\n"
                "Ask ~40 AI tutor / career chat questions\n"
                "Use AI writing help across summary, projects & achievements"
            ),
            "tokens": 100000,
            "price_usd": "1.8000",
            "amount": 149,
            "badge_label": "Most popular",
            "sort_order": 20,
            "is_featured": True,
        },
        {
            "code": "power",
            "name": "AI Power",
            "tagline": "Best value for heavy AI use",
            "description": "High-capacity pack for serious builders, counselors, and power users.",
            "usage_examples": (
                "Build or rewrite ~15+ AI resumes\n"
                "Ask ~150 AI tutor / career chat questions\n"
                "Plenty left for career search AI & reading-level help"
            ),
            "tokens": 400000,
            "price_usd": "4.8000",
            "amount": 399,
            "badge_label": "Best value",
            "sort_order": 30,
            "is_featured": False,
        },
    ]
    for row in defaults:
        obj, created = LLMTokenPackage.objects.get_or_create(
            code=row["code"],
            defaults={
                **row,
                "currency": choices.Currency.IND,
                "is_active": True,
            },
        )
        update_fields = []
        if not created:
            if row["code"] == "test-spark":
                # Keep free-starter copy aligned with student/parent feature quotas.
                for field in (
                    "name",
                    "tagline",
                    "description",
                    "usage_examples",
                    "badge_label",
                    "sort_order",
                    "tokens",
                    "price_usd",
                    "amount",
                ):
                    if getattr(obj, field) != row[field]:
                        setattr(obj, field, row[field])
                        update_fields.append(field)
            else:
                if not obj.price_usd or obj.price_usd == 0:
                    obj.price_usd = row["price_usd"]
                    update_fields.append("price_usd")
                if not (obj.usage_examples or "").strip():
                    obj.usage_examples = row["usage_examples"]
                    update_fields.append("usage_examples")
                if not (obj.tagline or "").strip() and row.get("tagline"):
                    obj.tagline = row["tagline"]
                    update_fields.append("tagline")
            if update_fields:
                update_fields.append("modified")
                obj.save(update_fields=list(dict.fromkeys(update_fields)))

    # Backfill any legacy "Test Spark" row missing usage lines.
    for legacy in LLMTokenPackage.objects.filter(name__iexact="Test Spark"):
        if not (legacy.usage_examples or "").strip():
            legacy.usage_examples = (
                "1 AI resume\n"
                "2 AI edits\n"
                "Included free for students & parents"
            )
            if not (legacy.tagline or "").strip():
                legacy.tagline = "Your free starter AI allowance"
            if not (legacy.badge_label or "").strip():
                legacy.badge_label = "Free starter"
            legacy.save(update_fields=["usage_examples", "tagline", "badge_label", "modified"])


def _resolve_active_package(user, packages):
    """Mark free Test Spark active for students/parents on the free starter tier."""
    from core.ai_feature_quota import (
        FEATURE_RESUME_AI,
        FEATURE_RESUME_CREATE,
        feature_status,
        quota_applies,
    )

    if not quota_applies(user):
        return None

    paid = LLMTokenPackagePayment.objects.filter(
        user=user,
        is_success=choices.YesNoChoices.YES,
        tokens_credited=True,
    ).exclude(package__code="test-spark").order_by("-modified").select_related("package").first()
    if paid and paid.package_id:
        return paid.package

    # Still on free starter: prefer test-spark, else any package named Test Spark.
    for pkg in packages:
        if (pkg.code or "").lower() in ("test-spark", "testspark", "test_spark"):
            return pkg
    for pkg in packages:
        if (pkg.name or "").strip().lower() == "test spark":
            return pkg

    # Fallback: free allowance still available.
    create_st = feature_status(user, FEATURE_RESUME_CREATE)
    ai_st = feature_status(user, FEATURE_RESUME_AI)
    if not create_st.get("locked") or not ai_st.get("locked"):
        for pkg in packages:
            if (pkg.name or "").strip().lower() == "test spark" or (pkg.code or "").lower() == "test-spark":
                return pkg
    return None


@method_decorator(login_required(login_url="/user/login/"), name="dispatch")
class LLMTokenPackagesView(TemplateView):
    template_name = "template20/core/llm_token_packages.html"

    def get_context_data(self, **kwargs):
        from core.ai_feature_quota import (
            FEATURE_RESUME_AI,
            FEATURE_RESUME_CREATE,
            feature_status,
            get_settings,
            quota_applies,
        )
        from core.llm_fx import package_pricing_dict, storefront_display_flags

        seed_role_defaults()
        _seed_default_packages()
        ctx = super().get_context_data(**kwargs)
        packages = list(
            LLMTokenPackage.objects.filter(is_active=True).order_by("sort_order", "price_usd")
        )
        pricing = {p.id: package_pricing_dict(p) for p in packages}
        flags = storefront_display_flags()
        active_pkg = _resolve_active_package(self.request.user, packages)
        feature_quota = None
        if quota_applies(self.request.user):
            settings_row = get_settings()
            create_st = feature_status(self.request.user, FEATURE_RESUME_CREATE, request=self.request)
            ai_st = feature_status(self.request.user, FEATURE_RESUME_AI, request=self.request)
            feature_quota = {
                "resume_creates_remaining": create_st.get("remaining"),
                "resume_ai_remaining": ai_st.get("remaining"),
                "resume_free_creates": settings_row.resume_free_creates,
                "resume_free_ai_edits": settings_row.resume_free_ai_edits,
            }
        ctx["packages"] = packages
        ctx["package_pricing"] = pricing
        ctx["wallet"] = wallet_summary_for_user(self.request.user, request=self.request)
        ctx["feature_hint"] = self.request.GET.get("feature") or ""
        ctx["active_package_id"] = getattr(active_pkg, "id", None)
        ctx["active_package"] = active_pkg
        ctx["feature_quota"] = feature_quota
        ctx.update(flags)
        return ctx


@method_decorator(never_cache, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(login_required(login_url="/user/login/"), name="dispatch")
class LLMPackageCheckoutView(View):
    """Create domain + gateway payment and open Razorpay or redirect to Eazypay."""

    def get_payment_url(self, request, package):
        from core.llm_fx import get_usd_to_inr_rate, usd_to_inr_amount

        user = request.user
        gateway_receipt = "LLM{}_{}".format(user.id, package.id)[:40]
        rate = get_usd_to_inr_rate()
        price_usd = package.price_usd
        amount = usd_to_inr_amount(price_usd, rate=rate)
        if amount <= 0:
            raise ValueError("Package INR amount is zero; set price_usd and USD→INR rate.")

        sp, _ = LLMTokenPackagePayment.objects.get_or_create(
            user=user,
            package=package,
            gateway_receipt=gateway_receipt,
            is_success=choices.YesNoChoices.NO,
            defaults={
                "amount": amount,
                "currency": choices.Currency.IND,
                "tokens_granted": package.tokens,
                "price_usd": price_usd,
                "usd_to_inr_rate": rate,
            },
        )
        update_fields = []
        if sp.amount != amount:
            sp.amount = amount
            update_fields.append("amount")
        if sp.tokens_granted != package.tokens:
            sp.tokens_granted = package.tokens
            update_fields.append("tokens_granted")
        if sp.price_usd != price_usd:
            sp.price_usd = price_usd
            update_fields.append("price_usd")
        if sp.usd_to_inr_rate != rate:
            sp.usd_to_inr_rate = rate
            update_fields.append("usd_to_inr_rate")
        if update_fields:
            update_fields.append("modified")
            sp.save(update_fields=update_fields)

        preferred_gateway = get_preferred_payment_gateway()
        payment, _ = Payment.objects.get_or_create(
            user=user,
            gateway_receipt=sp.gateway_receipt,
            gateway=preferred_gateway,
            is_success=choices.YesNoChoices.NO,
            obj_id=sp.id,
            obj_type=choices.PaymentObjectType.LLM_TOKEN_PACKAGE,
            amount=sp.amount,
            currency=sp.currency,
        )
        if payment.amount != sp.amount:
            payment.amount = sp.amount
            payment.save(update_fields=["amount"])

        if payment.gateway == choices.GatewayChoices.ICICIEAZYPAY and not is_gateway_available(
            choices.GatewayChoices.ICICIEAZYPAY
        ):
            payment.gateway = choices.GatewayChoices.RAZORPAY
            payment.save(update_fields=["gateway"])

        if payment.gateway == choices.GatewayChoices.RAZORPAY:
            try:
                payment_info_str = payment.get_payment_info()
                payment_info_dict = (
                    json.loads(payment_info_str)
                    if isinstance(payment_info_str, str)
                    else payment_info_str
                )
                return {
                    "type": "json",
                    "data": {"payment_info": payment_info_dict, "gateway": "razorpay"},
                    "sp": sp,
                }
            except Exception as e:
                logger.exception("LLM package Razorpay prep failed: %s", e)
                return HttpResponse(f"Error preparing payment: {e}", status=500)

        try:
            ezypy = IciciEazyPayService()
            payment_url = ezypy.get_encrypt_payment_url(
                reference_no=str(payment.id),
                sub_merchant_id=str(user.id),
                transaction_amount=str(amount),
                email=user.email,
                login_user_id=str(user.id),
                mobile_no=user.mobile if getattr(user, "mobile", None) else "1111111111",
                remarks=gateway_receipt,
                purchase_item="AI Tokens {}".format(package.name),
                order_no_1="x",
                order_no="x",
                upivpa="x",
            )
            return {"type": "redirect", "url": payment_url, "sp": sp}
        except Exception as e:
            logger.warning("Eazypay failed for LLM package, fallback Razorpay: %s", e, exc_info=True)
            payment.gateway = choices.GatewayChoices.RAZORPAY
            payment.save(update_fields=["gateway"])
            try:
                payment_info_str = payment.get_payment_info()
                payment_info_dict = (
                    json.loads(payment_info_str)
                    if isinstance(payment_info_str, str)
                    else payment_info_str
                )
                return {
                    "type": "json",
                    "data": {"payment_info": payment_info_dict, "gateway": "razorpay"},
                    "sp": sp,
                }
            except Exception as e2:
                logger.exception("LLM package Razorpay fallback failed: %s", e2)
                return HttpResponse(f"Error preparing Razorpay payment: {e2}", status=500)

    def get(self, request, code, *args, **kwargs):
        from core.llm_fx import package_pricing_dict

        package = get_object_or_404(LLMTokenPackage, code=code, is_active=True)
        pricing = package_pricing_dict(package)
        if not pricing["amount_inr"] or pricing["amount_inr"] <= 0:
            messages.error(request, "This package is not available for purchase.")
            return redirect("core:llm_token_packages")

        try:
            result = self.get_payment_url(request, package)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("core:llm_token_packages")
        if isinstance(result, HttpResponse):
            return result

        sp = result.get("sp")
        url_info = sp.get_payment_success_fail_url()

        if result.get("type") == "json":
            payment_info = result.get("data", {}).get("payment_info", {})
            if isinstance(payment_info, str):
                payment_info = json.loads(payment_info)
            return render(
                request,
                "template20/core/llm_package_payment.html",
                {
                    "package": package,
                    "pricing": pricing,
                    "show_price_inr": pricing.get("show_price_inr"),
                    "show_price_usd": pricing.get("show_price_usd"),
                    "show_exchange_rate": pricing.get("show_exchange_rate"),
                    "price_usd_display": pricing.get("price_usd_display") or "",
                    "rate_display": pricing.get("rate_display") or "",
                    "amount_inr_display": pricing.get("amount_inr_display")
                    or f"₹ {sp.amount}",
                    "payment_info_json": json.dumps(payment_info),
                    "payment_info": payment_info,
                    "gateway": result.get("data", {}).get("gateway", "razorpay"),
                    "success_url": url_info["success_url"],
                    "fail_url": url_info["fail_url"],
                    "payment_id": sp.id,
                },
            )
        if result.get("type") == "redirect":
            return redirect(result["url"])
        return HttpResponse("Unable to process payment. Please try again.", status=500)


class UpdateLLMPackagePaymentView(APIView):
    """Razorpay client callback — verify signature and credit tokens."""

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "error": "login_required"}, status=401)

        gateway_order_id = request.data.get("gateway_order_id")
        gateway_payment_id = request.data.get("gateway_payment_id")
        gateway_signature = request.data.get("gateway_signature")
        payment_id = request.data.get("payment_id")

        if not (gateway_order_id and gateway_payment_id and gateway_signature and payment_id):
            return JsonResponse({"success": False, "error": "missing_fields"}, status=400)

        sp = get_object_or_404(LLMTokenPackagePayment, id=payment_id, user=request.user)
        payment = get_object_or_404(
            Payment,
            obj_id=sp.id,
            obj_type=choices.PaymentObjectType.LLM_TOKEN_PACKAGE,
            user=request.user,
        )
        payment_status = payment.update_payment(
            gateway_payment_id, gateway_order_id, gateway_signature
        )
        try:
            from invoices.models import PaymentGatewayHealth
            from invoices.utils import record_gateway_callback

            record_gateway_callback(
                PaymentGatewayHealth.RAZORPAY,
                success=bool(payment_status),
                error_message=None if payment_status else "LLM package Razorpay verify failed",
                callback_url=request.build_absolute_uri(request.path),
            )
        except Exception:
            pass

        urls = sp.get_payment_success_fail_url()
        if payment_status:
            fulfill_package_payment(sp)
            return JsonResponse({"success": True, "redirect_url": urls["success_url"]})
        return JsonResponse({"success": False, "redirect_url": urls["fail_url"]}, status=400)


@method_decorator(login_required(login_url="/user/login/"), name="dispatch")
class LLMPackagePaymentSuccessView(View):
    def get(self, request, enc_id, *args, **kwargs):
        try:
            data = Signer().unsign_object(enc_id)
            sp = get_object_or_404(
                LLMTokenPackagePayment, id=data.get("enc_id"), user=request.user
            )
        except (BadSignature, TypeError, ValueError):
            messages.error(request, "Invalid payment link.")
            return redirect("core:llm_token_packages")

        if sp.is_success == choices.YesNoChoices.YES or sp.tokens_credited:
            fulfill_package_payment(sp)
        from core.llm_fx import storefront_display_flags

        wallet = wallet_summary_for_user(request.user, request=request)
        ctx = {"payment": sp, "package": sp.package, "wallet": wallet}
        ctx.update(storefront_display_flags())
        return render(request, "template20/core/llm_package_payment_success.html", ctx)


@method_decorator(login_required(login_url="/user/login/"), name="dispatch")
class LLMPackagePaymentFailView(View):
    def get(self, request, enc_id, *args, **kwargs):
        try:
            data = Signer().unsign_object(enc_id)
            sp = get_object_or_404(
                LLMTokenPackagePayment, id=data.get("enc_id"), user=request.user
            )
        except (BadSignature, TypeError, ValueError):
            messages.error(request, "Invalid payment link.")
            return redirect("core:llm_token_packages")
        return render(
            request,
            "template20/core/llm_package_payment_fail.html",
            {"payment": sp, "package": sp.package},
        )


@method_decorator(login_required(login_url="/user/login/"), name="dispatch")
class LLMWalletStatusAPI(View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        return JsonResponse(wallet_summary_for_user(request.user, request=request))
