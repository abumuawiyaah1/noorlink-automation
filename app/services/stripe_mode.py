"""Detect Stripe live vs test mode for admin finance warnings."""

from __future__ import annotations

from typing import Any, Dict

from app.core.config import get_settings


def stripe_mode_info() -> Dict[str, Any]:
    key = (get_settings().stripe_secret_key or "").strip()
    if key.startswith("sk_live_"):
        return {
            "mode": "live",
            "label": "Live",
            "badge_class": "success",
            "warning": None,
        }
    if key.startswith("sk_test_"):
        return {
            "mode": "test",
            "label": "Test",
            "badge_class": "warning",
            "warning": "Stripe is in test mode — real charges and refunds will not hit live accounts.",
        }
    return {
        "mode": "unknown",
        "label": "Not configured",
        "badge_class": "danger",
        "warning": "STRIPE_SECRET_KEY is missing or unrecognized — check Railway env vars.",
    }
