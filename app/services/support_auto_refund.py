"""
Strict auto-refund for unanswered refund tickets (48h SLA).

Only runs when:
- Ticket is refund-related and still open/waiting
- No human staff outbound reply yet (auto replies don't count)
- Ticket age >= AUTO_REFUND_WAIT_HOURS (default 48)
- Order passes strict eligibility (low usage, amount cap, Stripe PI present)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import SupportMessage, SupportTicket
from app.services.admin_refunds import (
    AdminRefundError,
    REFUND_USAGE_THRESHOLD_PCT,
    _usage_percent,
    process_order_refund,
    validate_refund_eligibility,
)
from app.services.ops_alerts import notify_staff_governance
from app.services.ops_event_log import log_ops_event
from app.services.support_messaging import send_staff_reply

logger = logging.getLogger(__name__)

# Stricter than the admin wizard's 50% override threshold
AUTO_REFUND_MAX_USAGE_PCT = 20
AUTO_REFUND_MAX_AMOUNT_CENTS = 5000  # $50
AUTO_REFUND_WAIT_HOURS = 48
AUTO_REFUND_ACTOR = "auto-48h"


class AutoRefundSkip(Exception):
    """Ticket/order not eligible for auto-refund."""


def _wait_hours() -> int:
    settings = get_settings()
    raw = getattr(settings, "support_auto_refund_wait_hours", None)
    try:
        value = int(raw) if raw is not None and str(raw).strip() != "" else AUTO_REFUND_WAIT_HOURS
    except (TypeError, ValueError):
        value = AUTO_REFUND_WAIT_HOURS
    return max(1, value)


def _max_amount_cents() -> int:
    settings = get_settings()
    raw = getattr(settings, "support_auto_refund_max_cents", None)
    try:
        value = int(raw) if raw is not None and str(raw).strip() != "" else AUTO_REFUND_MAX_AMOUNT_CENTS
    except (TypeError, ValueError):
        value = AUTO_REFUND_MAX_AMOUNT_CENTS
    return max(100, value)


def ticket_has_human_reply(ticket_id: Any) -> bool:
    factory = get_session_factory()
    if factory is None:
        return True  # fail closed
    with factory() as session:
        messages = session.scalars(
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket_id)
            .where(SupportMessage.direction == "outbound")
        ).all()
        for msg in messages:
            username = (msg.admin_username or "").strip().lower()
            if username and username not in {"auto", AUTO_REFUND_ACTOR}:
                return True
        return False


def list_unanswered_refund_tickets(*, older_than_hours: Optional[int] = None) -> List[SupportTicket]:
    hours = older_than_hours if older_than_hours is not None else _wait_hours()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    factory = get_session_factory()
    if factory is None:
        return []

    with factory() as session:
        tickets = list(
            session.scalars(
                select(SupportTicket)
                .where(SupportTicket.status.in_(("open", "waiting")))
                .where(SupportTicket.created_at <= cutoff)
                .where(
                    or_(
                        SupportTicket.category == "refund",
                        SupportTicket.subject.ilike("%refund%"),
                        SupportTicket.message.ilike("%refund%"),
                    )
                )
                .order_by(SupportTicket.created_at.asc())
                .limit(50)
            ).all()
        )
        # Detach for use outside session
        for t in tickets:
            session.expunge(t)
        return tickets


def evaluate_strict_auto_refund(row: Dict[str, Any]) -> None:
    """Raise AutoRefundSkip if order fails strict policy."""
    try:
        validate_refund_eligibility(row=row, admin_override=False)
    except AdminRefundError as exc:
        # Wizard blocks at 50%; we also enforce a stricter 20% cap below
        if "used" in str(exc).lower() and "override" in str(exc).lower():
            raise AutoRefundSkip(str(exc)) from exc
        raise AutoRefundSkip(str(exc)) from exc

    usage_pct = _usage_percent(row)
    if usage_pct is not None and usage_pct >= AUTO_REFUND_MAX_USAGE_PCT:
        raise AutoRefundSkip(
            f"Usage {usage_pct:.0f}% is at/above auto-refund limit ({AUTO_REFUND_MAX_USAGE_PCT}%)."
        )

    amount = int(row.get("amount_cents") or 0)
    if amount > _max_amount_cents():
        raise AutoRefundSkip(
            f"Amount ${amount / 100:.2f} exceeds auto-refund cap "
            f"(${_max_amount_cents() / 100:.2f})."
        )

    if not str(row.get("stripe_payment_intent_id") or "").strip():
        raise AutoRefundSkip("No Stripe payment intent on file.")


def process_ticket_auto_refund(ticket: SupportTicket) -> Dict[str, Any]:
    if ticket_has_human_reply(ticket.id):
        raise AutoRefundSkip("Staff already replied — skipping auto-refund.")

    order_number = (ticket.order_number or "").strip().upper()
    if not order_number:
        from app.services.support_auto_reply import extract_order_number

        order_number = extract_order_number(ticket.subject, ticket.message) or ""
    if not order_number:
        raise AutoRefundSkip("No order number on ticket.")

    # Verify customer email owns the order
    try:
        looked = db.lookup_order(order_number, ticket.email)
    except Exception as exc:
        raise AutoRefundSkip(f"Order lookup failed: {exc}") from exc
    if not looked:
        raise AutoRefundSkip("Order not found for this customer email.")

    row = db.get_order_row_by_order_number(looked.order_number)
    if not row:
        raise AutoRefundSkip("Order row missing.")

    evaluate_strict_auto_refund(row)

    result = process_order_refund(
        order_number=looked.order_number,
        reason=f"auto_refund_after_{_wait_hours()}h_unanswered_ticket",
        admin_username=AUTO_REFUND_ACTOR,
        admin_override=False,
    )

    amount = result["amount_cents"] / 100
    reply_body = (
        f"Hi {ticket.name},\n\n"
        f"Because we did not reach you with a manual review within {_wait_hours()} hours, "
        f"we issued an automatic refund of ${amount:.2f} for order {result['order_number']} "
        f"under our unused / low-usage policy.\n\n"
        f"Most banks show the credit in 5–10 business days on the original payment method.\n\n"
        f"If anything still looks wrong, reply to this email.\n\n"
        f"— NoorLink Support"
    )
    try:
        send_staff_reply(
            ticket_number=ticket.ticket_number,
            body=reply_body,
            admin_username=AUTO_REFUND_ACTOR,
        )
    except Exception:
        logger.exception("Auto-refund succeeded but customer email failed for %s", ticket.ticket_number)

    # Close ticket
    factory = get_session_factory()
    if factory is not None:
        with factory() as session:
            fresh = session.execute(
                select(SupportTicket).where(SupportTicket.ticket_number == ticket.ticket_number)
            ).scalar_one_or_none()
            if fresh:
                fresh.status = "closed"
                fresh.assigned_to = AUTO_REFUND_ACTOR
                fresh.updated_at = datetime.now(timezone.utc)
                if not fresh.order_number:
                    fresh.order_number = result["order_number"]
                session.commit()

    log_ops_event(
        event_type="auto_refund_48h",
        source="cron",
        severity="warning",
        order_number=result["order_number"],
        message=f"Auto-refunded ${amount:.2f} after unanswered ticket {ticket.ticket_number}",
        details={
            "ticket": ticket.ticket_number,
            "refund_id": result["refund_id"],
            "wait_hours": _wait_hours(),
            "max_usage_pct": AUTO_REFUND_MAX_USAGE_PCT,
        },
    )

    notify_staff_governance(
        title=f"Auto-refund issued — {result['order_number']}",
        summary=(
            f"Ticket {ticket.ticket_number} unanswered {_wait_hours()}h+; "
            f"refunded ${amount:.2f} to {ticket.email}."
        ),
        details={
            "ticket": ticket.ticket_number,
            "order": result["order_number"],
            "refund_id": result["refund_id"],
            "amount": f"${amount:.2f}",
        },
    )

    return {
        "ticket": ticket.ticket_number,
        "order_number": result["order_number"],
        "refund_id": result["refund_id"],
        "amount_cents": result["amount_cents"],
        "status": "refunded",
    }


def process_unanswered_auto_refunds() -> Dict[str, Any]:
    """Cron entry: scan unanswered refund tickets and refund when strict rules pass."""
    wait = _wait_hours()
    tickets = list_unanswered_refund_tickets(older_than_hours=wait)
    processed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for ticket in tickets:
        try:
            processed.append(process_ticket_auto_refund(ticket))
        except AutoRefundSkip as exc:
            skipped.append({"ticket": ticket.ticket_number, "reason": str(exc)})
        except AdminRefundError as exc:
            skipped.append({"ticket": ticket.ticket_number, "reason": str(exc)})
            logger.warning("Auto-refund Stripe/policy failed for %s: %s", ticket.ticket_number, exc)
        except Exception as exc:
            skipped.append({"ticket": ticket.ticket_number, "reason": str(exc)[:200]})
            logger.exception("Auto-refund failed for %s", ticket.ticket_number)

    return {
        "success": True,
        "wait_hours": wait,
        "candidates": len(tickets),
        "refunded": len(processed),
        "skipped": len(skipped),
        "processed": processed,
        "skip_details": skipped[:20],
        "policy": {
            "max_usage_pct": AUTO_REFUND_MAX_USAGE_PCT,
            "max_amount_cents": _max_amount_cents(),
            "wizard_usage_threshold_pct": REFUND_USAGE_THRESHOLD_PCT,
        },
    }
