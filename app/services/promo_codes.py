"""Promo code validation, discount math, and expiry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class PromoCodeError(Exception):
    """Raised when a promo code cannot be applied."""


HIGH_DISCOUNT_APPROVAL_THRESHOLD = 20


def requires_admin_approval(percent_off: Optional[int]) -> bool:
    """True when discount percent exceeds the threshold requiring admin sign-off."""
    return percent_off is not None and int(percent_off) > HIGH_DISCOUNT_APPROVAL_THRESHOLD


@dataclass(frozen=True)
class PromoDiscount:
    code: str
    subtotal_cents: int
    discount_cents: int
    final_cents: int
    percent_off: Optional[int]
    label: Optional[str]
    ends_at: str


def normalize_code(code: str) -> str:
    return code.strip().upper().replace(" ", "")


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def compute_discount_cents(row: Dict[str, Any], subtotal_cents: int) -> int:
    if subtotal_cents <= 0:
        return 0

    min_order = int(row.get("min_order_cents") or 0)
    if subtotal_cents < min_order:
        raise PromoCodeError(
            f"Minimum order is ${min_order / 100:.2f} for this code."
        )

    percent_off = row.get("percent_off")
    amount_off = row.get("amount_off_cents")

    if percent_off is not None:
        discount = int(round(subtotal_cents * int(percent_off) / 100))
    elif amount_off is not None:
        discount = int(amount_off)
    else:
        raise PromoCodeError("This promotion is misconfigured.")

    discount = max(0, min(discount, subtotal_cents - 1))
    if discount <= 0:
        raise PromoCodeError("This code does not apply to this order.")
    return discount


def validate_promo_row(
    row: Optional[Dict[str, Any]],
    *,
    subtotal_cents: int,
    now: Optional[datetime] = None,
) -> PromoDiscount:
    if not row:
        raise PromoCodeError("Invalid or expired promo code.")

    current = now or datetime.now(timezone.utc)
    if not row.get("is_active", True):
        raise PromoCodeError("This promotion has ended.")

    if requires_admin_approval(row.get("percent_off")) and not row.get("admin_approved", False):
        raise PromoCodeError(
            "This promotion is pending admin approval and cannot be used yet."
        )

    starts_at = _parse_ts(row["starts_at"])
    ends_at = _parse_ts(row["ends_at"])
    if current < starts_at:
        raise PromoCodeError("This promotion is not active yet.")
    if current > ends_at:
        raise PromoCodeError("This promotion has ended.")

    max_redemptions = row.get("max_redemptions")
    redemption_count = int(row.get("redemption_count") or 0)
    if max_redemptions is not None and redemption_count >= int(max_redemptions):
        raise PromoCodeError("This promotion has reached its usage limit.")

    discount_cents = compute_discount_cents(row, subtotal_cents)
    final_cents = subtotal_cents - discount_cents

    return PromoDiscount(
        code=str(row["code"]),
        subtotal_cents=subtotal_cents,
        discount_cents=discount_cents,
        final_cents=final_cents,
        percent_off=row.get("percent_off"),
        label=row.get("label"),
        ends_at=ends_at.isoformat(),
    )
