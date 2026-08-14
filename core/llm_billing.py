"""
Central LLM usage logging, estimated costs, and live provider billing.

- Per-call ledger: ``log_llm_usage`` / ``log_openai_response`` / ``log_gemini_response``
- Estimated USD from published list rates (local)
- Actual OpenAI organization costs/usage via Admin API (``OPENAI_ADMIN_API_KEY``)
- Amount collected: successful LLM token-package payments (INR)
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

logger = logging.getLogger(__name__)

OPENAI_API_BASE = "https://api.openai.com/v1"
PROVIDER_CACHE_TTL = 900  # 15 minutes

# Approximate public list prices (USD per 1M tokens). Update when rates change.
# Keys are lowercase model id substrings / exact names.
PRICE_PER_1M: dict[str, tuple[float, float]] = {
    # OpenAI chat
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # OpenAI embeddings (input only; output rate unused)
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
    "text-embedding-ada-002": (0.10, 0.0),
    # Gemini
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.15, 0.60),
    "embedding-001": (0.0, 0.0),
    "text-embedding-004": (0.0, 0.0),
}

DEFAULT_CHAT_RATES = (0.15, 0.60)  # gpt-4o-mini-ish fallback


def resolve_rates(model: str, call_type: str = "chat") -> tuple[float, float]:
    """Return (input_usd_per_1m, output_usd_per_1m) for a model name."""
    name = (model or "").strip().lower()
    if name in PRICE_PER_1M:
        return PRICE_PER_1M[name]
    for key, rates in PRICE_PER_1M.items():
        if key in name:
            return rates
    if call_type == "embedding":
        return (0.02, 0.0)
    return DEFAULT_CHAT_RATES


def estimate_cost_usd(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    call_type: str = "chat",
) -> Decimal:
    inp, out = resolve_rates(model, call_type=call_type)
    cost = (prompt_tokens * inp / 1_000_000) + (completion_tokens * out / 1_000_000)
    return Decimal(str(round(cost, 8)))


def tokens_from_openai_response(response: Any) -> tuple[int, int, int]:
    """Extract (prompt, completion, total) from an OpenAI chat/embedding response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
    # Embeddings often only set total_tokens
    if prompt == 0 and completion == 0 and total:
        prompt = total
    return prompt, completion, total


def tokens_from_gemini_response(response: Any) -> tuple[int, int, int]:
    """Extract tokens from a Gemini generate_content response when available."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0, 0
    prompt = int(
        getattr(meta, "prompt_token_count", None)
        or getattr(meta, "prompt_tokens", None)
        or 0
    )
    completion = int(
        getattr(meta, "candidates_token_count", None)
        or getattr(meta, "completion_tokens", None)
        or 0
    )
    total = int(getattr(meta, "total_token_count", None) or (prompt + completion) or 0)
    return prompt, completion, total


def log_llm_usage(
    *,
    feature: str,
    provider: str,
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: Optional[Decimal | float] = None,
    call_type: str = "chat",
    success: bool = True,
    error_message: str = "",
    user=None,
    request_id: str = "",
    metadata: Optional[dict] = None,
) -> Optional[Any]:
    """
    Persist one LLM call. Never raises — billing must not break product flows.
    """
    try:
        from core.models import LLMUsageLog

        prompt_tokens = int(prompt_tokens or 0)
        completion_tokens = int(completion_tokens or 0)
        total_tokens = int(total_tokens or 0) or (prompt_tokens + completion_tokens)

        if cost_usd is None:
            cost = estimate_cost_usd(
                model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                call_type=call_type,
            )
        else:
            cost = Decimal(str(cost_usd))

        return LLMUsageLog.objects.create(
            feature=feature,
            provider=(provider or "unknown")[:32],
            model=(model or "")[:128],
            call_type=(call_type or "chat")[:32],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            success=bool(success),
            error_message=(error_message or "")[:500],
            user=user if getattr(user, "is_authenticated", False) else None,
            request_id=(request_id or "")[:64],
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Failed to log LLM usage for feature=%s", feature)
        return None


def log_openai_response(
    *,
    feature: str,
    response: Any,
    model: str = "",
    call_type: str = "chat",
    user=None,
    metadata: Optional[dict] = None,
    consume: bool = False,
    request=None,
) -> Optional[Any]:
    prompt, completion, total = tokens_from_openai_response(response)
    row = log_llm_usage(
        feature=feature,
        provider="openai",
        model=model,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        call_type=call_type,
        user=user,
        metadata=metadata,
    )
    if consume and total:
        try:
            from core.llm_quota import consume_llm_tokens

            consume_llm_tokens(
                user,
                total,
                feature=feature,
                reference=f"usage:{getattr(row, 'id', '')}",
                request=request,
                metadata={"provider": "openai", "model": model},
            )
        except Exception:
            logger.exception("Failed wallet debit after OpenAI call feature=%s", feature)
    return row


def log_gemini_response(
    *,
    feature: str,
    response: Any,
    model: str = "",
    call_type: str = "chat",
    user=None,
    metadata: Optional[dict] = None,
    consume: bool = False,
    request=None,
) -> Optional[Any]:
    prompt, completion, total = tokens_from_gemini_response(response)
    row = log_llm_usage(
        feature=feature,
        provider="gemini",
        model=model,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        call_type=call_type,
        user=user,
        metadata=metadata,
    )
    if consume and total:
        try:
            from core.llm_quota import consume_llm_tokens

            consume_llm_tokens(
                user,
                total,
                feature=feature,
                reference=f"usage:{getattr(row, 'id', '')}",
                request=request,
                metadata={"provider": "gemini", "model": model},
            )
        except Exception:
            logger.exception("Failed wallet debit after Gemini call feature=%s", feature)
    return row


def _configured_openai_model() -> str:
    return (
        (getattr(settings, "OPENAI_MODEL", None) or "").strip()
        or (getattr(settings, "AI_MODEL", None) or "").strip()
        or "gpt-4o-mini"
    )


def _configured_gemini_model() -> str:
    return (getattr(settings, "GEMINI_MODEL", None) or "").strip() or "gemini-1.5-flash"


def _openai_api_key() -> str:
    """Use the same OPENAI_API_KEY already configured for app LLM calls."""
    return (getattr(settings, "OPENAI_API_KEY", None) or "").strip()


def _google_api_key() -> str:
    key = (getattr(settings, "GOOGLE_API_KEY", None) or "").strip()
    if not key or key.lower().startswith("your_google"):
        return ""
    return key


def _usd_to_inr_rate() -> float:
    try:
        rate = float(getattr(settings, "USD_TO_INR_RATE", 84) or 84)
    except (TypeError, ValueError):
        rate = 84.0
    return rate if rate > 0 else 84.0


def _openai_get(path: str, params: dict) -> dict:
    key = _openai_api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set in .env")
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{OPENAI_API_BASE}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {body or exc.reason}") from exc


def fetch_openai_usage_billing(days: int = 30, *, force_refresh: bool = False) -> dict:
    """
    Pull OpenAI usage via GET /v1/usage using OPENAI_API_KEY (same key as chat).

    Converts reported tokens to USD with rates for AI_MODEL / OPENAI_MODEL
    (or per-row snapshot_id when present).
    """
    days = max(1, min(int(days or 30), 90))
    cache_key = f"openai_usage_billing_v2_{days}"
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    default_model = _configured_openai_model()
    empty = {
        "configured": bool(_openai_api_key()),
        "ok": False,
        "source": "openai_/v1/usage",
        "error": "",
        "model_default": default_model,
        "cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "num_requests": 0,
        "daily": [],
        "by_model": [],
        "fetched_at": None,
    }

    if not _openai_api_key():
        empty["error"] = "OPENAI_API_KEY is not set in .env"
        cache.set(cache_key, empty, 120)
        return empty

    try:
        daily_map: dict[str, dict] = {}
        by_model: dict[str, dict] = {}
        input_tokens = 0
        output_tokens = 0
        num_requests = 0
        total_cost = 0.0

        today = timezone.localdate()
        for offset in range(days):
            day = today - timedelta(days=offset)
            day_s = day.isoformat()
            payload = _openai_get("/usage", {"date": day_s})
            rows = payload.get("data") or []
            day_in = day_out = day_req = 0
            day_cost = 0.0
            for row in rows:
                model = (row.get("snapshot_id") or row.get("model") or default_model or "").strip()
                inp = int(
                    row.get("n_context_tokens_total")
                    or row.get("n_prompt_tokens_total")
                    or row.get("input_tokens")
                    or 0
                )
                out = int(
                    row.get("n_generated_tokens_total")
                    or row.get("n_completion_tokens_total")
                    or row.get("output_tokens")
                    or 0
                )
                reqs = int(row.get("n_requests") or row.get("num_model_requests") or 0)
                cost = float(estimate_cost_usd(model or default_model, inp, out, call_type="chat"))
                input_tokens += inp
                output_tokens += out
                num_requests += reqs
                total_cost += cost
                day_in += inp
                day_out += out
                day_req += reqs
                day_cost += cost
                mkey = model or default_model
                mrow = by_model.setdefault(
                    mkey,
                    {
                        "model": mkey,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "num_requests": 0,
                        "cost_usd": 0.0,
                    },
                )
                mrow["input_tokens"] += inp
                mrow["output_tokens"] += out
                mrow["num_requests"] += reqs
                mrow["cost_usd"] += cost

            if day_in or day_out or day_req or day_cost:
                daily_map[day_s] = {
                    "day": day_s,
                    "input_tokens": day_in,
                    "output_tokens": day_out,
                    "num_requests": day_req,
                    "cost_usd": round(day_cost, 6),
                }

        result = {
            "configured": True,
            "ok": True,
            "source": "openai_/v1/usage + OPENAI_API_KEY",
            "error": "",
            "model_default": default_model,
            "cost_usd": round(total_cost, 6),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "num_requests": num_requests,
            "daily": [daily_map[k] for k in sorted(daily_map.keys(), reverse=True)],
            "by_model": sorted(by_model.values(), key=lambda r: -r["cost_usd"]),
            "fetched_at": timezone.now().isoformat(),
            "empty_usage": not bool(input_tokens or output_tokens or num_requests),
        }
        cache.set(cache_key, result, PROVIDER_CACHE_TTL)
        return result
    except Exception as exc:
        logger.warning("OpenAI /v1/usage fetch failed: %s", exc)
        empty["error"] = str(exc)[:500]
        empty["fetched_at"] = timezone.now().isoformat()
        cache.set(cache_key, empty, 120)
        return empty


def get_local_provider_expense(days: int = 30) -> dict:
    """
    Expense from local LLMUsageLog, priced with AI_MODEL / GEMINI_MODEL when needed.

    Used as the authoritative app-side expense (and fallback when OpenAI /usage is empty).
    """
    from core.models import LLMUsageLog

    days = max(1, min(int(days or 30), 365))
    since = timezone.now() - timedelta(days=days)
    qs = LLMUsageLog.objects.filter(created_at__gte=since, success=True)

    openai_model = _configured_openai_model()
    gemini_model = _configured_gemini_model()

    openai_in = openai_out = openai_calls = 0
    gemini_in = gemini_out = gemini_calls = 0
    openai_cost = Decimal("0")
    gemini_cost = Decimal("0")
    by_feature: dict[str, dict] = {}

    for row in qs.iterator():
        provider = (row.provider or "").lower()
        model = (row.model or "").strip()
        prompt = int(row.prompt_tokens or 0)
        completion = int(row.completion_tokens or 0)
        call_type = row.call_type or "chat"
        feature = row.feature or "other"

        if provider in ("openai", "gpt"):
            model = model or openai_model
            cost = estimate_cost_usd(model, prompt, completion, call_type=call_type)
            openai_in += prompt
            openai_out += completion
            openai_calls += 1
            openai_cost += cost
        elif provider in ("gemini", "google"):
            model = model or gemini_model
            cost = estimate_cost_usd(model, prompt, completion, call_type=call_type)
            gemini_in += prompt
            gemini_out += completion
            gemini_calls += 1
            gemini_cost += cost
        else:
            cost = Decimal(str(row.cost_usd or 0))

        feat = by_feature.setdefault(
            feature,
            {"feature": feature, "calls": 0, "total_tokens": 0, "cost_usd": Decimal("0")},
        )
        feat["calls"] += 1
        feat["total_tokens"] += int(row.total_tokens or (prompt + completion))
        feat["cost_usd"] += cost

    return {
        "openai": {
            "configured": bool(_openai_api_key()),
            "model": openai_model,
            "calls": openai_calls,
            "input_tokens": openai_in,
            "output_tokens": openai_out,
            "total_tokens": openai_in + openai_out,
            "cost_usd": float(openai_cost),
        },
        "gemini": {
            "configured": bool(_google_api_key()),
            "model": gemini_model,
            "calls": gemini_calls,
            "input_tokens": gemini_in,
            "output_tokens": gemini_out,
            "total_tokens": gemini_in + gemini_out,
            "cost_usd": float(gemini_cost),
        },
        "by_feature": [
            {
                "feature": v["feature"],
                "calls": v["calls"],
                "total_tokens": v["total_tokens"],
                "cost_usd": float(v["cost_usd"]),
            }
            for v in sorted(by_feature.values(), key=lambda x: -float(x["cost_usd"]))
        ],
        "cost_usd": float(openai_cost + gemini_cost),
    }


def get_amount_collected(days: int = 30) -> dict:
    """
    Successful payments in the window.

    - llm_collected_inr: AI token package sales only
    - total_collected_inr: all successful gateway payments
    """
    from core import choices
    from payments.models import Payment

    days = max(1, min(int(days or 30), 365))
    since = timezone.now() - timedelta(days=days)
    base = Payment.objects.filter(
        is_success=choices.YesNoChoices.YES,
        created__gte=since,
    )
    if hasattr(Payment, "is_test_payment"):
        base = base.filter(is_test_payment=False)

    llm_qs = base.filter(obj_type=choices.PaymentObjectType.LLM_TOKEN_PACKAGE)
    llm_agg = llm_qs.aggregate(total=Sum("amount"), count=Count("id"))
    all_agg = base.aggregate(total=Sum("amount"), count=Count("id"))

    llm_daily = list(
        llm_qs.annotate(day=TruncDate("created"))
        .values("day")
        .annotate(amount=Sum("amount"), count=Count("id"))
        .order_by("-day")[:days]
    )

    return {
        "llm_collected_inr": int(llm_agg["total"] or 0),
        "llm_payment_count": int(llm_agg["count"] or 0),
        "total_collected_inr": int(all_agg["total"] or 0),
        "total_payment_count": int(all_agg["count"] or 0),
        "llm_daily": llm_daily,
    }


def get_billing_summary(days: int = 30, *, force_refresh: bool = False) -> dict:
    """Aggregate OpenAI usage API + local logs (Gemini) + amount collected."""
    from core.models import LLMUsageLog
    from forum.models import PerformanceMetrics

    days = max(1, min(int(days or 30), 365))
    since = timezone.now() - timedelta(days=days)
    qs = LLMUsageLog.objects.filter(created_at__gte=since, success=True)

    totals = qs.aggregate(
        calls=Count("id"),
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        total_tokens=Sum("total_tokens"),
        cost_usd=Sum("cost_usd"),
    )

    by_provider = list(
        qs.values("provider", "model")
        .annotate(
            calls=Count("id"),
            total_tokens=Sum("total_tokens"),
            cost_usd=Sum("cost_usd"),
        )
        .order_by("-cost_usd")
    )

    daily = list(
        qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            calls=Count("id"),
            total_tokens=Sum("total_tokens"),
            cost_usd=Sum("cost_usd"),
        )
        .order_by("-day")[:days]
    )

    forum_since = timezone.localdate() - timedelta(days=days)
    forum_metrics = list(
        PerformanceMetrics.objects.filter(date__gte=forum_since).order_by("-date")[:days]
    )
    forum_cost = sum((m.total_cost_usd or 0.0) for m in forum_metrics)
    forum_ai_calls = sum((m.ai_generated or 0) for m in forum_metrics)

    recent = list(LLMUsageLog.objects.order_by("-created_at")[:40])

    openai_usage = fetch_openai_usage_billing(
        days=min(days, 90), force_refresh=force_refresh
    )
    local_expense = get_local_provider_expense(days=days)
    collected = get_amount_collected(days=days)
    usd_inr = _usd_to_inr_rate()

    # Prefer OpenAI /v1/usage tokens when the API returned data; else local OpenAI logs.
    if openai_usage.get("ok") and not openai_usage.get("empty_usage"):
        openai_cost_usd = float(openai_usage.get("cost_usd") or 0)
        openai_source = "OPENAI_API_KEY → /v1/usage"
    else:
        openai_cost_usd = float(local_expense["openai"]["cost_usd"] or 0)
        openai_source = f"local logs × {local_expense['openai']['model']} (AI_MODEL/OPENAI_MODEL)"

    gemini_cost_usd = float(local_expense["gemini"]["cost_usd"] or 0)
    expense_usd = round(openai_cost_usd + gemini_cost_usd, 6)
    expense_inr = round(expense_usd * usd_inr, 2)
    llm_collected = int(collected["llm_collected_inr"] or 0)
    margin_inr = round(llm_collected - expense_inr, 2)
    stored_estimate = float(totals["cost_usd"] or 0)

    return {
        "days": days,
        "since": since,
        "totals": {
            "calls": totals["calls"] or 0,
            "prompt_tokens": totals["prompt_tokens"] or 0,
            "completion_tokens": totals["completion_tokens"] or 0,
            "total_tokens": totals["total_tokens"] or 0,
            "cost_usd": stored_estimate,
        },
        "by_feature": local_expense["by_feature"],
        "by_provider": by_provider,
        "daily": daily,
        "forum_metrics": forum_metrics,
        "forum_cost_usd": forum_cost,
        "forum_ai_calls": forum_ai_calls,
        "recent": recent,
        "openai_usage": openai_usage,
        # Keep alias used by older template blocks
        "openai_actual": {
            "configured": openai_usage.get("configured"),
            "ok": openai_usage.get("ok"),
            "error": openai_usage.get("error") or "",
            "cost_usd": openai_cost_usd,
            "fetched_at": openai_usage.get("fetched_at"),
            "by_line_item": [],
            "daily_costs": [
                {"day": d["day"], "cost_usd": d["cost_usd"]} for d in openai_usage.get("daily") or []
            ],
            "completions": {
                "input_tokens": openai_usage.get("input_tokens")
                or local_expense["openai"]["input_tokens"],
                "output_tokens": openai_usage.get("output_tokens")
                or local_expense["openai"]["output_tokens"],
                "total_tokens": (
                    openai_usage.get("total_tokens")
                    if (openai_usage.get("ok") and not openai_usage.get("empty_usage"))
                    else local_expense["openai"]["total_tokens"]
                ),
                "num_model_requests": openai_usage.get("num_requests")
                or local_expense["openai"]["calls"],
                "by_model": openai_usage.get("by_model") or [],
                "daily": openai_usage.get("daily") or [],
            },
            "embeddings": {"input_tokens": 0, "num_model_requests": 0},
        },
        "local_expense": local_expense,
        "collected": collected,
        "usd_to_inr": usd_inr,
        "config_models": {
            "ai_model": getattr(settings, "AI_MODEL", "") or "",
            "openai_model": getattr(settings, "OPENAI_MODEL", "") or "",
            "gemini_model": _configured_gemini_model(),
            "openai_key_set": bool(_openai_api_key()),
            "google_key_set": bool(_google_api_key()),
        },
        "pnl": {
            "actual_cost_usd": expense_usd,
            "actual_cost_inr": expense_inr,
            "openai_cost_usd": openai_cost_usd,
            "gemini_cost_usd": gemini_cost_usd,
            "openai_source": openai_source,
            "gemini_source": f"local logs × {local_expense['gemini']['model']} (GEMINI_MODEL)",
            "llm_collected_inr": llm_collected,
            "margin_inr": margin_inr,
            "estimated_cost_usd": stored_estimate,
            "estimate_vs_actual_usd": round(stored_estimate - expense_usd, 6),
        },
        "pricing_note": (
            "Expense uses OPENAI_API_KEY (/v1/usage when it returns data, else local token logs) "
            "priced with AI_MODEL/OPENAI_MODEL, plus Gemini local logs priced with GEMINI_MODEL. "
            "Amount collected = successful LLM token-package payments."
        ),
    }
