"""Stripe Hosted Checkout session creation.

Wallets (Apple Pay, Google Pay) and Link appear on Checkout when:
  1. This session omits `payment_method_types` (dynamic payment methods), and
  2. Those methods are enabled in Stripe Dashboard → Settings → Payment methods.

Hosted Checkout runs on checkout.stripe.com, so Apple Pay works without
registering noorlink.co as a domain (domain verify is only needed for
on-site Payment Element / Express Checkout Element later).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

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
    force_custom_price: bool = False,
) -> List[Dict[str, Any]]:
    stripe_price_id = (package or {}).get("stripe_price_id")
    if stripe_price_id and not force_custom_price:
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
    force_custom_price: bool = False,
) -> stripe.checkout.Session:
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    success_url = (
        f"{settings.stripe_success_url.rstrip('/')}"
        "?session_id={CHECKOUT_SESSION_ID}"
        f"&email={quote(email.strip().lower(), safe='')}"
    )

    # Do NOT set payment_method_types — that locks Checkout to an explicit list
    # and turns off Dashboard dynamic methods (Apple Pay / Google Pay / Link).
    create_kwargs: Dict[str, Any] = {
        "mode": "payment",
        "customer_email": email.strip().lower(),
        "line_items": _line_items(
            package=package,
            package_name=package_name,
            amount_cents=amount_cents,
            currency=currency,
            force_custom_price=force_custom_price,
        ),
        "success_url": success_url,
        "cancel_url": settings.stripe_cancel_url,
        "billing_address_collection": "auto",
        "wallet_options": {
            # Show Link when available (one-tap / autofill on mobile).
            "link": {"display": "auto"},
        },
        "metadata": {
            "order_number": order_number,
            "order_id": order_id,
        },
    }

    pmc = (settings.stripe_payment_method_configuration or "").strip()
    if pmc:
        create_kwargs["payment_method_configuration"] = pmc

    try:
        return stripe.checkout.Session.create(**create_kwargs)
    except stripe.StripeError as exc:
        logger.exception("Stripe checkout session failed for %s", order_number)
        raise StripeCheckoutError(str(exc)) from exc


def create_stripe_payment_intent(
    *,
    order_number: str,
    order_id: str,
    email: str,
    amount_cents: int,
    currency: str,
    package_name: str,
) -> stripe.PaymentIntent:
    """PaymentIntent for on-page Express Checkout (Apple Pay / Google Pay / Link)."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    create_kwargs: Dict[str, Any] = {
        "amount": amount_cents,
        "currency": (currency or "USD").lower(),
        "receipt_email": email.strip().lower(),
        "description": package_name,
        "automatic_payment_methods": {"enabled": True},
        "metadata": {
            "order_number": order_number,
            "order_id": order_id,
        },
    }
    pmc = (settings.stripe_payment_method_configuration or "").strip()
    if pmc:
        create_kwargs["payment_method_configuration"] = pmc

    try:
        return stripe.PaymentIntent.create(**create_kwargs)
    except stripe.StripeError as exc:
        logger.exception("Stripe PaymentIntent failed for %s", order_number)
        raise StripeCheckoutError(str(exc)) from exc
