"""Stripe webhook signature verification and event parsing."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import stripe

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StripeWebhookError(Exception):
    """Invalid or unprocessable Stripe webhook payload."""


def construct_stripe_event(
    payload: bytes,
    signature_header: Optional[str],
) -> stripe.Event:
    if not signature_header:
        raise StripeWebhookError("Missing Stripe-Signature header")

    settings = get_settings()
    try:
        return stripe.Webhook.construct_event(
            payload,
            signature_header,
            settings.stripe_webhook_secret,
        )
    except ValueError as exc:
        raise StripeWebhookError("Invalid webhook payload") from exc
    except stripe.SignatureVerificationError as exc:
        raise StripeWebhookError("Invalid webhook signature") from exc


def extract_checkout_session_completed(
    event: stripe.Event,
) -> Optional[Dict[str, Any]]:
    if event.type != "checkout.session.completed":
        return None

    session = event.data.object
    metadata = getattr(session, "metadata", None) or {}
    if hasattr(metadata, "to_dict"):
        metadata = metadata.to_dict()

    order_number = metadata.get("order_number") if isinstance(metadata, dict) else None
    order_id = metadata.get("order_id") if isinstance(metadata, dict) else None
    checkout_type = metadata.get("checkout_type") if isinstance(metadata, dict) else None
    fund_usd = metadata.get("fund_usd") if isinstance(metadata, dict) else None

    payment_intent = getattr(session, "payment_intent", None)
    if isinstance(payment_intent, dict):
        payment_intent_id = payment_intent.get("id")
    else:
        payment_intent_id = payment_intent

    return {
        "session_id": getattr(session, "id", None),
        "order_number": order_number,
        "order_id": order_id,
        "checkout_type": checkout_type,
        "fund_usd": fund_usd,
        "payment_intent_id": payment_intent_id,
        "customer_email": getattr(session, "customer_email", None),
        "amount_cents": stripe_event_amount_cents(event),
        "customer_patch": _stripe_session_customer_patch(session),
    }


def _stripe_session_customer_patch(session: Any) -> Dict[str, Any]:
    from app.services.order_attribution import stripe_checkout_customer_patch

    return stripe_checkout_customer_patch(session)


def extract_payment_intent_succeeded(
    event: stripe.Event,
) -> Optional[Dict[str, Any]]:
    if event.type != "payment_intent.succeeded":
        return None

    intent = event.data.object
    metadata = getattr(intent, "metadata", None) or {}
    if hasattr(metadata, "to_dict"):
        metadata = metadata.to_dict()

    order_number = metadata.get("order_number") if isinstance(metadata, dict) else None
    order_id = metadata.get("order_id") if isinstance(metadata, dict) else None

    return {
        "payment_intent_id": getattr(intent, "id", None),
        "order_number": order_number,
        "order_id": order_id,
        "customer_email": getattr(intent, "receipt_email", None),
        "amount_cents": int(getattr(intent, "amount_received", None) or getattr(intent, "amount", 0) or 0) or None,
    }


def stripe_event_amount_cents(event: stripe.Event) -> Optional[int]:
    if event.type == "payment_intent.succeeded":
        intent = event.data.object
        raw = getattr(intent, "amount_received", None) or getattr(intent, "amount", None)
        return int(raw) if raw is not None else None
    if event.type == "checkout.session.completed":
        session = event.data.object
        raw = getattr(session, "amount_total", None)
        return int(raw) if raw is not None else None
    return None
