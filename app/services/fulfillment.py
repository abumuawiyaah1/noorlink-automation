"""
Post-payment fulfillment orchestration.

Runs after Stripe marks an order paid: eSIM credentials, travel assistant, delivered status, email.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.email_service import (
    EmailDeliveryError,
    build_fulfillment_email_html,
    send_fulfillment_email,
)
from app.services.esim_provision import provision_esim
from app.services.travel_assistant_service import enrich_order_with_travel_assistant

logger = logging.getLogger(__name__)


class FulfillmentError(Exception):
    """Fulfillment pipeline failed."""


def fulfill_paid_order(order_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full post-paid loop for a single order row (status should be paid or pending).
    """
    order_number = order_row["order_number"]
    if order_row.get("status") == "delivered":
        logger.info("Order %s already delivered; skipping fulfillment", order_number)
        return order_row

    esim = provision_esim(order_row)
    travel_guide = enrich_order_with_travel_assistant(order_row)

    metadata_patch = {
        "fulfillment": {
            "provider": esim.get("provider"),
            "lpa_string": esim.get("lpa_string"),
            "travel_assistant_included": True,
        },
        "travel_assistant": travel_guide,
    }

    delivered_row = db.mark_order_delivered(
        order_number,
        qr_code_url=esim["qr_code_url"],
        activation_code=esim["activation_code"],
        metadata_patch=metadata_patch,
    )

    settings = get_settings()
    flag = delivered_row.get("flag_emoji")
    country = delivered_row.get("country") or "your destination"
    subject = f"{country} eSIM delivered — {order_number}"

    html_body = build_fulfillment_email_html(
        order_number=order_number,
        country=country,
        package_name=delivered_row.get("package_name") or "Travel eSIM",
        flag_emoji=flag,
        qr_code_url=esim["qr_code_url"],
        activation_code=esim["activation_code"],
        travel_guide=travel_guide,
        app_url=settings.app_url,
    )

    try:
        send_fulfillment_email(
            to_email=str(delivered_row["email"]),
            subject=subject,
            html_body=html_body,
        )
    except EmailDeliveryError as exc:
        logger.error(
            "Order %s delivered in DB but email failed: %s",
            order_number,
            exc,
        )
        db.merge_order_metadata(
            order_number,
            {"fulfillment": {**metadata_patch.get("fulfillment", {}), "email_error": str(exc)}},
        )
        raise FulfillmentError(f"Email failed for {order_number}") from exc

    db.merge_order_metadata(
        order_number,
        {"fulfillment": {**metadata_patch.get("fulfillment", {}), "email_sent": True}},
    )

    logger.info("Fulfillment complete for order %s", order_number)
    return delivered_row


def process_paid_order(
    *,
    order_number: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
    stripe_payment_intent_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Mark paid (from webhook) then run fulfillment. Returns final order row.
    """
    paid_row = db.mark_order_paid(
        order_number=order_number,
        stripe_checkout_session_id=stripe_checkout_session_id,
        stripe_payment_intent_id=stripe_payment_intent_id,
    )
    if not paid_row:
        logger.warning(
            "No order found for payment (order_number=%s, session=%s)",
            order_number,
            stripe_checkout_session_id,
        )
        return None

    try:
        return fulfill_paid_order(paid_row)
    except FulfillmentError:
        raise
    except db.SupabaseRepositoryError as exc:
        raise FulfillmentError(str(exc)) from exc
