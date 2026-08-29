"""Newsletter subscriber admin helpers."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

from app.api import supabase_repository as db


class AdminNewsletterError(Exception):
    """Newsletter admin action failed."""


def list_subscriber_rows(*, active_only: bool = False, limit: int = 500) -> List[Dict[str, Any]]:
    client = db.get_supabase_client()
    try:
        query = (
            client.table("newsletter_subscribers")
            .select("email, dream_destination, source, subscribed_at, unsubscribed_at")
            .order("subscribed_at", desc=True)
            .limit(limit)
        )
        if active_only:
            query = query.is_("unsubscribed_at", "null")
        result = query.execute()
    except Exception as exc:
        raise AdminNewsletterError(str(exc)) from exc
    return result.data or []


def export_subscribers_csv(*, active_only: bool = True) -> str:
    rows = list_subscriber_rows(active_only=active_only, limit=5000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["email", "dream_destination", "source", "subscribed_at", "unsubscribed_at"])
    for row in rows:
        writer.writerow(
            [
                row.get("email") or "",
                row.get("dream_destination") or "",
                row.get("source") or "",
                row.get("subscribed_at") or "",
                row.get("unsubscribed_at") or "",
            ]
        )
    return buffer.getvalue()


def admin_unsubscribe(email: str) -> bool:
    try:
        return db.unsubscribe_newsletter_subscriber(email)
    except db.SupabaseRepositoryError as exc:
        raise AdminNewsletterError(str(exc)) from exc


def subscriber_stats() -> Dict[str, int]:
    rows = list_subscriber_rows(active_only=False, limit=5000)
    active = sum(1 for row in rows if not row.get("unsubscribed_at"))
    return {"total": len(rows), "active": active, "unsubscribed": len(rows) - active}
