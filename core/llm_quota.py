"""
Freemium AI token wallet: role defaults, admin grants, purchase credits, usage debit.

Call ``ensure_can_use_llm`` before every provider call and ``consume_llm_tokens``
after a successful response (with actual token counts).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Optional

from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Conservative pre-check estimates when call size is unknown.
FEATURE_ESTIMATE_TOKENS = {
    "forum": 2500,
    "resume_v2": 4000,
    "resume_guided": 6000,
    "seo": 3000,
    "careers_search": 2000,
    "careers_embedding": 500,
    "translation": 1500,
    "other": 2000,
}

FEATURE_LABELS = {
    "forum": "AI tutor / career chat",
    "resume_v2": "resume AI",
    "resume_guided": "guided resume AI",
    "seo": "SEO AI",
    "careers_search": "career search AI",
    "careers_embedding": "career search AI",
    "translation": "reading-level AI",
    "other": "AI",
}

# Recharge reminder: at most once per rolling 24 hours per user.
RECHARGE_NOTIFY_CACHE_TTL = 24 * 60 * 60
RECHARGE_NOTIFY_EVENT = "llm.recharge_reminder"

USER_TYPE_TO_ROLE_KEY = {
    1: "student",
    2: "institute",
    3: "institute_group_admin",
    4: "counselor",
    5: "marketing_group_admin",
    6: "parent",
}

DEFAULT_ROLE_SEEDS = {
    "student": {
        "monthly_free_tokens": 50000,
        "estimated_call_tokens": 2500,
        "marketing_headline": "Your free AI boost just ran out",
        "marketing_body": (
            "You've used this month's free AI tokens. Recharge a small pack and keep "
            "building standout resumes, smarter career answers, and clearer content."
        ),
    },
    "parent": {
        "monthly_free_tokens": 20000,
        "estimated_call_tokens": 2000,
        "marketing_headline": "AI assistance needs a quick top-up",
        "marketing_body": "Pick a token pack to continue helping your teen with AI-powered tools.",
    },
    "counselor": {
        "monthly_free_tokens": 100000,
        "estimated_call_tokens": 3000,
        "marketing_headline": "Counselor AI quota reached",
        "marketing_body": "Recharge tokens to keep using AI drafting and research tools with students.",
    },
    "institute": {
        "monthly_free_tokens": 0,
        "estimated_call_tokens": 3000,
        "marketing_headline": "Institute AI tokens needed",
        "marketing_body": "Ask your TopTeen admin to grant AI tokens, or purchase a pack to continue.",
    },
    "institute_group_admin": {
        "monthly_free_tokens": 0,
        "estimated_call_tokens": 3000,
        "marketing_headline": "AI tokens needed",
        "marketing_body": "Request an admin grant or recharge a token pack to continue.",
    },
    "marketing_group_admin": {
        "monthly_free_tokens": 0,
        "estimated_call_tokens": 3000,
        "marketing_headline": "AI tokens needed",
        "marketing_body": "Request an admin grant or recharge a token pack to continue.",
    },
    "staff": {
        "monthly_free_tokens": 0,
        "estimated_call_tokens": 3000,
        "marketing_headline": "Staff AI quota not set",
        "marketing_body": "Ask a superuser to grant AI tokens for SEO and internal tools.",
    },
    "anonymous": {
        "monthly_free_tokens": 10000,
        "estimated_call_tokens": 2000,
        "marketing_headline": "Sign in to keep using AI",
        "marketing_body": (
            "You've used the free guest AI allowance. Create a free TopTeen account to get "
            "monthly AI tokens — or sign in and recharge a pack."
        ),
    },
}


class LLMQuotaExceeded(Exception):
    """Raised when the user (or anonymous guest) cannot afford an LLM call."""

    def __init__(self, payload: dict):
        self.payload = payload
        super().__init__(payload.get("message") or "AI token limit reached")


@dataclass
class QuotaStatus:
    allowed: bool
    balance: int
    role_key: str
    estimated_cost: int
    paywall: Optional[dict] = None


def current_period_key() -> str:
    return timezone.now().strftime("%Y-%m")


def resolve_role_key(user=None) -> str:
    if user is None or not getattr(user, "is_authenticated", False):
        return "anonymous"
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return "staff"
    return USER_TYPE_TO_ROLE_KEY.get(getattr(user, "user_type", 1), "student")


def seed_role_defaults() -> None:
    from core.models import LLMRoleQuotaDefault

    for role_key, conf in DEFAULT_ROLE_SEEDS.items():
        LLMRoleQuotaDefault.objects.get_or_create(
            role_key=role_key,
            defaults={
                "monthly_free_tokens": conf["monthly_free_tokens"],
                "estimated_call_tokens": conf["estimated_call_tokens"],
                "marketing_headline": conf["marketing_headline"],
                "marketing_body": conf["marketing_body"],
                "is_enabled": True,
            },
        )


def get_role_default(role_key: str):
    from core.models import LLMRoleQuotaDefault

    seed_role_defaults()
    obj = LLMRoleQuotaDefault.objects.filter(role_key=role_key).first()
    if obj:
        return obj
    conf = DEFAULT_ROLE_SEEDS.get(role_key, DEFAULT_ROLE_SEEDS["student"])
    return LLMRoleQuotaDefault.objects.create(
        role_key=role_key,
        monthly_free_tokens=conf["monthly_free_tokens"],
        estimated_call_tokens=conf["estimated_call_tokens"],
        marketing_headline=conf["marketing_headline"],
        marketing_body=conf["marketing_body"],
        is_enabled=True,
    )


def estimate_tokens_for_feature(feature: str, role_key: str | None = None) -> int:
    role_est = None
    if role_key:
        try:
            role_est = get_role_default(role_key).estimated_call_tokens
        except Exception:
            role_est = None
    return int(
        FEATURE_ESTIMATE_TOKENS.get(feature, 2000)
        if role_est is None
        else max(role_est, FEATURE_ESTIMATE_TOKENS.get(feature, 2000))
    )


def shop_url() -> str:
    try:
        return reverse("core:llm_token_packages")
    except Exception:
        return "/ai-tokens/"


def login_url() -> str:
    try:
        return reverse("users:login")
    except Exception:
        return "/user/login/"


def build_paywall(
    *,
    role_key: str,
    balance: int,
    estimated_cost: int,
    feature: str,
    require_login: bool = False,
) -> dict:
    role = get_role_default(role_key)
    headline = (
        role.marketing_headline
        or DEFAULT_ROLE_SEEDS.get(role_key, {}).get("marketing_headline")
        or "AI token limit reached"
    )
    body = (
        role.marketing_body
        or DEFAULT_ROLE_SEEDS.get(role_key, {}).get("marketing_body")
        or "Recharge a token pack to continue."
    )
    packages = []
    try:
        from core.models import LLMTokenPackage

        for pkg in LLMTokenPackage.objects.filter(is_active=True).order_by(
            "sort_order", "price_usd"
        )[:6]:
            try:
                from core.llm_fx import package_pricing_dict

                pricing = package_pricing_dict(pkg)
            except Exception:
                pricing = {
                    "amount_inr": pkg.amount,
                    "amount_inr_display": pkg.get_display_price(),
                    "price_usd_display": "",
                    "rate_display": "",
                }
            packages.append(
                {
                    "id": pkg.id,
                    "code": pkg.code,
                    "name": pkg.name,
                    "tagline": pkg.tagline,
                    "usage_examples": pkg.get_usage_examples_list(),
                    "tokens": pkg.tokens,
                    "amount": pricing.get("amount_inr", pkg.amount),
                    "display_price": pricing.get("amount_inr_display") or pkg.get_display_price(),
                    "price_usd_display": pricing.get("price_usd_display") or "",
                    "rate_display": pricing.get("rate_display") or "",
                    "badge_label": pkg.badge_label,
                    "is_featured": pkg.is_featured,
                    "checkout_url": reverse(
                        "core:llm_package_checkout", kwargs={"code": pkg.code}
                    ),
                }
            )
    except Exception:
        logger.exception("Failed loading LLM packages for paywall")

    return {
        "code": "llm_quota_exceeded",
        "message": headline,
        "detail": body,
        "feature": feature,
        "balance_tokens": max(0, int(balance)),
        "estimated_cost": int(estimated_cost),
        "needs_recharge": True,
        "is_low": True,
        "require_login": require_login,
        "cta_label": "Sign in free" if require_login else "Recharge AI tokens",
        "cta_url": login_url() if require_login else shop_url(),
        "shop_url": shop_url(),
        "packages": packages,
        "headline": headline,
        "body": body,
    }


def feature_label(feature: str) -> str:
    return FEATURE_LABELS.get((feature or "").strip(), FEATURE_LABELS["other"])


def _recharge_notify_cache_key(user_id: int) -> str:
    return f"llm_recharge_notif:{int(user_id)}"


def maybe_notify_recharge(
    user,
    *,
    balance: int,
    estimated_cost: int,
    feature: str = "",
    reason: str = "insufficient",
) -> bool:
    """
    In-app notification to recharge when balance cannot cover the next AI call.

    At most once per rolling 24 hours per user (cache + recent Notification check).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if int(balance) >= int(estimated_cost):
        return False

    user_id = getattr(user, "id", None)
    if not user_id:
        return False

    cache_key = _recharge_notify_cache_key(user_id)
    try:
        if cache.get(cache_key):
            return False
    except Exception:
        pass

    try:
        from datetime import timedelta

        from notifications.models import Notification

        cutoff = timezone.now() - timedelta(seconds=RECHARGE_NOTIFY_CACHE_TTL)
        if Notification.objects.filter(
            recipient_id=user_id,
            event_type=RECHARGE_NOTIFY_EVENT,
            created__gte=cutoff,
        ).exists():
            try:
                cache.set(cache_key, 1, RECHARGE_NOTIFY_CACHE_TTL)
            except Exception:
                pass
            return False
    except Exception:
        logger.exception("LLM recharge notify: failed recent-notification check")

    try:
        if not cache.add(cache_key, 1, RECHARGE_NOTIFY_CACHE_TTL):
            return False
    except Exception:
        # If cache is down, still try DB-only throttle via emit dedupe bucket.
        pass

    try:
        from notifications.models import NotificationCategory
        from notifications.services import emit_notification, format_notification_message

        label = feature_label(feature)
        feature_clause = f" ({label})" if feature else ""
        balance_display = f"{max(0, int(balance)):,}"
        context = {
            "balance_display": balance_display,
            "balance_tokens": max(0, int(balance)),
            "estimated_cost": int(estimated_cost),
            "feature": feature or "",
            "feature_label": label,
            "feature_clause": feature_clause,
            "shop_url": shop_url(),
            "reason": reason,
        }
        title, body = format_notification_message(
            RECHARGE_NOTIFY_EVENT,
            context,
            default_title="Recharge AI tokens",
            default_body=(
                f"Your AI token balance ({balance_display}) is too low for your next AI action"
                f"{feature_clause}. Recharge a small pack to continue."
            ),
        )
        # Bucketed dedupe as a second guard (rolling day); primary throttle is 24h cache/DB.
        day_bucket = int(timezone.now().timestamp() // RECHARGE_NOTIFY_CACHE_TTL)
        emit_notification(
            event_type=RECHARGE_NOTIFY_EVENT,
            title=title,
            body=body,
            recipients=[user],
            category=NotificationCategory.SYSTEM,
            payload={
                "balance_tokens": max(0, int(balance)),
                "estimated_cost": int(estimated_cost),
                "feature": feature or "",
                "shop_url": shop_url(),
                "reason": reason,
                "cta_url": shop_url(),
                "cta_label": "Recharge AI tokens",
            },
            dedupe_key=f"llm_recharge:{user_id}:{day_bucket}",
        )
        return True
    except Exception:
        logger.exception("Failed to emit LLM recharge reminder for user=%s", user_id)
        return False


def check_and_notify_if_cannot_afford_next(
    user,
    *,
    balance: Optional[int] = None,
    feature: str = "other",
    request=None,
) -> bool:
    """True when balance is below the next-call estimate; may emit 24h recharge notification."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    role_key = resolve_role_key(user)
    cost = estimate_tokens_for_feature(feature or "other", role_key)
    if balance is None:
        balance = get_balance(user, request=request)
    if int(balance) >= int(cost):
        return False
    maybe_notify_recharge(
        user,
        balance=int(balance),
        estimated_cost=int(cost),
        feature=feature or "other",
        reason="below_next_call",
    )
    return True


def _anonymous_cache_key(request) -> str:
    session_key = ""
    if request is not None:
        session = getattr(request, "session", None)
        if session is not None:
            if not session.session_key:
                try:
                    session.save()
                except Exception:
                    pass
            session_key = session.session_key or ""
        ip = (
            (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
            or ""
        )
    else:
        ip = ""
    raw = f"{session_key}|{ip}|{current_period_key()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    return f"llm_anon_tokens:{digest}"


def get_anonymous_balance(request) -> int:
    role = get_role_default("anonymous")
    key = _anonymous_cache_key(request)
    cached = cache.get(key)
    if cached is None:
        cache.set(key, int(role.monthly_free_tokens), timeout=60 * 60 * 24 * 40)
        return int(role.monthly_free_tokens)
    return int(cached)


def debit_anonymous(request, tokens: int) -> int:
    key = _anonymous_cache_key(request)
    balance = get_anonymous_balance(request)
    new_balance = max(0, balance - max(0, int(tokens)))
    cache.set(key, new_balance, timeout=60 * 60 * 24 * 40)
    return new_balance


@transaction.atomic
def get_or_create_wallet(user):
    from core.models import UserLLMWallet

    wallet, _ = UserLLMWallet.objects.select_for_update().get_or_create(user=user)
    _apply_monthly_free_if_needed(wallet, user)
    wallet.refresh_from_db()
    return wallet


def _apply_monthly_free_if_needed(wallet, user) -> None:
    from core.models import LLMWalletLedger

    role_key = resolve_role_key(user)
    role = get_role_default(role_key)
    period = current_period_key()
    if wallet.free_period_key == period:
        return
    free_tokens = int(role.monthly_free_tokens or 0)
    wallet.free_period_key = period
    if free_tokens > 0 and role.is_enabled:
        wallet.balance_tokens = F("balance_tokens") + free_tokens
        wallet.lifetime_credited = F("lifetime_credited") + free_tokens
        wallet.save(update_fields=["balance_tokens", "lifetime_credited", "free_period_key"])
        wallet.refresh_from_db()
        LLMWalletLedger.objects.create(
            wallet=wallet,
            entry_type=LLMWalletLedger.ENTRY_CREDIT,
            source=LLMWalletLedger.SOURCE_FREE_MONTHLY,
            tokens=free_tokens,
            balance_after=wallet.balance_tokens,
            note=f"Monthly free allowance ({period})",
            reference=f"free:{user.id}:{period}",
            metadata={"role_key": role_key, "period": period},
        )
    else:
        wallet.save(update_fields=["free_period_key"])


@transaction.atomic
def credit_tokens(
    user,
    tokens: int,
    *,
    source: str,
    note: str = "",
    reference: str = "",
    created_by=None,
    metadata: Optional[dict] = None,
    feature: str = "",
) -> int:
    from core.models import LLMWalletLedger

    tokens = int(tokens or 0)
    if tokens <= 0:
        wallet = get_or_create_wallet(user)
        return int(wallet.balance_tokens)

    if reference:
        existing = LLMWalletLedger.objects.filter(
            source=source, reference=reference, entry_type=LLMWalletLedger.ENTRY_CREDIT
        ).first()
        if existing:
            return int(existing.balance_after)

    wallet = get_or_create_wallet(user)
    wallet.balance_tokens = F("balance_tokens") + tokens
    wallet.lifetime_credited = F("lifetime_credited") + tokens
    wallet.save(update_fields=["balance_tokens", "lifetime_credited", "updated_at"])
    wallet.refresh_from_db()
    LLMWalletLedger.objects.create(
        wallet=wallet,
        entry_type=LLMWalletLedger.ENTRY_CREDIT,
        source=source,
        tokens=tokens,
        balance_after=wallet.balance_tokens,
        feature=feature or "",
        note=(note or "")[:255],
        reference=(reference or "")[:64],
        created_by=created_by if getattr(created_by, "is_authenticated", False) else None,
        metadata=metadata or {},
    )
    return int(wallet.balance_tokens)


@transaction.atomic
def consume_llm_tokens(
    user,
    tokens: int,
    *,
    feature: str = "",
    reference: str = "",
    metadata: Optional[dict] = None,
    request=None,
) -> int:
    """Debit actual tokens after a successful LLM call. Never raises."""
    from core.models import LLMWalletLedger

    tokens = max(0, int(tokens or 0))
    if tokens <= 0:
        return 0

    try:
        if user is None or not getattr(user, "is_authenticated", False):
            return debit_anonymous(request, tokens)

        if reference:
            existing = LLMWalletLedger.objects.filter(
                source=LLMWalletLedger.SOURCE_USAGE,
                reference=reference,
                entry_type=LLMWalletLedger.ENTRY_DEBIT,
            ).first()
            if existing:
                return int(existing.balance_after)

        wallet = get_or_create_wallet(user)
        wallet.balance_tokens = F("balance_tokens") - tokens
        wallet.lifetime_consumed = F("lifetime_consumed") + tokens
        wallet.save(update_fields=["balance_tokens", "lifetime_consumed", "updated_at"])
        wallet.refresh_from_db()
        LLMWalletLedger.objects.create(
            wallet=wallet,
            entry_type=LLMWalletLedger.ENTRY_DEBIT,
            source=LLMWalletLedger.SOURCE_USAGE,
            tokens=tokens,
            balance_after=wallet.balance_tokens,
            feature=(feature or "")[:64],
            note=f"LLM usage ({feature})",
            reference=(reference or "")[:64],
            metadata=metadata or {},
        )
        remaining = int(wallet.balance_tokens)
        # After a successful call, warn once/24h if remaining balance cannot cover the next one.
        try:
            check_and_notify_if_cannot_afford_next(
                user,
                balance=remaining,
                feature=feature or "other",
                request=request,
            )
        except Exception:
            logger.exception("Post-consume low-balance notify failed")
        return remaining
    except Exception:
        logger.exception("Failed to consume LLM tokens for feature=%s", feature)
        return 0


def get_balance(user, request=None) -> int:
    if user is None or not getattr(user, "is_authenticated", False):
        return get_anonymous_balance(request)
    wallet = get_or_create_wallet(user)
    return int(wallet.balance_tokens)


def ensure_can_use_llm(
    user,
    *,
    feature: str,
    estimated_tokens: Optional[int] = None,
    request=None,
    raise_exception: bool = True,
) -> QuotaStatus:
    """
    Pre-flight quota check. Raises LLMQuotaExceeded when raise_exception=True.
    When balance is below the next-call estimate, emits a recharge notification
    at most once every 24 hours.
    """
    role_key = resolve_role_key(user)
    role = get_role_default(role_key)
    cost = int(estimated_tokens or estimate_tokens_for_feature(feature, role_key))

    if not role.is_enabled:
        paywall = build_paywall(
            role_key=role_key,
            balance=0,
            estimated_cost=cost,
            feature=feature,
            require_login=role_key == "anonymous",
        )
        paywall["message"] = "AI features are paused for your role"
        paywall["detail"] = (
            "An administrator has not enabled AI tokens for your account type yet. "
            "Please contact TopTeen support or ask an admin to grant tokens."
        )
        if user is not None and getattr(user, "is_authenticated", False):
            maybe_notify_recharge(
                user,
                balance=0,
                estimated_cost=cost,
                feature=feature,
                reason="role_disabled",
            )
        status = QuotaStatus(False, 0, role_key, cost, paywall)
        if raise_exception:
            raise LLMQuotaExceeded(paywall)
        return status

    if role_key == "anonymous":
        balance = get_anonymous_balance(request)
        if balance < cost:
            paywall = build_paywall(
                role_key=role_key,
                balance=balance,
                estimated_cost=cost,
                feature=feature,
                require_login=True,
            )
            status = QuotaStatus(False, balance, role_key, cost, paywall)
            if raise_exception:
                raise LLMQuotaExceeded(paywall)
            return status
        return QuotaStatus(True, balance, role_key, cost, None)

    wallet = get_or_create_wallet(user)
    balance = int(wallet.balance_tokens)
    if balance < cost:
        paywall = build_paywall(
            role_key=role_key,
            balance=balance,
            estimated_cost=cost,
            feature=feature,
            require_login=False,
        )
        maybe_notify_recharge(
            user,
            balance=balance,
            estimated_cost=cost,
            feature=feature,
            reason="insufficient_for_next_call",
        )
        status = QuotaStatus(False, balance, role_key, cost, paywall)
        if raise_exception:
            raise LLMQuotaExceeded(paywall)
        return status
    return QuotaStatus(True, balance, role_key, cost, None)


def apply_admin_grant(grant) -> int:
    """Credit wallet from an LLMAdminGrant row (idempotent)."""
    from core.models import LLMWalletLedger

    if grant.applied:
        return get_balance(grant.user)

    balance = credit_tokens(
        grant.user,
        grant.tokens,
        source=LLMWalletLedger.SOURCE_ADMIN_GRANT,
        note=grant.reason or "Admin grant",
        reference=f"grant:{grant.id}",
        created_by=grant.granted_by,
        metadata={"grant_id": grant.id},
    )
    if not grant.applied:
        grant.applied = True
        grant.save(update_fields=["applied"])
    return balance


def fulfill_package_payment(package_payment) -> int:
    """Credit tokens after successful package purchase (idempotent)."""
    from core.models import LLMWalletLedger

    if package_payment.tokens_credited:
        return get_balance(package_payment.user)

    tokens = int(package_payment.tokens_granted or 0)
    if tokens <= 0 and package_payment.package_id:
        tokens = int(package_payment.package.tokens or 0)
        package_payment.tokens_granted = tokens

    balance = credit_tokens(
        package_payment.user,
        tokens,
        source=LLMWalletLedger.SOURCE_PURCHASE,
        note=f"Purchased {getattr(package_payment.package, 'name', 'AI pack')}",
        reference=f"purchase:{package_payment.id}",
        metadata={
            "package_payment_id": package_payment.id,
            "package_id": package_payment.package_id,
        },
    )
    from core import choices

    package_payment.tokens_credited = True
    package_payment.is_success = choices.YesNoChoices.YES
    package_payment.save(
        update_fields=["tokens_credited", "is_success", "tokens_granted", "modified"]
    )
    try:
        from core.ai_feature_quota import grant_purchase_bonuses

        grant_purchase_bonuses(
            package_payment.user,
            reference=f"purchase:{package_payment.id}",
        )
    except Exception:
        logger.exception(
            "Failed granting AI feature bonuses for payment=%s",
            getattr(package_payment, "id", None),
        )
    return balance


def wallet_summary_for_user(user, request=None) -> dict[str, Any]:
    role_key = resolve_role_key(user)
    role = get_role_default(role_key)
    balance = get_balance(user, request=request)
    next_cost = estimate_tokens_for_feature("other", role_key)
    # Prefer role default so admin-tuned estimated_call_tokens drives soft low.
    next_cost = max(int(next_cost), int(role.estimated_call_tokens or 0) or next_cost)
    needs_recharge = balance < next_cost
    is_low = needs_recharge or balance < max(next_cost * 2, next_cost)
    return {
        "balance_tokens": balance,
        "role_key": role_key,
        "monthly_free_tokens": int(role.monthly_free_tokens or 0),
        "estimated_next_call_tokens": int(next_cost),
        "needs_recharge": needs_recharge,
        "is_low": is_low,
        "shop_url": shop_url(),
        "cta_label": "Recharge AI tokens" if needs_recharge or is_low else "",
        "cta_url": shop_url() if needs_recharge or is_low else "",
    }


def quota_error_response(exc: LLMQuotaExceeded, status: int = 402):
    """Django JsonResponse helper for API views."""
    from django.http import JsonResponse

    payload = dict(exc.payload or {})
    payload["error"] = payload.get("message") or "AI token limit reached"
    payload["quota_exceeded"] = True
    return JsonResponse(payload, status=status)
