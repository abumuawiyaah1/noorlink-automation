"""Enriched order context for admin support."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.api import supabase_repository as db


class AdminOrderContextError(Exception):
    """Order context lookup failed."""


def build_order_context(*, order_number: str) -> Dict[str, Any]:
    normalized = order_number.strip().upper()
    if not normalized:
        raise AdminOrderContextError("Order number is required.")

    try:
        row = db.get_order_row_by_order_number(normalized)
    except db.SupabaseRepositoryError as exc:
        raise AdminOrderContextError(str(exc)) from exc

    if not row:
        raise AdminOrderContextError(f"Order not found: {normalized}")

    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    gift = metadata.get("gift") if isinstance(metadata.get("gift"), dict) else {}
    reminders = metadata.get("reminders") if isinstance(metadata.get("reminders"), dict) else {}
    simbase = metadata.get("simbase") if isinstance(metadata.get("simbase"), dict) else {}
    complimentary = metadata.get("complimentary") if isinstance(metadata.get("complimentary"), dict) else {}
    topups = metadata.get("topups") if isinstance(metadata.get("topups"), list) else []

    breakage = None
    try:
        breakage = db.get_breakage_allowance_by_order_number(normalized)
    except Exception:
        pass

    reminder_labels = []
    if reminders.get("low_data_70_sent_at"):
        reminder_labels.append(f"Low data (70%) sent: {reminders['low_data_70_sent_at']}")
    if reminders.get("expiring_soon_sent_at"):
        reminder_labels.append(f"Expiring soon sent: {reminders['expiring_soon_sent_at']}")
    if reminders.get("expiry_sent_at"):
        reminder_labels.append(f"Expired notice sent: {reminders['expiry_sent_at']}")
    if not reminder_labels:
        reminder_labels.append("No reminder emails sent yet")

    return {
        "order_number": normalized,
        "status": row.get("status"),
        "email": row.get("email"),
        "country": row.get("country"),
        "package_name": row.get("package_name"),
        "amount_cents": row.get("amount_cents"),
        "iccid": row.get("iccid"),
        "data_used_gb": row.get("data_used_gb"),
        "data_total_gb": row.get("data_total_gb"),
        "paid_at": row.get("paid_at"),
        "fulfilled_at": row.get("fulfilled_at"),
        "is_gift": bool(gift.get("is_gift")),
        "gift_recipient_email": gift.get("recipient_email"),
        "gift_recipient_name": gift.get("recipient_name"),
        "gift_sender_name": gift.get("sender_name"),
        "gift_message": gift.get("message"),
        "reminder_labels": reminder_labels,
        "suspended_at": simbase.get("suspended_at"),
        "usage_guard": simbase.get("usage_guard"),
        "is_complimentary": bool(complimentary.get("granted_by")),
        "complimentary_reason": complimentary.get("reason"),
        "topup_count": len(topups),
        "breakage": breakage,
    }
