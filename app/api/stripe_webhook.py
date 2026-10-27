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


def _as_dict(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            converted = value.to_dict()
            return converted if isinstance(converted, dict) else None
        except Exception:
            return None
    return None


def extract_checkout_presentment(session: Any) -> Dict[str, Any]:
    """Capture what the customer was shown/charged (Adaptive Pricing aware)."""
    session_currency = (getattr(session, "currency", None) or "usd").lower()
    amount_total = getattr(session, "amount_total", None)
    payment_status = getattr(session, "payment_status", None)

    presentment = _as_dict(getattr(session, "presentment_details", None)) or {}
    conversion = _as_dict(getattr(session, "currency_conversion", None))

    presentment_currency = (
        presentment.get("presentment_currency")
        or presentment.get("currency")
        or session_currency
    )
    presentment_amount = presentment.get("presentment_amount") or presentment.get(
        "amount"
    )
    if presentment_amount is None and amount_total is not None:
        presentment_amount = amount_total

    metadata = getattr(session, "metadata", None) or {}
    if hasattr(metadata, "to_dict"):
        metadata = metadata.to_dict()
    settlement_currency = None
    settlement_amount_cents = None
    if isinstance(metadata, dict):
        settlement_currency = metadata.get("settlement_currency")
        raw_settle = metadata.get("settlement_amount_cents")
        if raw_settle not in (None, ""):
            try:
                settlement_amount_cents = int(raw_settle)
            except (TypeError, ValueError):
                settlement_amount_cents = None

    return {
        "stripe_session_id": getattr(session, "id", None),
        "payment_status": payment_status,
        "session_currency": (session_currency or "usd").upper(),
        "session_amount_total_cents": int(amount_total)
        if amount_total is not None
        else None,
        "presentment_currency": str(presentment_currency or session_currency or "usd").upper(),
        "presentment_amount_cents": int(presentment_amount)
        if presentment_amount is not None
        else None,
        "settlement_currency": (
            str(settlement_currency).upper()
            if settlement_currency
            else None
        ),
        "settlement_amount_cents": settlement_amount_cents,
        "currency_conversion": conversion,
        "presentment_details": presentment or None,
    }


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
    topup_provider = metadata.get("topup_provider") if isinstance(metadata, dict) else None
    offer_id = metadata.get("offer_id") if isinstance(metadata, dict) else None
    package_slug = metadata.get("package_slug") if isinstance(metadata, dict) else None
    package_code = metadata.get("package_code") if isinstance(metadata, dict) else None
    period_num = metadata.get("period_num") if isinstance(metadata, dict) else None
    retail_cents = metadata.get("retail_cents") if isinstance(metadata, dict) else None
    wholesale_usd = metadata.get("wholesale_usd") if isinstance(metadata, dict) else None

    payment_intent = getattr(session, "payment_intent", None)
    if isinstance(payment_intent, dict):
        payment_intent_id = payment_intent.get("id")
    else:
        payment_intent_id = payment_intent

    customer_email = getattr(session, "customer_email", None)
    if not customer_email:
        details = getattr(session, "customer_details", None)
        if details is not None:
            if hasattr(details, "to_dict"):
                details = details.to_dict()
            if isinstance(details, dict):
                customer_email = details.get("email")
            else:
                customer_email = getattr(details, "email", None)

    presentment = extract_checkout_presentment(session)

    return {
        "session_id": getattr(session, "id", None),
        "order_number": order_number,
        "order_id": order_id,
        "checkout_type": checkout_type,
        "fund_usd": fund_usd,
        "topup_provider": topup_provider,
        "offer_id": offer_id,
        "package_slug": package_slug,
        "package_code": package_code,
        "period_num": period_num,
        "retail_cents": retail_cents,
        "wholesale_usd": wholesale_usd,
        "payment_intent_id": payment_intent_id,
        "customer_email": customer_email,
        "amount_cents": stripe_event_amount_cents(event),
        "customer_patch": _stripe_session_customer_patch(session),
        "stripe_payment": presentment,
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
    amount = int(
        getattr(intent, "amount_received", None) or getattr(intent, "amount", 0) or 0
    ) or None
    currency = (getattr(intent, "currency", None) or "usd").upper()

    return {
        "payment_intent_id": getattr(intent, "id", None),
        "order_number": order_number,
        "order_id": order_id,
        "customer_email": getattr(intent, "receipt_email", None),
        "amount_cents": amount,
        "checkout_type": metadata.get("checkout_type") if isinstance(metadata, dict) else None,
        "fund_usd": metadata.get("fund_usd") if isinstance(metadata, dict) else None,
        "topup_provider": metadata.get("topup_provider") if isinstance(metadata, dict) else None,
        "offer_id": metadata.get("offer_id") if isinstance(metadata, dict) else None,
        "package_slug": metadata.get("package_slug") if isinstance(metadata, dict) else None,
        "package_code": metadata.get("package_code") if isinstance(metadata, dict) else None,
        "period_num": metadata.get("period_num") if isinstance(metadata, dict) else None,
        "retail_cents": metadata.get("retail_cents") if isinstance(metadata, dict) else None,
        "wholesale_usd": metadata.get("wholesale_usd") if isinstance(metadata, dict) else None,
        "stripe_payment": {
            "payment_intent_id": getattr(intent, "id", None),
            "payment_status": "paid",
            "session_currency": currency,
            "session_amount_total_cents": amount,
            "presentment_currency": currency,
            "presentment_amount_cents": amount,
            "settlement_currency": currency,
            "settlement_amount_cents": amount,
        },
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


def verify_stripe_paid_amount_for_order(order_row: dict, event: stripe.Event) -> bool:
    """
    Confirm money was collected before eSIM fulfillment.

    With Adaptive Pricing, Checkout Session amount_total/currency may be the
    customer's presentment currency, while the order row stays in USD.
    """
    expected = int(order_row.get("amount_cents") or 0)
    if not expected:
        return True

    order_currency = (order_row.get("currency") or "USD").lower()

    if event.type == "payment_intent.succeeded":
        received = stripe_event_amount_cents(event)
        if not received:
            return True
        intent = event.data.object
        pi_currency = (getattr(intent, "currency", None) or order_currency).lower()
        if pi_currency != order_currency:
            logger.error(
                "PaymentIntent currency mismatch for %s: expected %s got %s",
                order_row.get("order_number"),
                order_currency,
                pi_currency,
            )
            return False
        if expected != received:
            logger.error(
                "Stripe amount mismatch for order %s: expected %s got %s",
                order_row.get("order_number"),
                expected,
                received,
            )
            return False
        return True

    if event.type != "checkout.session.completed":
        return True

    session = event.data.object
    payment_status = str(getattr(session, "payment_status", None) or "").lower()
    if payment_status and payment_status != "paid":
        logger.error(
            "Stripe session not paid for %s: status=%s",
            order_row.get("order_number"),
            payment_status,
        )
        return False

    session_currency = (getattr(session, "currency", None) or "usd").lower()
    amount_total = getattr(session, "amount_total", None)

    if session_currency == order_currency:
        if amount_total is None:
            return True
        if int(amount_total) != expected:
            logger.error(
                "Stripe amount mismatch for order %s: expected %s %s got %s %s",
                order_row.get("order_number"),
                expected,
                order_currency,
                amount_total,
                session_currency,
            )
            return False
        return True

    # Adaptive Pricing path: presentment currency differs from order settlement.
    pi_ref = getattr(session, "payment_intent", None)
    pi_id = pi_ref.get("id") if isinstance(pi_ref, dict) else pi_ref
    if pi_id:
        try:
            settings = get_settings()
            stripe.api_key = settings.stripe_secret_key
            intent = stripe.PaymentIntent.retrieve(str(pi_id))
            pi_currency = (getattr(intent, "currency", None) or "").lower()
            pi_amount = int(
                getattr(intent, "amount_received", None)
                or getattr(intent, "amount", 0)
                or 0
            )
            if pi_currency == order_currency and pi_amount:
                if pi_amount != expected:
                    logger.error(
                        "Stripe PI settlement mismatch for %s: expected %s got %s",
                        order_row.get("order_number"),
                        expected,
                        pi_amount,
                    )
                    return False
                return True
            if pi_amount > 0 and payment_status == "paid":
                logger.info(
                    "Adaptive Pricing paid for %s: presentment %s %s; order %s %s — fulfilling",
                    order_row.get("order_number"),
                    amount_total,
                    session_currency,
                    expected,
                    order_currency,
                )
                return True
        except Exception as exc:
            logger.warning(
                "Could not retrieve PaymentIntent %s for amount verify: %s",
                pi_id,
                exc,
            )

    if payment_status == "paid" and amount_total and int(amount_total) > 0:
        logger.info(
            "Adaptive Pricing session paid for %s without USD cent match "
            "(presentment %s %s vs order %s %s) — fulfilling",
            order_row.get("order_number"),
            amount_total,
            session_currency,
            expected,
            order_currency,
        )
        return True

    logger.error(
        "Could not verify paid amount for Adaptive Pricing order %s",
        order_row.get("order_number"),
    )
    return False
