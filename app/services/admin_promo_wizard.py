"""Create promo codes from the staff wizard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import PromoCode
from app.services.admin_promo_codes import (
    AdminPromoError,
    apply_promo_approval_rules,
    validate_promo_payload,
)
from app.services.promo_codes import normalize_code


def _parse_datetime(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        raise AdminPromoError("Start and end dates are required.")
    if len(text) == 10:
        text = f"{text}T00:00:00+00:00"
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_promo_wizard_form(form: Dict[str, Any]) -> Dict[str, Any]:
    discount_type = str(form.get("discount_type") or "percent").strip().lower()
    percent_off = None
    amount_off_cents = None

    if discount_type == "amount":
        amount_off_cents = int(str(form.get("amount_off_cents") or "0"))
    else:
        percent_off = int(str(form.get("percent_off") or "0"))

    return {
        "code": normalize_code(str(form.get("code") or "")),
        "label": str(form.get("label") or "").strip(),
        "percent_off": percent_off,
        "amount_off_cents": amount_off_cents,
        "starts_at": _parse_datetime(str(form.get("starts_at") or "")),
        "ends_at": _parse_datetime(str(form.get("ends_at") or "")),
        "max_redemptions": str(form.get("max_redemptions") or "").strip() or None,
        "min_order_cents": int(str(form.get("min_order_cents") or "0")),
        "is_active": str(form.get("is_active") or "1").lower() in {"1", "true", "on", "yes"},
    }


def create_promo_from_wizard(
    *,
    form: Dict[str, Any],
    editor_is_admin: bool,
    editor_username: str,
) -> Dict[str, Any]:
    parsed = parse_promo_wizard_form(form)
    payload = validate_promo_payload(
        {
            **parsed,
            "max_redemptions": parsed["max_redemptions"],
        },
        is_create=True,
    )
    apply_promo_approval_rules(
        payload,
        is_create=True,
        editor_is_admin=editor_is_admin,
        editor_username=editor_username,
    )

    factory = get_session_factory()
    if factory is None:
        raise AdminPromoError("DATABASE_URL is required.")

    with factory() as session:
        existing = session.execute(
            select(PromoCode.id).where(PromoCode.code == payload["code"])
        ).scalar_one_or_none()
        if existing is not None:
            raise AdminPromoError(f"Promo code already exists: {payload['code']}")

        promo = PromoCode(
            id=uuid4(),
            code=payload["code"],
            label=payload.get("label"),
            percent_off=payload.get("percent_off"),
            amount_off_cents=payload.get("amount_off_cents"),
            starts_at=payload["starts_at"],
            ends_at=payload["ends_at"],
            is_active=bool(payload.get("is_active", True)),
            max_redemptions=payload.get("max_redemptions"),
            redemption_count=0,
            min_order_cents=payload.get("min_order_cents", 0),
            admin_approved=bool(payload.get("admin_approved")),
            admin_approved_by=payload.get("admin_approved_by"),
            admin_approved_at=payload.get("admin_approved_at"),
        )
        session.add(promo)
        session.commit()

    return {
        "code": payload["code"],
        "admin_approved": bool(payload.get("admin_approved")),
        "percent_off": payload.get("percent_off"),
        "amount_off_cents": payload.get("amount_off_cents"),
    }
