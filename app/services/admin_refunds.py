"""Stripe refund wizard for admin."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.ops_event_log import log_ops_event

logger = logging.getLogger(__name__)

REFUND_USAGE_THRESHOLD_PCT = 50


class AdminRefundError(Exception):
    """Refund could not be processed."""


def _usage_percent(row: Dict[str, Any]) -> Optional[float]:
    used = row.get("data_used_gb")
    total = row.get("data_total_gb")
    if used is None or total is None:
        return None
    try:
        total_f = float(total)
        if total_f <= 0:
            return None
        return float(used) / total_f * 100
    except (TypeError, ValueError):
        return None


def validate_refund_eligibility(
    *,
    row: Dict[str, Any],
    admin_override: bool = False,
) -> None:
    status = str(row.get("status") or "").lower()
    if status == "refunded":
        raise AdminRefundError("Order is already refunded.")
    if status in ("pending", "failed"):
        raise AdminRefundError(f"Order status is {status!r} — nothing to refund.")

    amount = int(row.get("amount_cents") or 0)
    if amount <= 0:
        raise AdminRefundError("Complimentary / $0 orders cannot be refunded via Stripe.")

    usage_pct = _usage_percent(row)
    if usage_pct is not None and usage_pct >= REFUND_USAGE_THRESHOLD_PCT and not admin_override:
        raise AdminRefundError(
            f"Customer has used {usage_pct:.0f}% of data. "
            f"Check 'Admin override' to refund anyway (policy: over {REFUND_USAGE_THRESHOLD_PCT}%)."
        )


def process_order_refund(
    *,
    order_number: str,
    reason: str,
    admin_username: str,
    admin_override: bool = False,
    partial_cents: Optional[int] = None,
) -> Dict[str, Any]:
    normalized = order_number.strip().upper()
    row = db.get_order_row_by_order_number(normalized)
    if not row:
        raise AdminRefundError(f"Order not found: {normalized}")

    validate_refund_eligibility(row=row, admin_override=admin_override)

    payment_intent_id = str(row.get("stripe_payment_intent_id") or "").strip()
    if not payment_intent_id:
        raise AdminRefundError("Order has no Stripe payment intent — refund manually in Stripe Dashboard.")

    amount_cents = int(row.get("amount_cents") or 0)
    refund_amount = partial_cents if partial_cents is not None else amount_cents
    if refund_amount <= 0 or refund_amount > amount_cents:
        raise AdminRefundError("Invalid refund amount.")

    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    try:
        refund = stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=refund_amount,
            metadata={
                "order_number": normalized,
                "reason": (reason or "admin")[:200],
                "admin": admin_username,
            },
        )
    except stripe.StripeError as exc:
        logger.error("Stripe refund failed for %s: %s", normalized, exc)
        raise AdminRefundError(str(exc)) from exc

    now = datetime.now(timezone.utc).isoformat()
    client = db.get_supabase_client()
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["refund"] = {
        "reason": reason,
        "admin": admin_username,
        "refund_id": refund.id,
        "amount_cents": refund_amount,
        "at": now,
    }
    try:
        client.table("orders").update(
            {
                "status": "refunded",
                "refunded_at": now,
                "metadata": metadata,
            }
        ).eq("order_number", normalized).execute()
    except Exception as exc:
        raise AdminRefundError(f"Stripe refund succeeded but DB update failed: {exc}") from exc

    log_ops_event(
        event_type="order_refunded",
        source="admin",
        severity="warning",
        order_number=normalized,
        message=f"Refunded ${refund_amount / 100:.2f} — {reason}",
        details={"refund_id": refund.id, "admin": admin_username},
    )

    return {
        "order_number": normalized,
        "refund_id": refund.id,
        "amount_cents": refund_amount,
        "status": "refunded",
    }
