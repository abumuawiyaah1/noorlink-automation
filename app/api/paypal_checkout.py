"""Standalone PayPal Business checkout (US Stripe cannot enable PayPal).

Flow: create NoorLink pending order → create PayPal order → capture on approve →
process_paid_order (same eSIM fulfillment path as Stripe).

Charge currency: USD settlement catalog; when shopper picks CAD/EUR/GBP/MXN
(enabled on the PayPal account), create the PayPal order in that currency.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.services.fx_rates import (
    convert_usd_to,
    format_paypal_amount,
    normalize_currency,
    resolve_paypal_charge_currency,
)

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


def build_paypal_charge(
    *,
    amount_usd: float,
    preferred_currency: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve PayPal presentment amount/currency from a USD catalog price."""
    charge_currency = resolve_paypal_charge_currency(preferred_currency)
    charge_amount = convert_usd_to(float(amount_usd), charge_currency)
    return {
        "settlement_currency": "USD",
        "settlement_amount": round(float(amount_usd), 2),
        "settlement_amount_cents": int(round(float(amount_usd) * 100)),
        "presentment_currency": charge_currency,
        "presentment_amount": charge_amount,
        "presentment_amount_cents": int(round(charge_amount * 100)),
        "preferred_currency": normalize_currency(preferred_currency),
    }


def create_paypal_order(
    *,
    order_number: str,
    amount_usd: float,
    description: str,
    return_url: str,
    cancel_url: str,
    currency: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Create a PayPal order; returns (paypal_order_id, charge_meta)."""
    token = _access_token()
    charge = build_paypal_charge(
        amount_usd=amount_usd,
        preferred_currency=currency,
    )
    amount_value = format_paypal_amount(
        charge["presentment_amount"],
        charge["presentment_currency"],
    )
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": order_number,
                "custom_id": order_number,
                "description": (description or "NoorLink eSIM")[:127],
                "amount": {
                    "currency_code": charge["presentment_currency"],
                    "value": amount_value,
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
    return str(paypal_order_id), charge


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
    amount_currency: Optional[str] = None
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
            if isinstance(amount, dict):
                if amount.get("value"):
                    amount_value = str(amount.get("value"))
                if amount.get("currency_code"):
                    amount_currency = str(amount.get("currency_code")).upper()

    payer = data.get("payer") if isinstance(data.get("payer"), dict) else {}
    payer_email = None
    if isinstance(payer, dict):
        payer_email = payer.get("email_address")

    data["_noorlink"] = {
        "order_number": order_number,
        "capture_id": capture_id,
        "amount_value": amount_value,
        "amount_currency": amount_currency,
        "payer_email": payer_email,
    }
    return data, order_number, str(payer_email).strip().lower() if payer_email else None


def verify_paypal_capture_amount(
    *,
    expected_presentment_amount: Optional[float],
    expected_presentment_currency: Optional[str],
    received_value: Optional[str],
    received_currency: Optional[str],
    settlement_amount_usd: Optional[float] = None,
) -> bool:
    """
    Confirm captured PayPal amount matches what we created.
    Prefer presentment currency match; fall back to USD settlement cents.
    """
    if not received_value:
        return True
    try:
        received_cents = int(round(float(received_value) * 100))
    except (TypeError, ValueError):
        return False
    if not received_cents:
        return False

    recv_cur = normalize_currency(received_currency)
    exp_cur = normalize_currency(expected_presentment_currency)

    if expected_presentment_amount is not None and recv_cur == exp_cur:
        expected_cents = int(round(float(expected_presentment_amount) * 100))
        if expected_cents and expected_cents != received_cents:
            logger.error(
                "PayPal presentment mismatch: expected %s %s got %s %s",
                expected_cents,
                exp_cur,
                received_cents,
                recv_cur,
            )
            return False
        return True

    # Legacy / USD-only path
    if recv_cur == "USD" and settlement_amount_usd is not None:
        expected_cents = int(round(float(settlement_amount_usd) * 100))
        if expected_cents and expected_cents != received_cents:
            logger.error(
                "PayPal USD mismatch: expected %s got %s",
                expected_cents,
                received_cents,
            )
            return False
        return True

    # Paid in a different currency than stored — still allow if amount > 0 and
    # we at least recorded a presentment expectation that we cannot re-check.
    if expected_presentment_amount is None and settlement_amount_usd is not None:
        expected_cents = int(round(float(settlement_amount_usd) * 100))
        if recv_cur == "USD" and expected_cents and expected_cents != received_cents:
            return False
        return True

    logger.error(
        "PayPal currency mismatch on capture: expected %s got %s %s",
        exp_cur,
        received_cents,
        recv_cur,
    )
    return False
