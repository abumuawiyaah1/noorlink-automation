"""Persist operational events for admin visibility."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.api import supabase_repository as db

logger = logging.getLogger(__name__)


def log_ops_event(
    *,
    event_type: str,
    source: str,
    message: str,
    severity: str = "info",
    order_number: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Best-effort insert — never raises to callers."""
    try:
        client = db.get_supabase_client()
        client.table("ops_event_log").insert(
            {
                "id": str(uuid4()),
                "event_type": event_type,
                "source": source,
                "severity": severity,
                "order_number": (order_number or "").strip().upper() or None,
                "message": message[:500],
                "details": details or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as exc:
        logger.warning("ops_event_log insert failed: %s", exc)


def list_ops_events(
    *,
    limit: int = 100,
    event_type: Optional[str] = None,
    event_type_prefix: Optional[str] = None,
    order_number: Optional[str] = None,
) -> List[Dict[str, Any]]:
    try:
        client = db.get_supabase_client()
        query = client.table("ops_event_log").select("*").order("created_at", desc=True).limit(limit)
        if event_type:
            query = query.eq("event_type", event_type)
        if order_number:
            query = query.eq("order_number", order_number.strip().upper())
        result = query.execute()
        rows = result.data or []
        if event_type_prefix:
            rows = [
                row
                for row in rows
                if str(row.get("event_type") or "").startswith(event_type_prefix)
            ]
        return rows
    except Exception as exc:
        logger.warning("ops_event_log list failed: %s", exc)
        return []


def log_email_delivery(
    *,
    event_type: str,
    recipient: str,
    email_type: str,
    subject: Optional[str] = None,
    message_id: Optional[str] = None,
    insider_slug: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        client = db.get_supabase_client()
        client.table("email_delivery_events").insert(
            {
                "id": str(uuid4()),
                "event_type": event_type,
                "recipient": recipient.strip().lower(),
                "email_type": email_type,
                "subject": subject,
                "message_id": message_id,
                "insider_slug": insider_slug,
                "details": details or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as exc:
        logger.warning("email_delivery_events insert failed: %s", exc)


def email_analytics_summary(*, days: int = 30) -> Dict[str, Any]:
    try:
        client = db.get_supabase_client()
        result = (
            client.table("email_delivery_events")
            .select("email_type, event_type, insider_slug")
            .order("created_at", desc=True)
            .limit(2000)
            .execute()
        )
        rows = result.data or []
    except Exception:
        rows = []

    by_type: Dict[str, int] = {}
    by_event: Dict[str, int] = {}
    insider_sends: Dict[str, int] = {}
    for row in rows:
        et = str(row.get("email_type") or "other")
        ev = str(row.get("event_type") or "sent")
        by_type[et] = by_type.get(et, 0) + 1
        by_event[ev] = by_event.get(ev, 0) + 1
        slug = row.get("insider_slug")
        if slug and et == "insider":
            insider_sends[str(slug)] = insider_sends.get(str(slug), 0) + 1

    return {
        "total_logged": len(rows),
        "by_email_type": by_type,
        "by_event_type": by_event,
        "insider_sends": insider_sends,
    }
