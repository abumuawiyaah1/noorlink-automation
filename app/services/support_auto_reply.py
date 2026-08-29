"""Automatic first-response for support tickets (MVP until support scales)."""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import SupportMessage, SupportTicket
from app.services.email_brand import wrap_branded_email
from app.services.email_service import EmailDeliveryError, send_email
from app.services.support_categories import get_category_config

logger = logging.getLogger(__name__)

ORDER_RE = re.compile(r"\b(NL-[A-Z0-9]{6,12})\b", re.IGNORECASE)

# Always escalate to a human
HUMAN_KEYWORDS = (
    "refund",
    "chargeback",
    "lawyer",
    "attorney",
    "gdpr",
    "delete my data",
    "sue",
    "fraud",
    "stolen",
    "unauthorized charge",
)

QR_MISSING_KEYWORDS = (
    "no qr",
    "didn't get",
    "did not get",
    "haven't received",
    "have not received",
    "missing qr",
    "where's my qr",
    "where is my qr",
    "no email",
    "didn't receive",
    "did not receive",
    "resend",
    "re-send",
    "send again",
    "never got",
    "still waiting for qr",
)

INSTALL_KEYWORDS = (
    "install",
    "activate",
    "how to set up",
    "setup",
    "set up",
    "add esim",
    "scan",
    "not working",
    "won't connect",
    "cant connect",
    "can't connect",
)


def extract_order_number(*texts: Optional[str]) -> Optional[str]:
    for text in texts:
        if not text:
            continue
        match = ORDER_RE.search(text)
        if match:
            return match.group(1).upper()
    return None


def _blob(*parts: Optional[str]) -> str:
    return " ".join(p.strip().lower() for p in parts if p and p.strip())


def classify_intent(*, subject: Optional[str], message: str, category: Optional[str]) -> str:
    """Return intent: refund | qr_missing | install | order_status | general."""
    text = _blob(subject, message, category)
    if any(k in text for k in HUMAN_KEYWORDS) or (category or "") == "refund":
        return "refund"
    if any(k in text for k in QR_MISSING_KEYWORDS):
        return "qr_missing"
    if (category or "") == "install_qr" or any(k in text for k in INSTALL_KEYWORDS):
        return "install"
    if (category or "") == "order_help" or "order" in text:
        return "order_status"
    return "general"


def _self_serve_links() -> str:
    settings = get_settings()
    base = settings.app_url.rstrip("/")
    return (
        f"• Look up your order / usage: {base}/dashboard\n"
        f"• Destinations & plans: {base}/destinations\n"
        f"• Install tips: {base}/support\n"
    )


def _lookup_order_row(*, email: str, order_number: Optional[str]) -> Optional[Dict[str, Any]]:
    if not order_number:
        return None
    try:
        looked = db.lookup_order(order_number, email)
        if not looked:
            return None
        return db.get_order_row_by_order_number(looked.order_number)
    except Exception:
        logger.exception("Auto-reply order lookup failed for %s", order_number)
        return None


def _order_status_lines(row: Dict[str, Any]) -> Tuple[str, bool]:
    """Return (customer-facing paragraph, has_qr)."""
    status = str(row.get("status") or "unknown")
    order_number = str(row.get("order_number") or "")
    has_qr = bool(row.get("qr_code_url") or row.get("lpa_string"))
    package = str(row.get("package_name") or "your plan")
    country = str(row.get("country") or "")

    if status == "refunded":
        return (
            f"Order {order_number} shows as refunded. If you still see a charge, wait 5–10 "
            "business days for your bank, then reply here with a screenshot.",
            False,
        )
    if status in {"paid"} and not has_qr:
        return (
            f"We see payment for {order_number} ({package}"
            + (f" — {country}" if country else "")
            + "). Your eSIM is still being prepared. If it has been more than 15 minutes, "
            "reply here and we will push fulfillment again.",
            False,
        )
    if has_qr and status in {"paid", "delivered", "active", "suspended", "expired"}:
        tip = (
            f"Order {order_number} is {status}. Your QR / install email should already be in your inbox "
            "(check spam and promotions). You can also open the order on the dashboard and resend the QR."
        )
        if status == "suspended":
            tip += " This eSIM looks suspended (often data used up) — top-up from the dashboard if you need more data."
        return tip, True
    return (
        f"Order {order_number} is currently marked “{status}”. Our team can dig in if this still looks wrong.",
        has_qr,
    )


def build_auto_reply_body(
    *,
    name: str,
    intent: str,
    order_row: Optional[Dict[str, Any]],
    qr_resent: bool,
    qr_resend_error: Optional[str],
) -> str:
    greet = f"Hi {name.strip() or 'there'},"
    links = _self_serve_links()
    parts: List[str] = [greet, ""]

    if intent == "refund":
        parts.extend(
            [
                "Thanks for writing about a refund. For money-related requests a teammate reviews "
                "usage and payment details before we approve anything.",
                "",
                "While you wait, please reply with:",
                "• Your order ID (NL-……)",
                "• The email used at checkout",
                "• A short note on why you need a refund",
                "",
                "Someone will follow up — usually within 24 hours.",
            ]
        )
    elif order_row:
        status_text, _ = _order_status_lines(order_row)
        parts.append(status_text)
        parts.append("")
        if qr_resent:
            parts.append(
                "We just resent your eSIM / QR email. Please check inbox and spam within a few minutes."
            )
            parts.append("")
        elif qr_resend_error:
            parts.append(
                f"We tried to resend your QR automatically but could not ({qr_resend_error}). "
                "A teammate will follow up if needed."
            )
            parts.append("")
        if intent == "install":
            parts.extend(
                [
                    "Quick install tips:",
                    "1. Connect to Wi‑Fi before you fly",
                    "2. Open the QR email (or dashboard) and scan / tap the install link",
                    "3. After install, turn on Data Roaming for the NoorLink line when you land",
                    "",
                ]
            )
    else:
        if intent in {"qr_missing", "install", "order_status"}:
            parts.extend(
                [
                    "Thanks for reaching out. To look up your eSIM automatically, reply with your "
                    "order ID (starts with NL-) and the email used at checkout — or open the dashboard link below.",
                    "",
                ]
            )
        else:
            parts.extend(
                [
                    "Thanks for contacting NoorLink. A teammate typically replies within 24 hours.",
                    "If this is about an order, include your NL- order ID so we can help faster.",
                    "",
                ]
            )

    parts.extend(["Helpful links:", links, "— NoorLink Support"])
    return "\n".join(parts).strip()


def _should_try_qr_resend(*, intent: str, order_row: Optional[Dict[str, Any]]) -> bool:
    if intent not in {"qr_missing", "install", "order_status"}:
        return False
    if not order_row:
        return False
    if not (order_row.get("qr_code_url") or order_row.get("lpa_string")):
        return False
    status = str(order_row.get("status") or "")
    return status in {"paid", "delivered", "active", "suspended"}


def run_support_auto_reply(
    *,
    ticket_number: str,
    name: str,
    email: str,
    subject: Optional[str],
    message: str,
    order_number: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a helpful first reply, optionally resend QR, close if solved.
    Returns flags for staff notification routing.
    """
    intent = classify_intent(subject=subject, message=message, category=category)
    order_id = order_number or extract_order_number(subject, message)
    order_row = _lookup_order_row(email=email, order_number=order_id)

    # Persist extracted order on ticket when missing
    if order_id and order_row:
        _ensure_ticket_order(ticket_number, order_id)

    qr_resent = False
    qr_resend_error: Optional[str] = None
    if _should_try_qr_resend(intent=intent, order_row=order_row) and intent in {
        "qr_missing",
        "install",
    }:
        try:
            from app.services.customer_self_service import (
                CustomerSelfServiceError,
                customer_resend_esim_email,
            )

            customer_resend_esim_email(order_number=str(order_row["order_number"]), email=email)
            qr_resent = True
        except CustomerSelfServiceError as exc:
            qr_resend_error = str(exc)
        except Exception as exc:
            qr_resend_error = str(exc)[:200]
            logger.exception("Auto QR resend failed for %s", ticket_number)

    needs_human = intent == "refund" or (
        intent in {"qr_missing", "order_status"} and order_row is None
    )
    # Paid but no QR yet → human/ops should see it
    if order_row and str(order_row.get("status")) == "paid" and not (
        order_row.get("qr_code_url") or order_row.get("lpa_string")
    ):
        needs_human = True

    # Successful QR resend or clear status + install tips → auto-close
    auto_resolved = False
    if qr_resent:
        auto_resolved = True
        needs_human = False
    elif (
        intent == "install"
        and order_row
        and (order_row.get("qr_code_url") or order_row.get("lpa_string"))
        and not needs_human
    ):
        auto_resolved = True
    elif intent == "order_status" and order_row and not needs_human:
        # Gave clear status; leave open only if stuck paid-no-qr (already needs_human)
        auto_resolved = str(order_row.get("status")) not in {"paid"} or bool(
            order_row.get("qr_code_url") or order_row.get("lpa_string")
        )

    if intent == "refund":
        auto_resolved = False
        needs_human = True

    body = build_auto_reply_body(
        name=name,
        intent=intent,
        order_row=order_row,
        qr_resent=qr_resent,
        qr_resend_error=qr_resend_error,
    )

    try:
        _send_auto_outbound(
            ticket_number=ticket_number,
            body=body,
            close=auto_resolved,
        )
    except Exception:
        logger.exception("Failed to send support auto-reply for %s", ticket_number)
        return {
            "sent": False,
            "needs_human": True,
            "auto_resolved": False,
            "intent": intent,
            "order_number": order_id,
            "qr_resent": False,
        }

    return {
        "sent": True,
        "needs_human": needs_human,
        "auto_resolved": auto_resolved,
        "intent": intent,
        "order_number": (order_row or {}).get("order_number") or order_id,
        "qr_resent": qr_resent,
        "qr_resend_error": qr_resend_error,
    }


def _ensure_ticket_order(ticket_number: str, order_number: str) -> None:
    factory = get_session_factory()
    if factory is None:
        return
    with factory() as session:
        ticket = session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number.strip().upper())
        ).scalar_one_or_none()
        if ticket and not ticket.order_number:
            ticket.order_number = order_number
            session.commit()


def _send_auto_outbound(*, ticket_number: str, body: str, close: bool) -> None:
    settings = get_settings()
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL required for auto-reply")

    with factory() as session:
        ticket = session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number.strip().upper())
        ).scalar_one_or_none()
        if ticket is None:
            raise RuntimeError(f"Ticket {ticket_number} not found")

        category = get_category_config(ticket.category)
        subject = f"Re: [{ticket.ticket_number}] {ticket.subject or category['label']}"
        safe_body = html.escape(body).replace("\n", "<br/>")
        order_line = ""
        if ticket.order_number:
            order_line = (
                f'<p style="margin:0 0 12px;color:#334155;font-size:14px;">Order: '
                f"<strong>{html.escape(ticket.order_number)}</strong></p>"
            )

        html_body = f"""
          {order_line}
          <div style="margin:0 0 16px;padding:16px;background:#F3F7F7;border-radius:10px;border:1px solid #E5E7EB;">
            <p style="margin:0;color:#111827;line-height:1.6;">{safe_body}</p>
          </div>
          <p style="margin:0;color:#6B7280;font-size:13px;">
            Reply to this email if you still need help. Ticket {html.escape(ticket.ticket_number)}.
          </p>
        """
        full_html = wrap_branded_email(
            eyebrow="Quick help",
            title="Automatic reply from NoorLink",
            body_html=html_body,
            app_url=settings.app_url,
            tip="A teammate will step in if this did not solve it.",
        )

        try:
            resend_id = send_email(
                to_email=ticket.email,
                subject=subject[:240],
                html_body=full_html,
                text_body=body,
                reply_to=settings.support_email,
            )
        except EmailDeliveryError as exc:
            raise RuntimeError(str(exc)) from exc

        outbound = SupportMessage(
            ticket_id=ticket.id,
            order_number=ticket.order_number,
            direction="outbound",
            from_email=settings.support_email,
            to_email=ticket.email,
            subject=subject[:240],
            body_text=body,
            body_html=full_html,
            resend_email_id=resend_id,
            admin_username="auto",
            created_at=now,
        )
        ticket.last_message_at = now
        ticket.updated_at = now
        ticket.assigned_to = ticket.assigned_to or "auto"
        ticket.status = "closed" if close else "waiting"
        session.add(outbound)
        session.commit()
