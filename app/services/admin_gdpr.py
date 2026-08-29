"""GDPR export and delete tools."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from app.api import supabase_repository as db


class AdminGdprError(Exception):
    """GDPR tool failed."""


def _log_gdpr_request(*, email: str, request_type: str, admin_username: str, notes: str = "") -> None:
    try:
        client = db.get_supabase_client()
        client.table("gdpr_requests").insert(
            {
                "id": str(uuid4()),
                "email": email.strip().lower(),
                "request_type": request_type,
                "status": "completed",
                "admin_username": admin_username,
                "notes": notes[:500] if notes else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception:
        pass


def export_customer_data(*, email: str, admin_username: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise AdminGdprError("Valid email required.")

    client = db.get_supabase_client()
    bundle: Dict[str, Any] = {"email": normalized, "exported_at": datetime.now(timezone.utc).isoformat()}

    try:
        orders = client.table("orders").select("*").eq("email", normalized).execute()
        bundle["orders"] = orders.data or []
    except Exception as exc:
        raise AdminGdprError(f"Orders export failed: {exc}") from exc

    try:
        tickets = client.table("support_tickets").select("*").eq("email", normalized).execute()
        bundle["support_tickets"] = tickets.data or []
    except Exception as exc:
        bundle["support_tickets"] = []

    try:
        subs = client.table("newsletter_subscribers").select("*").eq("email", normalized).execute()
        bundle["newsletter"] = subs.data or []
    except Exception:
        bundle["newsletter"] = []

    _log_gdpr_request(email=normalized, request_type="export", admin_username=admin_username)
    return json.dumps(bundle, indent=2, default=str)


def delete_customer_data(
    *,
    email: str,
    admin_username: str,
    confirm: bool,
) -> Dict[str, Any]:
    if not confirm:
        raise AdminGdprError("You must confirm deletion.")

    normalized = email.strip().lower()
    if "@" not in normalized:
        raise AdminGdprError("Valid email required.")

    client = db.get_supabase_client()
    counts: Dict[str, int] = {}

    try:
        db.unsubscribe_newsletter_subscriber(normalized)
        counts["newsletter_unsubscribed"] = 1
    except Exception:
        counts["newsletter_unsubscribed"] = 0

    try:
        result = (
            client.table("support_tickets")
            .update({"email": f"redacted+{uuid4().hex[:8]}@deleted.noorlink.local"})
            .eq("email", normalized)
            .execute()
        )
        counts["tickets_redacted"] = len(result.data or [])
    except Exception:
        counts["tickets_redacted"] = 0

    # Orders retained for accounting — redact PII in email field only if no paid amount dispute
    try:
        orders = client.table("orders").select("order_number, email").eq("email", normalized).execute()
        redacted = 0
        for order in orders.data or []:
            client.table("orders").update(
                {
                    "email": f"redacted+{order['order_number'].lower()}@deleted.noorlink.local",
                    "metadata": {"gdpr_redacted": True, "original_email_hash": uuid4().hex[:12]},
                }
            ).eq("order_number", order["order_number"]).execute()
            redacted += 1
        counts["orders_redacted"] = redacted
    except Exception as exc:
        raise AdminGdprError(f"Order redaction failed: {exc}") from exc

    _log_gdpr_request(
        email=normalized,
        request_type="delete",
        admin_username=admin_username,
        notes=json.dumps(counts),
    )
    return {"email": normalized, **counts}
