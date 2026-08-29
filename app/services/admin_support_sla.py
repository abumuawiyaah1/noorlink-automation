"""Support SLA helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import SupportTicket


def list_sla_breaches(*, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
    factory = get_session_factory()
    if factory is None:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with factory() as session:
        tickets = session.scalars(
            select(SupportTicket)
            .where(SupportTicket.status == "open")
            .where(SupportTicket.created_at <= cutoff)
            .order_by(SupportTicket.created_at.asc())
            .limit(limit)
        ).all()

    results: List[Dict[str, Any]] = []
    for ticket in tickets:
        age_hours = (datetime.now(timezone.utc) - ticket.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        results.append(
            {
                "ticket_number": ticket.ticket_number,
                "email": ticket.email,
                "subject": ticket.subject,
                "assigned_to": ticket.assigned_to,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
                "age_hours": round(age_hours, 1),
            }
        )
    return results


def sla_summary() -> Dict[str, Any]:
    breaches = list_sla_breaches()
    unassigned = [t for t in breaches if not t.get("assigned_to")]
    return {
        "waiting_over_24h": len(breaches),
        "unassigned_over_24h": len(unassigned),
        "tickets": breaches[:20],
    }
