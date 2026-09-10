"""Standalone PayPal Business checkout (US Stripe cannot enable PayPal).

Flow: create NoorLink pending order → create PayPal order → capture on approve →
process_paid_order (same eSIM fulfillment path as Stripe).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class PayPalCheckoutError(Exception):
    """Raised when PayPal Orders API calls fail."""


def paypal_enabled() -> bool:
    settings = get_settings()
    return bool(
        (settings.paypal_client_id or "").strip()
        and (settings.paypal_client_secret or "").strip()
    )


def _api_base() -> str:
    mode = (get_settings().paypal_mode or "sandbox").strip().lower()
    if mode in {"live", "production", "prod"}:
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def _access_token() -> str:
    settings = get_settings()
    client_id = (settings.paypal_client_id or "").strip()
    secret = (settings.paypal_client_secret or "").strip()
    if not client_id or not secret:
        raise PayPalCheckoutError("PayPal is not configured.")

    url = f"{_api_base()}/v1/oauth2/token"
    try:
        response = httpx.post(
            url,
            data={"grant_type": "client_credentials"},
            auth=(client_id, secret),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.exception("PayPal OAuth failed")
        raise PayPalCheckoutError("Could not authenticate with PayPal.") from exc

    token = data.get("access_token")
    if not token:
        raise PayPalCheckoutError("PayPal OAuth missing access_token.")
    return str(token)


def create_paypal_order(
    *,
    order_number: str,
    amount_usd: float,
    description: str,
    return_url: str,
    cancel_url: str,
) -> str:
    """Create a PayPal order; returns PayPal order id."""
    token = _access_token()
    amount = f"{amount_usd:.2f}"
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": order_number,
                "custom_id": order_number,
                "description": (description or "NoorLink eSIM")[:127],
                "amount": {
                    "currency_code": "USD",
                    "value": amount,
                },
            }
        ],
        "application_context": {
            "brand_name": "NoorLink",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    url = f"{_api_base()}/v2/checkout/orders"
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            logger.error("PayPal create order failed: %s", response.text[:500])
            raise PayPalCheckoutError("PayPal could not start checkout.")
        data = response.json()
    except PayPalCheckoutError:
        raise
    except Exception as exc:
        logger.exception("PayPal create order request failed")
        raise PayPalCheckoutError("PayPal could not start checkout.") from exc

    paypal_order_id = data.get("id")
    if not paypal_order_id:
        raise PayPalCheckoutError("PayPal create order missing id.")
    return str(paypal_order_id)


def capture_paypal_order(paypal_order_id: str) -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
    """
    Capture an approved PayPal order.
    Returns (capture_payload, order_number, payer_email).
    """
    token = _access_token()
    url = f"{_api_base()}/v2/checkout/orders/{paypal_order_id}/capture"
    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            timeout=45.0,
        )
        if response.status_code >= 400:
            logger.error("PayPal capture failed: %s", response.text[:500])
            raise PayPalCheckoutError("PayPal payment could not be completed.")
        data = response.json()
    except PayPalCheckoutError:
        raise
    except Exception as exc:
        logger.exception("PayPal capture request failed")
        raise PayPalCheckoutError("PayPal payment could not be completed.") from exc

    status = str(data.get("status") or "")
    if status != "COMPLETED":
        logger.error("Unexpected PayPal capture status %s for %s", status, paypal_order_id)
        raise PayPalCheckoutError(
            "PayPal payment is not complete yet. Please try again or use another method."
        )

    order_number: Optional[str] = None
    capture_id: Optional[str] = None
    amount_value: Optional[str] = None
    for unit in data.get("purchase_units") or []:
        if not isinstance(unit, dict):
            continue
        if not order_number:
            custom = unit.get("custom_id") or unit.get("reference_id")
            if custom:
                order_number = str(custom)
        payments = unit.get("payments") if isinstance(unit.get("payments"), dict) else {}
        captures = payments.get("captures") if isinstance(payments, dict) else None
        if isinstance(captures, list) and captures:
            first = captures[0] if isinstance(captures[0], dict) else {}
            capture_id = str(first.get("id") or "") or capture_id
            amount = first.get("amount") if isinstance(first.get("amount"), dict) else {}
            if isinstance(amount, dict) and amount.get("value"):
                amount_value = str(amount.get("value"))

    payer = data.get("payer") if isinstance(data.get("payer"), dict) else {}
    payer_email = None
    if isinstance(payer, dict):
        payer_email = payer.get("email_address")

    data["_noorlink"] = {
        "order_number": order_number,
        "capture_id": capture_id,
        "amount_value": amount_value,
        "payer_email": payer_email,
    }
    return data, order_number, str(payer_email).strip().lower() if payer_email else None
