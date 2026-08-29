"""Admin helpers for promo code management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.services.promo_codes import normalize_code, requires_admin_approval


class AdminPromoError(Exception):
    """Promo admin operation failed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_promo_payload(data: Dict[str, Any], *, is_create: bool) -> Dict[str, Any]:
    """Normalize and validate promo form data before save."""
    cleaned = dict(data)

    code = normalize_code(str(cleaned.get("code") or ""))
    if not code:
        raise AdminPromoError("Promo code is required.")
    if len(code) > 64:
        raise AdminPromoError("Promo code is too long.")
    cleaned["code"] = code

    label = str(cleaned.get("label") or "").strip()
    cleaned["label"] = label or None

    percent = cleaned.get("percent_off")
    amount = cleaned.get("amount_off_cents")

    if percent in ("", None):
        percent = None
    else:
        percent = int(percent)

    if amount in ("", None):
        amount = None
    else:
        amount = int(amount)

    if percent is not None and amount is not None:
        raise AdminPromoError("Use either percent off or fixed amount off — not both.")
    if percent is None and amount is None:
        raise AdminPromoError("Set percent off or fixed amount off (cents).")
    if percent is not None and not (0 < percent <= 90):
        raise AdminPromoError("Percent off must be between 1 and 90.")
    if amount is not None and amount <= 0:
        raise AdminPromoError("Amount off must be greater than zero.")

    cleaned["percent_off"] = percent
    cleaned["amount_off_cents"] = amount

    starts_at = cleaned.get("starts_at")
    ends_at = cleaned.get("ends_at")
    if starts_at is None or ends_at is None:
        raise AdminPromoError("Start and end dates are required.")

    if isinstance(starts_at, str):
        starts_at = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    if isinstance(ends_at, str):
        ends_at = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    if ends_at <= starts_at:
        raise AdminPromoError("End date must be after start date.")

    cleaned["starts_at"] = starts_at
    cleaned["ends_at"] = ends_at

    max_redemptions = cleaned.get("max_redemptions")
    if max_redemptions in ("", None):
        cleaned["max_redemptions"] = None
    else:
        max_redemptions = int(max_redemptions)
        if max_redemptions <= 0:
            raise AdminPromoError("Max redemptions must be positive or empty for unlimited.")
        cleaned["max_redemptions"] = max_redemptions

    min_order = cleaned.get("min_order_cents")
    cleaned["min_order_cents"] = max(0, int(min_order or 0))

    slug = str(cleaned.get("insider_issue_slug") or "").strip()
    cleaned["insider_issue_slug"] = slug or None

    if is_create:
        cleaned.setdefault("is_active", True)
        cleaned.setdefault("redemption_count", 0)

    return cleaned


def apply_promo_approval_rules(
    validated: Dict[str, Any],
    *,
    is_create: bool,
    editor_is_admin: bool,
    editor_username: str,
    existing: Optional[Any] = None,
) -> Dict[str, Any]:
    """Set admin_approved fields for codes above the discount threshold."""
    percent = validated.get("percent_off")
    if not requires_admin_approval(percent):
        validated["admin_approved"] = True
        validated["admin_approved_by"] = None
        validated["admin_approved_at"] = None
        return validated

    if editor_is_admin:
        validated["admin_approved"] = True
        validated["admin_approved_by"] = editor_username
        validated["admin_approved_at"] = _utc_now()
        return validated

    unchanged_high_discount = (
        not is_create
        and existing is not None
        and getattr(existing, "admin_approved", False)
        and getattr(existing, "percent_off", None) == percent
    )
    if unchanged_high_discount:
        validated["admin_approved"] = True
        validated["admin_approved_by"] = getattr(existing, "admin_approved_by", None)
        validated["admin_approved_at"] = getattr(existing, "admin_approved_at", None)
        return validated

    validated["admin_approved"] = False
    validated["admin_approved_by"] = None
    validated["admin_approved_at"] = None
    return validated


def promo_status_label(
    *,
    is_active: bool,
    starts_at: datetime,
    ends_at: datetime,
    percent_off: Optional[int] = None,
    admin_approved: bool = True,
    now: Optional[datetime] = None,
) -> str:
    current = now or _utc_now()
    if requires_admin_approval(percent_off) and not admin_approved:
        return "Pending approval"
    if not is_active:
        return "Disabled"
    if current < starts_at:
        return "Scheduled"
    if current > ends_at:
        return "Expired"
    return "Active"


def days_remaining(ends_at: datetime, now: Optional[datetime] = None) -> int:
    current = now or _utc_now()
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    delta = ends_at - current
    return max(0, int(delta.total_seconds() // 86400))


def extend_promo_end(promo: Any, *, days: int) -> datetime:
    if days <= 0:
        raise AdminPromoError("Extension days must be positive.")
    ends_at = promo.ends_at
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    base = max(ends_at, _utc_now())
    new_end = base + timedelta(days=days)
    promo.ends_at = new_end
    promo.is_active = True
    return new_end


def approve_high_discount_promo(promo: Any, *, admin_username: str) -> None:
    """Mark a >20% promo as admin-approved."""
    if not requires_admin_approval(getattr(promo, "percent_off", None)):
        promo.admin_approved = True
        promo.admin_approved_by = admin_username
        promo.admin_approved_at = _utc_now()
        return
    promo.admin_approved = True
    promo.admin_approved_by = admin_username
    promo.admin_approved_at = _utc_now()


def set_promo_active(promo: Any, *, active: bool) -> None:
    promo.is_active = active
