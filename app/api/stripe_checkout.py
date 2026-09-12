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
    email: Optional[str],
    package: Optional[Dict[str, Any]],
    package_name: str,
    amount_cents: int,
    currency: str,
    force_custom_price: bool = False,
    is_gift: bool = False,
) -> stripe.checkout.Session:
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    success_url = (
        f"{settings.stripe_success_url.rstrip('/')}"
        "?session_id={CHECKOUT_SESSION_ID}"
    )
    normalized_email = (email or "").strip().lower()
    if normalized_email:
        success_url += f"&email={quote(normalized_email, safe='')}"
    if is_gift:
        success_url += "&gift=1"

    display_name = f"Gift · {package_name}" if is_gift else package_name

    # Do NOT set payment_method_types — that locks Checkout to an explicit list
    # and turns off Dashboard dynamic methods (Apple Pay / Google Pay / Link).
    create_kwargs: Dict[str, Any] = {
        "mode": "payment",
        "line_items": _line_items(
            package=package,
            package_name=display_name,
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
    # Prefill when we have it; otherwise Stripe Checkout asks for email.
    if normalized_email:
        create_kwargs["customer_email"] = normalized_email

    pmc = (settings.stripe_payment_method_configuration or "").strip()
    if pmc:
        create_kwargs["payment_method_configuration"] = pmc

    try:
        return stripe.checkout.Session.create(**create_kwargs)
    except stripe.StripeError as exc:
        logger.exception("Stripe checkout session failed for %s", order_number)
        raise StripeCheckoutError(str(exc)) from exc


def create_topup_checkout_session(
    *,
    parent_order_number: str,
    parent_order_id: str,
    email: str,
    iccid: str,
    fund_usd: Optional[float] = None,
    retail_cents: Optional[int] = None,
    display_name: Optional[str] = None,
    topup_provider: str = "citrus",
    offer_id: Optional[str] = None,
    package_slug: Optional[str] = None,
    package_code: Optional[str] = None,
    period_num: Optional[int] = None,
    wholesale_usd: Optional[float] = None,
) -> stripe.checkout.Session:
    """Stripe Checkout for topping up an existing eSIM (Citrus wallet or Access pack)."""
    from app.services.esim_topup import topup_retail_cents

    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    if retail_cents is not None:
        amount_cents = int(retail_cents)
    elif fund_usd is not None:
        amount_cents = topup_retail_cents(fund_usd)
    else:
        raise StripeCheckoutError("Top-up checkout requires fund_usd or retail_cents.")

    if not display_name:
        if topup_provider == "esimaccess":
            label = package_slug or offer_id or "package"
            display_name = f"eSIM top-up · {parent_order_number} · {label}"
        else:
            display_name = f"Data top-up · {parent_order_number} · ${float(fund_usd or 0):.0f} data"

    success_url = (
        f"{settings.app_url.rstrip('/')}/dashboard"
        f"?orderId={quote(parent_order_number, safe='')}"
        f"&email={quote(email.strip().lower(), safe='')}"
        "&topup=1"
    )

    metadata: Dict[str, str] = {
        "checkout_type": "topup",
        "order_number": parent_order_number,
        "order_id": parent_order_id,
        "iccid": iccid,
        "topup_provider": topup_provider,
        "retail_cents": str(amount_cents),
    }
    if fund_usd is not None:
        metadata["fund_usd"] = str(fund_usd)
    if wholesale_usd is not None:
        metadata["wholesale_usd"] = str(wholesale_usd)
    if offer_id:
        metadata["offer_id"] = offer_id
    if package_slug:
        metadata["package_slug"] = package_slug
    if package_code:
        metadata["package_code"] = package_code
    if period_num is not None:
        metadata["period_num"] = str(period_num)

    create_kwargs: Dict[str, Any] = {
        "mode": "payment",
        "customer_email": email.strip().lower(),
        "line_items": [
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_cents,
                    "product_data": {"name": display_name},
                },
                "quantity": 1,
            }
        ],
        "success_url": success_url,
        "cancel_url": f"{settings.app_url.rstrip('/')}/dashboard",
        "metadata": metadata,
    }

    pmc = (settings.stripe_payment_method_configuration or "").strip()
    if pmc:
        create_kwargs["payment_method_configuration"] = pmc

    try:
        return stripe.checkout.Session.create(**create_kwargs)
    except stripe.StripeError as exc:
        logger.exception("Stripe top-up checkout failed for %s", parent_order_number)
        raise StripeCheckoutError(str(exc)) from exc


def create_stripe_payment_intent(
    *,
    order_number: str,
    order_id: str,
    email: Optional[str],
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
        "description": package_name,
        "automatic_payment_methods": {"enabled": True},
        "metadata": {
            "order_number": order_number,
            "order_id": order_id,
        },
    }
    normalized_email = (email or "").strip().lower()
    if normalized_email:
        create_kwargs["receipt_email"] = normalized_email
    pmc = (settings.stripe_payment_method_configuration or "").strip()
    if pmc:
        create_kwargs["payment_method_configuration"] = pmc

    try:
        return stripe.PaymentIntent.create(**create_kwargs)
    except stripe.StripeError as exc:
        logger.exception("Stripe PaymentIntent failed for %s", order_number)
        raise StripeCheckoutError(str(exc)) from exc


def create_topup_payment_intent(
    *,
    parent_order_number: str,
    parent_order_id: str,
    email: str,
    iccid: str,
    amount_cents: int,
    display_name: str,
    topup_provider: str = "citrus",
    fund_usd: Optional[float] = None,
    wholesale_usd: Optional[float] = None,
    offer_id: Optional[str] = None,
    package_slug: Optional[str] = None,
    package_code: Optional[str] = None,
    period_num: Optional[int] = None,
) -> stripe.PaymentIntent:
    """PaymentIntent for My eSIMs express wallets (Apple Pay / Google Pay / Link)."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    metadata: Dict[str, str] = {
        "checkout_type": "topup",
        "order_number": parent_order_number,
        "order_id": parent_order_id,
        "iccid": iccid,
        "topup_provider": topup_provider,
        "retail_cents": str(int(amount_cents)),
    }
    if fund_usd is not None:
        metadata["fund_usd"] = str(fund_usd)
    if wholesale_usd is not None:
        metadata["wholesale_usd"] = str(wholesale_usd)
    if offer_id:
        metadata["offer_id"] = offer_id
    if package_slug:
        metadata["package_slug"] = package_slug
    if package_code:
        metadata["package_code"] = package_code
    if period_num is not None:
        metadata["period_num"] = str(period_num)

    create_kwargs: Dict[str, Any] = {
        "amount": int(amount_cents),
        "currency": "usd",
        "description": display_name,
        "automatic_payment_methods": {"enabled": True},
        "metadata": metadata,
        "receipt_email": email.strip().lower(),
    }
    pmc = (settings.stripe_payment_method_configuration or "").strip()
    if pmc:
        create_kwargs["payment_method_configuration"] = pmc

    try:
        return stripe.PaymentIntent.create(**create_kwargs)
    except stripe.StripeError as exc:
        logger.exception("Stripe top-up PaymentIntent failed for %s", parent_order_number)
        raise StripeCheckoutError(str(exc)) from exc
