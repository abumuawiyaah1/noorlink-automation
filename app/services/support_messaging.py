"""Support ticket threads — create, reply, inbound email matching."""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.support_categories import (
    get_category_config,
    get_reply_template,
    list_reply_templates,
    normalize_support_category,
)
from app.services.support_language import detect_ticket_language
from app.db.engine import get_session_factory
from app.db.models import AdminUser, SupportMessage, SupportTicket
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger(__name__)

TICKET_RE = re.compile(r"\b(TCK-[A-F0-9]{8})\b", re.IGNORECASE)


class SupportMessagingError(Exception):
    """Support thread operation failed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_order_number(value: Optional[str]) -> Optional[str]:
    cleaned = (value or "").strip().upper()
    return cleaned or None


def parse_ticket_number(subject: Optional[str], body: Optional[str] = None) -> Optional[str]:
    for text in (subject or "", body or ""):
        match = TICKET_RE.search(text)
        if match:
            return match.group(1).upper()
    return None


def ticket_subject_tag(ticket_number: str) -> str:
    return f"[{ticket_number.upper()}]"


def build_thread_subject(ticket: SupportTicket, *, is_reply: bool = False) -> str:
    base = (ticket.subject or "Support request").strip()
    tag = ticket_subject_tag(ticket.ticket_number)
    if tag in base:
        subject = base
    elif is_reply and base.lower().startswith("re:"):
        subject = f"Re: {tag} {base[3:].strip()}"
    elif is_reply:
        subject = f"Re: {tag} {base}"
    else:
        subject = f"{tag} {base}"
    return subject[:240]


def _require_session() -> Session:
    factory = get_session_factory()
    if factory is None:
        raise SupportMessagingError("DATABASE_URL is required for support messaging.")
    return factory()


def create_ticket_from_contact(
    *,
    name: str,
    email: str,
    subject: Optional[str],
    message: str,
    order_number: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Create ticket + first inbound message (website contact form)."""
    settings = get_settings()
    ticket_number = f"TCK-{uuid4().hex[:8].upper()}"
    now = _utc_now()
    order = _normalize_order_number(order_number)
    customer_email = email.strip().lower()
    subject_clean = (subject or "Support request").strip()
    category = normalize_support_category(subject_clean)
    lang = detect_ticket_language(message=message, hint=language)

    with _require_session() as session:
        ticket = SupportTicket(
            id=uuid4(),
            ticket_number=ticket_number,
            name=name.strip(),
            email=customer_email,
            subject=subject_clean,
            message=message.strip(),
            order_number=order,
            category=category,
            language=lang,
            status="open",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(ticket)
        session.flush()

        inbound = SupportMessage(
            ticket_id=ticket.id,
            order_number=order,
            direction="inbound",
            from_email=customer_email,
            to_email=settings.support_email,
            subject=build_thread_subject(ticket, is_reply=False),
            body_text=message.strip(),
            body_html=None,
            created_at=now,
        )
        session.add(inbound)
        session.commit()

        return {
            "ticket_number": ticket_number,
            "ticket_id": str(ticket.id),
            "order_number": order,
            "category": category,
            "name": name.strip(),
            "email": customer_email,
            "subject": subject_clean,
            "message": message.strip(),
        }


def list_tickets_for_inbox(*, status: Optional[str] = None, limit: int = 100) -> List[SupportTicket]:
    with _require_session() as session:
        stmt = select(SupportTicket).order_by(SupportTicket.last_message_at.desc().nullslast())
        if status:
            stmt = stmt.where(SupportTicket.status == status)
        stmt = stmt.limit(limit)
        return list(session.scalars(stmt).all())


def get_ticket_by_number(ticket_number: str) -> Optional[SupportTicket]:
    with _require_session() as session:
        return session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number.strip().upper())
        ).scalar_one_or_none()


def list_messages_for_ticket(ticket_id: str) -> List[SupportMessage]:
    with _require_session() as session:
        return list(
            session.scalars(
                select(SupportMessage)
                .where(SupportMessage.ticket_id == ticket_id)
                .order_by(SupportMessage.created_at.asc())
            ).all()
        )


def list_tickets_for_order(order_number: str) -> List[SupportTicket]:
    order = _normalize_order_number(order_number)
    if not order:
        return []
    with _require_session() as session:
        return list(
            session.scalars(
                select(SupportTicket)
                .where(SupportTicket.order_number == order)
                .order_by(SupportTicket.created_at.desc())
            ).all()
        )


def list_messages_for_order(order_number: str, *, customer_email: str) -> List[Dict[str, Any]]:
    """Customer-safe thread (must match ticket email)."""
    order = _normalize_order_number(order_number)
    email = customer_email.strip().lower()
    if not order or not email:
        return []

    with _require_session() as session:
        tickets = list(
            session.scalars(
                select(SupportTicket).where(
                    SupportTicket.order_number == order,
                    SupportTicket.email == email,
                )
            ).all()
        )
        if not tickets:
            return []

        ticket_ids = [t.id for t in tickets]
        ticket_map = {t.id: t.ticket_number for t in tickets}
        messages = list(
            session.scalars(
                select(SupportMessage)
                .where(SupportMessage.ticket_id.in_(ticket_ids))
                .order_by(SupportMessage.created_at.asc())
            ).all()
        )

    return [_message_to_public_dict(m, ticket_map.get(m.ticket_id)) for m in messages]


def _message_to_public_dict(message: SupportMessage, ticket_number: Optional[str] = None) -> Dict[str, Any]:
    body = (message.body_text or "").strip()
    if not body and message.body_html:
        body = html.unescape(re.sub(r"<[^>]+>", " ", message.body_html))
    return {
        "direction": message.direction,
        "from_email": message.from_email,
        "subject": message.subject,
        "body": body,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "ticket_number": ticket_number,
    }


def record_inbound_email(
    *,
    from_email: str,
    to_email: str,
    subject: Optional[str],
    body_text: Optional[str],
    body_html: Optional[str] = None,
    resend_email_id: Optional[str] = None,
    message_id_header: Optional[str] = None,
    in_reply_to: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Match inbound support email to a ticket and append message."""
    customer_email = from_email.strip().lower()
    ticket_number = parse_ticket_number(subject, body_text)
    now = _utc_now()

    with _require_session() as session:
        ticket: Optional[SupportTicket] = None
        if ticket_number:
            ticket = session.execute(
                select(SupportTicket).where(SupportTicket.ticket_number == ticket_number)
            ).scalar_one_or_none()

        if ticket is None:
            # Fallback: most recent open ticket for this email (7-day window heuristic)
            ticket = session.execute(
                select(SupportTicket)
                .where(SupportTicket.email == customer_email, SupportTicket.status != "closed")
                .order_by(SupportTicket.last_message_at.desc().nullslast())
                .limit(1)
            ).scalar_one_or_none()

        if ticket is None:
            logger.info("Inbound email ignored — no matching ticket for %s", customer_email)
            return None

        body = (body_text or "").strip()
        if not body and body_html:
            body = html.unescape(re.sub(r"<[^>]+>", " ", body_html)).strip()

        msg = SupportMessage(
            ticket_id=ticket.id,
            order_number=ticket.order_number,
            direction="inbound",
            from_email=customer_email,
            to_email=to_email.strip().lower(),
            subject=subject,
            body_text=body or "(empty message)",
            body_html=body_html,
            resend_email_id=resend_email_id,
            message_id_header=message_id_header,
            in_reply_to=in_reply_to,
            created_at=now,
        )
        ticket.last_message_at = now
        ticket.updated_at = now
        if ticket.status in {"waiting", "closed"}:
            ticket.status = "open"
        session.add(msg)
        session.commit()

        return {
            "ticket_number": ticket.ticket_number,
            "message_id": str(msg.id),
            "order_number": ticket.order_number,
        }


def send_staff_reply(
    *,
    ticket_number: str,
    body: str,
    admin_username: str,
    template_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Send branded email reply to customer and record outbound message."""
    settings = get_settings()
    if len(body.strip()) > 8000:
        raise SupportMessagingError("Reply is too long.")

    now = _utc_now()

    with _require_session() as session:
        ticket = session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number.strip().upper())
        ).scalar_one_or_none()
        if ticket is None:
            raise SupportMessagingError(f"Ticket {ticket_number} not found.")

        if not body.strip() and template_key:
            body = (get_reply_template(ticket.category, template_key) or "").strip()
        if not body:
            raise SupportMessagingError("Reply message cannot be empty.")

        category = get_category_config(ticket.category)
        subject = build_thread_subject(ticket, is_reply=True)
        safe_body = html.escape(body).replace("\n", "<br/>")
        order_line = ""
        if ticket.order_number:
            order_line = f"<p style=\"margin:0 0 12px;color:#334155;font-size:14px;\">Order: <strong>{html.escape(ticket.order_number)}</strong></p>"

        html_body = f"""
          <p style="margin:0 0 16px;">Hi {html.escape(ticket.name)},</p>
          {order_line}
          <div style="margin:0 0 16px;padding:16px;background:#F3F7F7;border-radius:10px;border:1px solid #E5E7EB;">
            <p style="margin:0;color:#111827;line-height:1.6;">{safe_body}</p>
          </div>
          <p style="margin:0;color:#6B7280;font-size:13px;">
            Reply to this email to continue the conversation. Ticket {html.escape(ticket.ticket_number)}.
          </p>
        """
        from app.services.email_brand import wrap_branded_email

        full_html = wrap_branded_email(
            eyebrow=category["reply_eyebrow"],
            title=category["reply_title"],
            body_html=html_body,
            app_url=settings.app_url,
            tip=category["reply_tip"],
        )

        try:
            resend_id = send_email(
                to_email=ticket.email,
                subject=subject,
                html_body=full_html,
                text_body=(
                    f"Hi {ticket.name},\n\n"
                    f"{body}\n\n"
                    f"Reply to this email to continue the conversation. "
                    f"Ticket {ticket.ticket_number}."
                    + (f"\nOrder: {ticket.order_number}" if ticket.order_number else "")
                ),
                reply_to=settings.support_email,
            )
        except EmailDeliveryError as exc:
            raise SupportMessagingError(str(exc)) from exc

        outbound = SupportMessage(
            ticket_id=ticket.id,
            order_number=ticket.order_number,
            direction="outbound",
            from_email=settings.support_email,
            to_email=ticket.email,
            subject=subject,
            body_text=body,
            body_html=full_html,
            resend_email_id=resend_id,
            admin_username=admin_username,
            created_at=now,
        )
        ticket.last_message_at = now
        ticket.updated_at = now
        ticket.status = "waiting"
        session.add(outbound)
        session.commit()

        return {
            "ticket_number": ticket.ticket_number,
            "resend_email_id": resend_id,
            "order_number": ticket.order_number,
        }


def update_ticket_status(ticket_number: str, status: str) -> None:
    allowed = {"open", "waiting", "closed"}
    if status not in allowed:
        raise SupportMessagingError(f"Invalid status: {status}")
    with _require_session() as session:
        ticket = session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number.strip().upper())
        ).scalar_one_or_none()
        if ticket is None:
            raise SupportMessagingError("Ticket not found.")
        ticket.status = status
        ticket.updated_at = _utc_now()
        session.commit()


def list_assignable_admins() -> List[AdminUser]:
    with _require_session() as session:
        return list(
            session.execute(
                select(AdminUser)
                .where(AdminUser.is_active.is_(True))
                .order_by(AdminUser.display_name, AdminUser.username)
            )
            .scalars()
            .all()
        )


def assign_support_ticket(
    *,
    ticket_number: str,
    assignee_username: str,
) -> Dict[str, Any]:
    """Assign ticket to an admin user and send notification emails."""
    from app.services.support_notifications import (
        send_customer_ticket_assigned,
        send_staff_ticket_assigned,
    )

    assignee_username = assignee_username.strip()
    if not assignee_username:
        raise SupportMessagingError("Choose a team member to assign.")

    now = _utc_now()
    with _require_session() as session:
        ticket = session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number.strip().upper())
        ).scalar_one_or_none()
        if ticket is None:
            raise SupportMessagingError(f"Ticket {ticket_number} not found.")

        assignee = session.execute(
            select(AdminUser).where(
                AdminUser.username == assignee_username,
                AdminUser.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if assignee is None:
            raise SupportMessagingError(f"Admin user {assignee_username} not found.")

        previous = ticket.assigned_to
        ticket.assigned_to = assignee.username
        ticket.assigned_at = now
        ticket.updated_at = now
        session.commit()

        display_name = (assignee.display_name or assignee.username).strip()
        staff_email = (assignee.notify_email or "").strip()

    if previous == assignee_username:
        return {
            "ticket_number": ticket_number,
            "assigned_to": assignee_username,
            "skipped_notifications": True,
        }

    try:
        send_customer_ticket_assigned(
            to_email=ticket.email,
            name=ticket.name,
            ticket_id=ticket.ticket_number,
            assignee_display_name=display_name,
            subject=ticket.subject,
            category=ticket.category,
            order_number=ticket.order_number,
        )
    except EmailDeliveryError as exc:
        raise SupportMessagingError(f"Assignment saved but customer email failed: {exc}") from exc

    if staff_email:
        try:
            send_staff_ticket_assigned(
                to_email=staff_email,
                ticket_id=ticket.ticket_number,
                customer_name=ticket.name,
                customer_email=ticket.email,
                subject=ticket.subject,
                category=ticket.category,
                order_number=ticket.order_number,
            )
        except EmailDeliveryError:
            logger.exception("Staff assignment email failed for %s", assignee_username)

    return {
        "ticket_number": ticket_number,
        "assigned_to": assignee_username,
        "display_name": display_name,
    }
