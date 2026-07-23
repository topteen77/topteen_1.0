"""
Per-feature AI quotas for students and parents only.

Counselor and other roles are never gated. AI Counselor / Chat-with-page are
unlimited unless admin sets a positive message limit.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import transaction
from django.db.models import F
from django.urls import reverse

logger = logging.getLogger(__name__)

FEATURE_RESUME_CREATE = "resume_create"
FEATURE_RESUME_AI = "resume_ai"
FEATURE_COUNSELLOR = "counsellor"
FEATURE_PAGE_CHAT = "page_chat"

ALL_FEATURES = (
    FEATURE_RESUME_CREATE,
    FEATURE_RESUME_AI,
    FEATURE_COUNSELLOR,
    FEATURE_PAGE_CHAT,
)

RECHARGE_MESSAGE = "AI tokens need to recharge — Buy now."
CTA_LABEL = "Buy now"

_USED_FIELD = {
    FEATURE_RESUME_CREATE: "resume_creates_used",
    FEATURE_RESUME_AI: "resume_ai_edits_used",
    FEATURE_COUNSELLOR: "counsellor_messages_used",
    FEATURE_PAGE_CHAT: "page_chat_messages_used",
}
_BONUS_FIELD = {
    FEATURE_RESUME_CREATE: "resume_create_bonus",
    FEATURE_RESUME_AI: "resume_ai_bonus",
    FEATURE_COUNSELLOR: "counsellor_bonus",
    FEATURE_PAGE_CHAT: "page_chat_bonus",
}


class AIFeatureQuotaExceeded(Exception):
    """Raised when a student/parent cannot afford a feature action."""

    def __init__(self, payload: dict):
        self.payload = payload or {}
        super().__init__(self.payload.get("message") or RECHARGE_MESSAGE)


def shop_url() -> str:
    try:
        return reverse("core:llm_token_packages")
    except Exception:
        return "/ai-tokens/"


def quota_applies(user) -> bool:
    """Only students and parents are gated."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    from core import choices

    return getattr(user, "user_type", None) in (
        choices.UserType.STUDENT,
        choices.UserType.PARENT,
    )


def get_settings():
    from core.models import AIFeatureQuotaSettings

    return AIFeatureQuotaSettings.load()


def get_or_create_usage(user):
    from core.models import UserAIFeatureUsage
    from users.models import UserResume

    usage, created = UserAIFeatureUsage.objects.get_or_create(user=user)
    # Sync create counter with existing resumes so prior users don't get a free extra.
    try:
        actual = UserResume.objects.filter(user=user).count()
    except Exception:
        actual = 0
    if actual > int(usage.resume_creates_used or 0):
        usage.resume_creates_used = actual
        usage.save(update_fields=["resume_creates_used", "updated_at"])
    return usage


def _admin_cap(settings_row, feature: str) -> Optional[int]:
    """Return None for unlimited bot features; int cap otherwise."""
    if feature == FEATURE_RESUME_CREATE:
        return int(settings_row.resume_free_creates or 0)
    if feature == FEATURE_RESUME_AI:
        return int(settings_row.resume_free_ai_edits or 0)
    if feature == FEATURE_COUNSELLOR:
        lim = settings_row.counsellor_message_limit
        if lim is None or int(lim) <= 0:
            return None
        return int(lim)
    if feature == FEATURE_PAGE_CHAT:
        lim = settings_row.page_chat_message_limit
        if lim is None or int(lim) <= 0:
            return None
        return int(lim)
    return 0


def _allowance(settings_row, usage, feature: str) -> tuple[bool, int]:
    """
    Returns (unlimited, remaining).
    remaining is ignored when unlimited is True.
    """
    bonus = int(getattr(usage, _BONUS_FIELD[feature], 0) or 0)
    used = int(getattr(usage, _USED_FIELD[feature], 0) or 0)
    cap = _admin_cap(settings_row, feature)
    if feature in (FEATURE_COUNSELLOR, FEATURE_PAGE_CHAT) and cap is None:
        return True, 0
    base = int(cap or 0)
    remaining = max(0, base + bonus - used)
    return False, remaining


def build_locked_payload(feature: str) -> dict[str, Any]:
    return {
        "code": "ai_feature_quota_exceeded",
        "message": RECHARGE_MESSAGE,
        "detail": RECHARGE_MESSAGE,
        "headline": RECHARGE_MESSAGE,
        "body": RECHARGE_MESSAGE,
        "feature": feature,
        "quota_exceeded": True,
        "needs_recharge": True,
        "cta_label": CTA_LABEL,
        "cta_url": shop_url(),
        "shop_url": shop_url(),
    }


def feature_status(user, feature: str, request=None) -> dict[str, Any]:
    if feature not in ALL_FEATURES:
        raise ValueError(f"Unknown feature: {feature}")

    if not quota_applies(user):
        return {
            "feature": feature,
            "applies": False,
            "unlimited": True,
            "remaining": None,
            "used": 0,
            "locked": False,
            "message": "",
            "cta_label": "",
            "cta_url": "",
            "shop_url": shop_url(),
        }

    settings_row = get_settings()
    usage = get_or_create_usage(user)
    unlimited, remaining = _allowance(settings_row, usage, feature)
    used = int(getattr(usage, _USED_FIELD[feature], 0) or 0)
    locked = (not unlimited) and remaining <= 0
    payload = {
        "feature": feature,
        "applies": True,
        "unlimited": unlimited,
        "remaining": None if unlimited else remaining,
        "used": used,
        "locked": locked,
        "message": RECHARGE_MESSAGE if locked else "",
        "cta_label": CTA_LABEL if locked else "",
        "cta_url": shop_url() if locked else "",
        "shop_url": shop_url(),
    }
    return payload


def status_for_user(user, request=None) -> dict[str, Any]:
    features = {f: feature_status(user, f, request=request) for f in ALL_FEATURES}
    balance_tokens = 0
    try:
        from core.llm_quota import get_balance

        balance_tokens = int(get_balance(user, request=request) or 0)
    except Exception:
        balance_tokens = 0
    return {
        "applies": quota_applies(user),
        "message": RECHARGE_MESSAGE,
        "cta_label": CTA_LABEL,
        "shop_url": shop_url(),
        "balance_tokens": balance_tokens,
        "features": features,
    }


def ensure_can_use_feature(
    user,
    feature: str,
    *,
    request=None,
    raise_exception: bool = True,
) -> dict[str, Any]:
    status = feature_status(user, feature, request=request)
    if status.get("locked"):
        payload = build_locked_payload(feature)
        if raise_exception:
            raise AIFeatureQuotaExceeded(payload)
        return {**status, **payload}
    return status


@transaction.atomic
def consume_feature(
    user,
    feature: str,
    *,
    amount: int = 1,
    request=None,
    raise_exception: bool = True,
) -> dict[str, Any]:
    """Increment usage after a successful action. No-op when not gated.

    When bots are unlimited, usage is not incremented (no cap to track against).
    """
    if feature not in ALL_FEATURES:
        raise ValueError(f"Unknown feature: {feature}")
    amount = max(1, int(amount or 1))

    if not quota_applies(user):
        return feature_status(user, feature, request=request)

    from core.models import UserAIFeatureUsage

    get_or_create_usage(user)
    settings_row = get_settings()
    usage = UserAIFeatureUsage.objects.select_for_update().get(user=user)

    if feature == FEATURE_RESUME_CREATE:
        from users.models import UserResume

        actual = UserResume.objects.filter(user=user).count()
        if actual > int(usage.resume_creates_used or 0):
            usage.resume_creates_used = actual
            usage.save(update_fields=["resume_creates_used", "updated_at"])
            usage.refresh_from_db()

    unlimited, remaining = _allowance(settings_row, usage, feature)
    if unlimited:
        return feature_status(user, feature, request=request)

    if remaining < amount:
        payload = build_locked_payload(feature)
        if raise_exception:
            raise AIFeatureQuotaExceeded(payload)
        return {**feature_status(user, feature, request=request), **payload}

    used_field = _USED_FIELD[feature]
    if feature == FEATURE_RESUME_CREATE:
        from users.models import UserResume

        # Align counter to actual resumes after create (avoids double-count with sync).
        usage.resume_creates_used = UserResume.objects.filter(user=user).count()
        usage.save(update_fields=["resume_creates_used", "updated_at"])
    else:
        setattr(usage, used_field, F(used_field) + amount)
        usage.save(update_fields=[used_field, "updated_at"])
    usage.refresh_from_db()
    return feature_status(user, feature, request=request)


def grant_purchase_bonuses(user, *, reference: str = "") -> dict[str, int]:
    """Add configurable bonus credits after an AI token pack purchase."""
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    settings_row = get_settings()
    usage = get_or_create_usage(user)
    bonuses = {
        "resume_create_bonus": int(settings_row.purchase_bonus_resume_creates or 0),
        "resume_ai_bonus": int(settings_row.purchase_bonus_resume_ai or 0),
        "counsellor_bonus": int(settings_row.purchase_bonus_counsellor or 0),
        "page_chat_bonus": int(settings_row.purchase_bonus_page_chat or 0),
    }
    update_fields = []
    for field, delta in bonuses.items():
        if delta > 0:
            setattr(usage, field, F(field) + delta)
            update_fields.append(field)
    if update_fields:
        update_fields.append("updated_at")
        usage.save(update_fields=update_fields)
        usage.refresh_from_db()
        logger.info(
            "Granted AI feature bonuses user=%s ref=%s bonuses=%s",
            getattr(user, "id", None),
            reference,
            bonuses,
        )
    return bonuses


def feature_quota_error_response(exc: AIFeatureQuotaExceeded, status: int = 402):
    from django.http import JsonResponse

    payload = dict(exc.payload or {})
    payload["error"] = payload.get("message") or RECHARGE_MESSAGE
    payload["quota_exceeded"] = True
    return JsonResponse(payload, status=status)
