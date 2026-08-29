"""Branded support ticket notification emails."""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.email_brand import wrap_branded_email
from app.services.email_service import EmailDeliveryError, send_email
from app.services.support_categories import category_label, get_category_config, normalize_support_category

logger = logging.getLogger(__name__)


def _staff_notify_addresses() -> List[str]:
    settings = get_settings()
    addresses: List[str] = []
    support = (settings.support_email or "").strip()
    if support:
        addresses.append(support)
    extra = (getattr(settings, "support_staff_notify_emails", "") or "").strip()
    if extra:
        for part in extra.split(","):
            addr = part.strip()
            if addr and addr not in addresses:
                addresses.append(addr)
    return addresses


def send_customer_ticket_received(
    *,
    to_email: str,
    name: str,
    ticket_id: str,
    subject: Optional[str],
    message: str,
    order_number: Optional[str] = None,
    category: Optional[str] = None,
) -> str:
    """Branded confirmation when a customer submits a support ticket."""
    settings = get_settings()
    slug = category or normalize_support_category(subject)
    config = get_category_config(slug)
    safe_name = html.escape(name.strip() or "there")
    safe_ticket = html.escape(ticket_id)
    safe_subject = html.escape((subject or config["label"]).strip())
    safe_message = html.escape(message.strip()).replace("\n", "<br/>")
    order_block = ""
    if order_number:
        order_block = (
            f'<p style="margin:0 0 16px;"><strong style="color:#0F3D3E;">Order:</strong> '
            f"{html.escape(order_number)}</p>"
        )

    body = f"""
      <p style="margin:0 0 16px;">Hi {safe_name},</p>
      <p style="margin:0 0 16px;">{html.escape(config["received_intro"])}</p>
      <p style="margin:0 0 8px;"><strong style="color:#0F3D3E;">Ticket:</strong> {safe_ticket}</p>
      <p style="margin:0 0 8px;"><strong style="color:#0F3D3E;">Topic:</strong> {safe_subject}</p>
      {order_block}
      <div style="margin:0 0 8px;padding:16px;background:#F3F7F7;border-radius:10px;border:1px solid #E5E7EB;">
        <p style="margin:0 0 8px;font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.08em;font-weight:700;">Your message</p>
        <p style="margin:0;color:#111827;">{safe_message}</p>
      </div>
      <p style="margin:16px 0 0;color:#334155;font-size:14px;line-height:1.55;">
        Reply to this email to add details — keep <strong>[{safe_ticket}]</strong> in the subject
        so your message stays on this thread. You may also get a quick automatic reply with
        order status and self-serve links.
      </p>
    """
    html_body = wrap_branded_email(
        eyebrow="Support",
        title=config["received_title"],
        body_html=body,
        app_url=settings.app_url,
        tip=config["received_tip"],
    )
    email_subject = f"[{ticket_id}] {subject or config['label']}"
    if len(email_subject) > 240:
        email_subject = f"[{ticket_id}] {config['label']} — NoorLink"
    return send_email(
        to_email=to_email,
        subject=email_subject,
        html_body=html_body,
        reply_to=settings.support_email,
    )


def send_staff_new_ticket_alert(
    *,
    ticket_id: str,
    name: str,
    customer_email: str,
    subject: Optional[str],
    message: str,
    order_number: Optional[str] = None,
    category: Optional[str] = None,
    auto_result: Optional[Dict[str, Any]] = None,
) -> None:
    """Notify support staff that a new ticket arrived (or was auto-handled)."""
    recipients = _staff_notify_addresses()
    if not recipients:
        return

    settings = get_settings()
    slug = category or normalize_support_category(subject)
    config = get_category_config(slug)
    safe_message = html.escape(message.strip()).replace("\n", "<br/>")
    order_line = ""
    if order_number:
        order_line = f"<p style=\"margin:0 0 12px;\"><strong>Order:</strong> {html.escape(str(order_number))}</p>"

    auto_line = ""
    if auto_result:
        intent = html.escape(str(auto_result.get("intent") or ""))
        if auto_result.get("auto_resolved"):
            auto_line = (
                f'<p style="margin:0 0 12px;color:#047857;"><strong>Auto-handled</strong> '
                f"(intent: {intent}"
                + (", QR resent" if auto_result.get("qr_resent") else "")
                + "). Ticket closed — review only if the customer replies.</p>"
            )
        elif auto_result.get("needs_human"):
            auto_line = (
                f'<p style="margin:0 0 12px;color:#B45309;"><strong>Needs human</strong> '
                f"(intent: {intent}). Auto-reply sent with self-serve links.</p>"
            )
        else:
            auto_line = (
                f'<p style="margin:0 0 12px;"><strong>Auto-reply sent</strong> '
                f"(intent: {intent}). Ticket waiting on customer.</p>"
            )

    body = f"""
      <p style="margin:0 0 16px;">New support ticket <strong>{html.escape(ticket_id)}</strong>.</p>
      {auto_line}
      <p style="margin:0 0 8px;"><strong>Topic:</strong> {html.escape(config['label'])}</p>
      <p style="margin:0 0 8px;"><strong>Customer:</strong> {html.escape(name)} &lt;{html.escape(customer_email)}&gt;</p>
      {order_line}
      <div style="margin:0 0 16px;padding:16px;background:#F3F7F7;border-radius:10px;border:1px solid #E5E7EB;">
        <p style="margin:0;color:#111827;line-height:1.6;">{safe_message}</p>
      </div>
      <p style="margin:0;color:#334155;font-size:14px;">
        Open Support Inbox in admin if you need to take over.
      </p>
    """
    title_prefix = "New ticket"
    if auto_result and auto_result.get("auto_resolved"):
        title_prefix = "Auto-handled"
    elif auto_result and auto_result.get("needs_human"):
        title_prefix = "Needs human"
    html_body = wrap_branded_email(
        eyebrow=title_prefix,
        title=f"{config['label']} — {ticket_id}",
        body_html=body,
        app_url=settings.app_url,
        tip="Auto-replies cover QR/install/order status; refunds always need a person.",
    )
    email_subject = f"[Staff] {title_prefix} {ticket_id} — {config['label']}"
    for addr in recipients:
        try:
            send_email(to_email=addr, subject=email_subject, html_body=html_body)
        except EmailDeliveryError:
            logger.exception("Staff new-ticket alert failed for %s", addr)


def send_customer_ticket_assigned(
    *,
    to_email: str,
    name: str,
    ticket_id: str,
    assignee_display_name: str,
    subject: Optional[str],
    category: Optional[str] = None,
    order_number: Optional[str] = None,
) -> str:
    """Tell the customer their ticket was assigned to a team member."""
    settings = get_settings()
    slug = category or normalize_support_category(subject)
    config = get_category_config(slug)
    order_line = ""
    if order_number:
        order_line = f"<p style=\"margin:0 0 12px;\">Order: <strong>{html.escape(order_number)}</strong></p>"

    body = f"""
      <p style="margin:0 0 16px;">Hi {html.escape(name.strip() or 'there')},</p>
      <p style="margin:0 0 16px;">{html.escape(config['assigned_customer_intro'])}</p>
      <p style="margin:0 0 16px;">
        <strong style="color:#0F3D3E;">{html.escape(assignee_display_name)}</strong>
        is handling ticket <strong>{html.escape(ticket_id)}</strong>
        ({html.escape(category_label(slug))}).
      </p>
      {order_line}
      <p style="margin:0;color:#6B7280;font-size:13px;">
        Reply to this email if you have more details — we typically respond within 24 hours.
      </p>
    """
    html_body = wrap_branded_email(
        eyebrow="Support",
        title="Your ticket has been assigned",
        body_html=body,
        app_url=settings.app_url,
        tip=config["received_tip"],
    )
    email_subject = f"[{ticket_id}] Assigned — {subject or config['label']}"
    return send_email(
        to_email=to_email,
        subject=email_subject,
        html_body=html_body,
        reply_to=settings.support_email,
    )


def send_staff_ticket_assigned(
    *,
    to_email: str,
    ticket_id: str,
    customer_name: str,
    customer_email: str,
    subject: Optional[str],
    category: Optional[str] = None,
    order_number: Optional[str] = None,
) -> str:
    """Tell a staff member they were assigned a ticket."""
    settings = get_settings()
    slug = category or normalize_support_category(subject)
    config = get_category_config(slug)
    order_line = ""
    if order_number:
        order_line = f"<p style=\"margin:0 0 12px;\"><strong>Order:</strong> {html.escape(order_number)}</p>"

    body = f"""
      <p style="margin:0 0 16px;">You were assigned ticket <strong>{html.escape(ticket_id)}</strong>.</p>
      <p style="margin:0 0 8px;"><strong>Topic:</strong> {html.escape(config['label'])}</p>
      <p style="margin:0 0 8px;"><strong>Customer:</strong> {html.escape(customer_name)} &lt;{html.escape(customer_email)}&gt;</p>
      {order_line}
      <p style="margin:0;color:#334155;font-size:14px;">
        Open Support Inbox in admin to reply with a branded message or a topic template.
      </p>
    """
    html_body = wrap_branded_email(
        eyebrow="Assignment",
        title=f"{ticket_id} — {config['label']}",
        body_html=body,
        app_url=settings.app_url,
        tip="Use the quick templates for install, payment, and refund cases.",
    )
    email_subject = f"[Assigned] {ticket_id} — {config['label']}"
    return send_email(to_email=to_email, subject=email_subject, html_body=html_body)


def dispatch_ticket_created_notifications(
    *,
    ticket_id: str,
    name: str,
    email: str,
    subject: Optional[str],
    message: str,
    order_number: Optional[str] = None,
    category: Optional[str] = None,
    run_auto_reply: bool = True,
) -> str:
    """Customer confirmation + optional auto-reply + staff alert. Returns Resend id for customer email."""
    slug = category or normalize_support_category(subject)
    customer_id = send_customer_ticket_received(
        to_email=email,
        name=name,
        ticket_id=ticket_id,
        subject=subject,
        message=message,
        order_number=order_number,
        category=slug,
    )

    auto_result: Optional[Dict[str, Any]] = None
    if run_auto_reply:
        try:
            from app.services.support_auto_reply import run_support_auto_reply

            auto_result = run_support_auto_reply(
                ticket_number=ticket_id,
                name=name,
                email=email,
                subject=subject,
                message=message,
                order_number=order_number,
                category=slug,
            )
        except Exception:
            logger.exception("Support auto-reply failed for %s", ticket_id)
            auto_result = {"sent": False, "needs_human": True, "auto_resolved": False}

    try:
        send_staff_new_ticket_alert(
            ticket_id=ticket_id,
            name=name,
            customer_email=email,
            subject=subject,
            message=message,
            order_number=(auto_result or {}).get("order_number") or order_number,
            category=slug,
            auto_result=auto_result,
        )
    except EmailDeliveryError:
        logger.exception("Staff alert failed for ticket %s", ticket_id)

    if auto_result and auto_result.get("needs_human") and not auto_result.get("auto_resolved"):
        try:
            from app.services.ops_alerts import notify_staff_governance

            notify_staff_governance(
                title=f"Support needs human — {ticket_id}",
                summary=f"{name} <{email}> — intent {auto_result.get('intent')}",
                details={
                    "ticket": ticket_id,
                    "order": auto_result.get("order_number") or order_number or "—",
                    "category": slug,
                },
            )
        except Exception:
            logger.exception("Ops needs-human alert failed for %s", ticket_id)

    return customer_id
