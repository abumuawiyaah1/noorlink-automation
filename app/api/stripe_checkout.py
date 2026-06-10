"""Stripe Hosted Checkout session creation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import stripe

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StripeCheckoutError(Exception):
    """Raised when Stripe Checkout Session creation fails."""


def _line_items(
    *,
    package: Optional[Dict[str, Any]],
    package_name: str,
    amount_cents: int,
    currency: str,
) -> List[Dict[str, Any]]:
    stripe_price_id = (package or {}).get("stripe_price_id")
    if stripe_price_id:
        return [{"price": stripe_price_id, "quantity": 1}]

    return [
        {
            "price_data": {
                "currency": (currency or "USD").lower(),
                "unit_amount": amount_cents,
                "product_data": {"name": package_name},
            },
            "quantity": 1,
        }
    ]


def create_stripe_checkout_session(
    *,
    order_number: str,
    order_id: str,
    email: str,
    package: Optional[Dict[str, Any]],
    package_name: str,
    amount_cents: int,
    currency: str,
) -> stripe.checkout.Session:
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    success_url = (
        f"{settings.stripe_success_url.rstrip('/')}"
        "?session_id={CHECKOUT_SESSION_ID}"
    )

    try:
        return stripe.checkout.Session.create(
            mode="payment",
            customer_email=email.strip().lower(),
            line_items=_line_items(
                package=package,
                package_name=package_name,
                amount_cents=amount_cents,
                currency=currency,
            ),
            success_url=success_url,
            cancel_url=settings.stripe_cancel_url,
            metadata={
                "order_number": order_number,
                "order_id": order_id,
            },
        )
    except stripe.StripeError as exc:
        logger.exception("Stripe checkout session failed for %s", order_number)
        raise StripeCheckoutError(str(exc)) from exc
