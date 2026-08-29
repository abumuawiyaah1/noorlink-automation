"""Customer self-service: resend QR email."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.api import supabase_repository as db
from app.services.admin_orders import AdminOrderError, resend_order_esim_email

RESEND_COOLDOWN_MINUTES = 15


class CustomerSelfServiceError(Exception):
    """Customer self-service action failed."""


def customer_resend_esim_email(*, order_number: str, email: str) -> Dict[str, Any]:
    looked_up = db.lookup_order(order_number, email.strip().lower())
    if not looked_up:
        raise CustomerSelfServiceError("Order not found for that email.")

    row = db.get_order_row_by_order_number(looked_up.order_number)
    if not row:
        raise CustomerSelfServiceError("Order not found.")

    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    last_resend = metadata.get("customer_resend_at")
    if last_resend:
        try:
            parsed = datetime.fromisoformat(str(last_resend).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - parsed < timedelta(minutes=RESEND_COOLDOWN_MINUTES):
                raise CustomerSelfServiceError(
                    f"Please wait {RESEND_COOLDOWN_MINUTES} minutes between resend requests."
                )
        except CustomerSelfServiceError:
            raise
        except Exception:
            pass

    try:
        message_id = resend_order_esim_email(row)
    except AdminOrderError as exc:
        raise CustomerSelfServiceError(str(exc)) from exc

    db.merge_order_metadata(
        looked_up.order_number,
        {"customer_resend_at": datetime.now(timezone.utc).isoformat()},
    )

    from app.services.ops_event_log import log_email_delivery, log_ops_event

    gift = metadata.get("gift") if isinstance(metadata.get("gift"), dict) else {}
    recipient = (
        str(gift.get("recipient_email") or "").strip().lower()
        if gift.get("is_gift")
        else str(row.get("email") or "").strip().lower()
    )
    log_email_delivery(
        event_type="sent",
        recipient=recipient,
        email_type="fulfillment_resend",
        subject=f"Customer resend {looked_up.order_number}",
        message_id=message_id,
    )
    log_ops_event(
        event_type="customer_resend_esim",
        source="customer",
        message=f"Customer requested QR resend for {looked_up.order_number}",
        order_number=looked_up.order_number,
    )

    return {"success": True, "message_id": message_id, "order_number": looked_up.order_number}
