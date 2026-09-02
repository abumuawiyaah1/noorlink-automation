"""Normalize marketing attribution stored on orders."""

from __future__ import annotations

from typing import Any, Dict, Optional


def clean_attribution_payload(raw: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    allowed = (
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "landing_path",
        "referrer",
    )
    cleaned: Dict[str, str] = {}
    for key in allowed:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        cleaned[key] = text[:240]
    return cleaned or None


def stripe_checkout_customer_patch(session: Any) -> Dict[str, Any]:
    """Extract billing country + wallet type from a Stripe Checkout Session."""
    patch: Dict[str, Any] = {}

    customer_details = getattr(session, "customer_details", None) or {}
    if hasattr(customer_details, "to_dict"):
        customer_details = customer_details.to_dict()
    if isinstance(customer_details, dict):
        address = customer_details.get("address")
        if isinstance(address, dict):
            country = str(address.get("country") or "").strip().upper()
            if len(country) == 2:
                patch["customer"] = {"billing_country": country}

    payment_method_types = getattr(session, "payment_method_types", None) or []
    if payment_method_types:
        methods = [str(item) for item in payment_method_types if item]
        if methods:
            customer = patch.setdefault("customer", {})
            customer["payment_method_types"] = methods

    return patch
