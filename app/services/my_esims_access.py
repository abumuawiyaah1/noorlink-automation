"""Signed My eSIMs access tokens (email magic links)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

from app.core.config import get_settings

TOKEN_TTL_SECONDS = 60 * 60 * 24  # 24 hours
TOKEN_PURPOSE = "my_esims"


class MyEsimsTokenError(Exception):
    """Invalid or expired My eSIMs access token."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _signing_key() -> bytes:
    settings = get_settings()
    secret = (settings.secret_key or "").strip() or "change-this-in-production"
    return secret.encode("utf-8")


def create_my_esims_token(email: str, *, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    """Return a signed, time-limited token that unlocks My eSIMs for this email."""
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise MyEsimsTokenError("A valid email is required.")
    payload = {
        "purpose": TOKEN_PURPOSE,
        "email": normalized,
        "exp": int(time.time()) + int(ttl_seconds),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64url_encode(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_my_esims_token(token: str) -> str:
    """Validate token and return the normalized email."""
    raw = (token or "").strip()
    if not raw or "." not in raw:
        raise MyEsimsTokenError("This link is invalid. Request a new one from My eSIMs.")
    body, _, sig = raw.partition(".")
    expected = _b64url_encode(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise MyEsimsTokenError("This link is invalid. Request a new one from My eSIMs.")
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise MyEsimsTokenError("This link is invalid. Request a new one from My eSIMs.") from exc
    if not isinstance(payload, dict) or payload.get("purpose") != TOKEN_PURPOSE:
        raise MyEsimsTokenError("This link is invalid. Request a new one from My eSIMs.")
    exp = payload.get("exp")
    try:
        exp_i = int(exp)
    except (TypeError, ValueError) as exc:
        raise MyEsimsTokenError("This link is invalid. Request a new one from My eSIMs.") from exc
    if exp_i < int(time.time()):
        raise MyEsimsTokenError("This link has expired. Request a new one from My eSIMs.")
    email = str(payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise MyEsimsTokenError("This link is invalid. Request a new one from My eSIMs.")
    return email


def my_esims_dashboard_url(email: str, *, token: Optional[str] = None) -> str:
    settings = get_settings()
    base = settings.app_url.rstrip("/")
    access = token or create_my_esims_token(email)
    return f"{base}/dashboard?myEsimsToken={quote(access, safe='')}"


def summarize_order_card(order: Any) -> Dict[str, Any]:
    """Compact card fields for multi-eSIM list responses."""
    return {
        "order_number": getattr(order, "order_number", None),
        "package_name": getattr(order, "package_name", None),
        "country": getattr(order, "country", None),
        "flag": getattr(order, "flag", None),
        "status": getattr(order, "status", None),
        "activation_status": getattr(order, "activation_status", None),
        "data_remaining_gb": getattr(order, "data_remaining_gb", None),
        "data_total_gb": getattr(order, "data_total_gb", None),
        "days_remaining": getattr(order, "days_remaining", None),
        "wallet_balance_usd": getattr(order, "wallet_balance_usd", None),
        "fulfillment_pending": bool(getattr(order, "fulfillment_pending", False)),
        "created_at": getattr(order, "created_at", None),
    }
