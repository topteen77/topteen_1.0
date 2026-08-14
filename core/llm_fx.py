"""
USD → INR conversion helpers for AI token package checkout.

Provider LLM cost is tracked in USD; packs are sold in INR using the admin
rate from ``LLMPricingSettings``.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Union

Number = Union[Decimal, float, int, str]


def _as_decimal(value: Number, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def get_pricing_settings():
    from core.models import LLMPricingSettings

    return LLMPricingSettings.load()


def get_usd_to_inr_rate() -> Decimal:
    settings_row = get_pricing_settings()
    rate = _as_decimal(settings_row.usd_to_inr_rate, "83")
    if rate <= 0:
        return Decimal("83")
    return rate


def usd_to_inr_amount(price_usd: Number, rate: Optional[Number] = None) -> int:
    """Convert USD list price to whole INR for gateway charge (half-up)."""
    usd = _as_decimal(price_usd)
    fx = _as_decimal(rate) if rate is not None else get_usd_to_inr_rate()
    if fx <= 0:
        fx = get_usd_to_inr_rate()
    inr = (usd * fx).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(0, int(inr))


def format_usd(price_usd: Number) -> str:
    usd = _as_decimal(price_usd)
    # Trim trailing zeros for display: $1.80 or $0.59
    text = f"{usd.normalize():f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"${text}"


def format_rate(rate: Optional[Number] = None) -> str:
    fx = _as_decimal(rate) if rate is not None else get_usd_to_inr_rate()
    text = f"{fx.normalize():f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"1 USD = ₹ {text}"


def package_pricing_dict(package) -> dict:
    """Storefront pricing payload for one package (respects admin display toggles)."""
    settings_row = get_pricing_settings()
    rate = get_usd_to_inr_rate()
    inr = usd_to_inr_amount(package.price_usd, rate=rate)
    show_inr = bool(settings_row.show_price_inr)
    show_usd = bool(settings_row.show_price_usd)
    show_rate = bool(settings_row.show_exchange_rate)
    show_note = bool(settings_row.show_conversion_note)
    return {
        "price_usd": package.price_usd,
        "price_usd_display": format_usd(package.price_usd) if show_usd else "",
        "amount_inr": inr,
        "amount_inr_display": f"₹ {inr}" if show_inr else "",
        "usd_to_inr_rate": rate,
        "rate_display": format_rate(rate) if show_rate else "",
        "show_price_inr": show_inr,
        "show_price_usd": show_usd,
        "show_exchange_rate": show_rate,
        "show_conversion_note": show_note,
        "conversion_note": (settings_row.conversion_note or "").strip() if show_note else "",
    }


def storefront_display_flags() -> dict:
    settings_row = get_pricing_settings()
    return {
        "show_price_inr": bool(settings_row.show_price_inr),
        "show_price_usd": bool(settings_row.show_price_usd),
        "show_exchange_rate": bool(settings_row.show_exchange_rate),
        "show_conversion_note": bool(settings_row.show_conversion_note),
        "conversion_note": (
            (settings_row.conversion_note or "").strip()
            if settings_row.show_conversion_note
            else ""
        ),
        "usd_to_inr_rate": get_usd_to_inr_rate(),
        "rate_display": (
            format_rate() if settings_row.show_exchange_rate else ""
        ),
    }
