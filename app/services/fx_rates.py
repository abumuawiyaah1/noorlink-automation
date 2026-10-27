"""USD → retail FX for PayPal local-currency charges.

Mirrors the site fallback table; optionally refreshes from open.er-api.com.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Currencies PayPal Business account has enabled for checkout (user-confirmed).
PAYPAL_CHARGE_CURRENCIES = frozenset({"USD", "EUR", "GBP", "CAD", "MXN"})

FALLBACK_RATES_USD: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "CAD": 1.36,
    "AUD": 1.53,
    "MXN": 17.2,
    "SAR": 3.75,
    "AED": 3.67,
    "QAR": 3.64,
    "KWD": 0.31,
    "BHD": 0.38,
    "OMR": 0.39,
    "EGP": 50.5,
    "TRY": 34.5,
    "JPY": 149.0,
    "SGD": 1.34,
    "CHF": 0.88,
    "NZD": 1.66,
    "ZAR": 18.2,
    "PLN": 3.95,
    "SEK": 10.5,
    "NOK": 10.7,
    "DKK": 6.85,
    "THB": 35.5,
}

_CACHE_TTL_SEC = 12 * 60 * 60
_rates_cache: Dict[str, float] = dict(FALLBACK_RATES_USD)
_rates_fetched_at: float = 0.0


def normalize_currency(code: Optional[str]) -> str:
    raw = (code or "USD").strip().upper()
    return raw if raw else "USD"


def resolve_paypal_charge_currency(preferred: Optional[str]) -> str:
    """Map shopper preference to a currency PayPal can actually charge."""
    code = normalize_currency(preferred)
    if code in PAYPAL_CHARGE_CURRENCIES:
        return code
    return "USD"


def _refresh_rates_if_stale() -> None:
    global _rates_cache, _rates_fetched_at
    now = time.time()
    if _rates_fetched_at and (now - _rates_fetched_at) < _CACHE_TTL_SEC:
        return
    try:
        response = httpx.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=8.0,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("result") not in (None, "success"):
            raise ValueError("FX provider error")
        partial = data.get("rates") or {}
        merged = dict(FALLBACK_RATES_USD)
        for code, value in partial.items():
            if isinstance(value, (int, float)) and float(value) > 0:
                merged[str(code).upper()] = float(value)
        merged["USD"] = 1.0
        _rates_cache = merged
        _rates_fetched_at = now
    except Exception as exc:
        logger.warning("FX refresh failed; using cached/fallback rates: %s", exc)
        if not _rates_fetched_at:
            _rates_cache = dict(FALLBACK_RATES_USD)
            _rates_fetched_at = now


def get_usd_rate(currency: str) -> float:
    code = normalize_currency(currency)
    _refresh_rates_if_stale()
    return float(_rates_cache.get(code) or FALLBACK_RATES_USD.get(code) or 1.0)


def convert_usd_to(amount_usd: float, currency: str, *, decimals: int = 2) -> float:
    """Convert a USD major-unit amount into `currency`, rounded for retail."""
    code = normalize_currency(currency)
    if code == "USD":
        return round(float(amount_usd), decimals)
    rate = get_usd_rate(code)
    factor = 10 ** decimals
    return round(float(amount_usd) * rate * factor) / factor


def format_paypal_amount(amount: float, currency: str) -> str:
    """PayPal amount.value string (usually 2 decimal places)."""
    code = normalize_currency(currency)
    # JPY-style zero-decimal not in PayPal charge set; keep 2dp for enabled set.
    _ = code
    return f"{float(amount):.2f}"
