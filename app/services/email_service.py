"""Resend transactional email delivery."""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, Optional

import resend

from app.core.config import get_settings
from app.services.email_brand import (
    ACCENT,
    BG,
    MUTED,
    PRIMARY,
    cta_button,
    wrap_branded_email,
)

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when Resend fails to send."""


def _configure_resend() -> None:
    settings = get_settings()
    resend.api_key = settings.resend_api_key


def _html_to_text(html_body: str) -> str:
    text = (
        html_body.replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
        .replace("</p>", "\n\n")
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def send_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> str:
    """Send a transactional email via Resend. Returns provider message id."""
    settings = get_settings()
    _configure_resend()
    if not (settings.resend_api_key or "").strip():
        raise EmailDeliveryError("RESEND_API_KEY is not configured")
    if not (settings.resend_from_email or "").strip():
        raise EmailDeliveryError("RESEND_FROM_EMAIL is not configured")

    # Plain-text twin improves inbox placement vs HTML-only messages.
    if text_body is None:
        text_body = _html_to_text(html_body)

    payload: Dict[str, Any] = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
        "reply_to": "support@noorlink.co",
    }

    try:
        response = resend.Emails.send(payload)
    except TypeError:
        # Older SDK may not accept reply_to
        payload.pop("reply_to", None)
        try:
            response = resend.Emails.send(payload)
        except Exception as exc:
            logger.exception("Resend delivery failed for %s", to_email)
            raise EmailDeliveryError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Resend delivery failed for %s", to_email)
        raise EmailDeliveryError(str(exc)) from exc

    message_id = ""
    if isinstance(response, dict):
        # Newer SDKs may return {"id": "..."} or {"data": {"id": "..."}}
        message_id = str(
            response.get("id")
            or (response.get("data") or {}).get("id")
            or ""
        )
        if response.get("error"):
            raise EmailDeliveryError(str(response["error"]))
    else:
        message_id = str(getattr(response, "id", "") or response)

    if not message_id:
        raise EmailDeliveryError(
            f"Resend returned no message id (response={response!r})"
        )

    logger.info("Email sent to %s (id=%s subject=%s)", to_email, message_id, subject)
    return message_id


def build_checkout_ack_email_html(
    *,
    order_number: str,
    country: str,
    package_name: str,
    amount: float,
    currency: str,
    flag_emoji: Optional[str],
    checkout_url: Optional[str],
    app_url: str,
) -> str:
    flag = flag_emoji or ""
    amount_label = f"{currency.upper()} {amount:.2f}"
    pay_block = ""
    if checkout_url:
        pay_block = f"""
            <p style="text-align:center;margin:24px 0;">
              {cta_button(href=checkout_url, label="Complete payment")}
            </p>"""

    body = f"""
      <p style="margin:0 0 16px;color:{PRIMARY};">
        Thanks for choosing NoorLink. We saved your details for order
        <strong>{html.escape(order_number)}</strong>
        ({html.escape(package_name)} · {html.escape(country)} · {html.escape(amount_label)}).
      </p>
      <p style="margin:0 0 16px;">
        Complete payment on Stripe to activate delivery. Your eSIM QR code and
        install instructions will arrive in a second email right after payment clears.
      </p>
      {pay_block}
      <p style="margin:24px 0 0;font-size:13px;color:{MUTED};">
        If you did not start this checkout, you can ignore this message.
      </p>
    """
    return wrap_branded_email(
        eyebrow="Checkout",
        title=f"{flag} We received your order details".strip(),
        body_html=body,
        app_url=app_url,
        tip="Keep this email handy — after payment, install your eSIM on Wi‑Fi before you fly.",
    )


def build_fulfillment_email_html(
    *,
    order_number: str,
    country: str,
    package_name: str,
    flag_emoji: Optional[str],
    qr_code_url: str,
    activation_code: str,
    travel_guide: Dict[str, Any],
    app_url: str,
) -> str:
    flag = flag_emoji or ""
    itinerary_rows = ""
    for item in travel_guide.get("itinerary") or []:
        itinerary_rows += f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #E5E7EB;color:{MUTED};font-size:13px;">
            {html.escape(str(item.get('day', '')))}
          </td>
          <td style="padding:12px 0;border-bottom:1px solid #E5E7EB;">
            <strong style="color:{PRIMARY};">{html.escape(str(item.get('title', '')))}</strong><br/>
            <span style="color:{PRIMARY};font-size:14px;">{html.escape(str(item.get('detail', '')))}</span>
          </td>
        </tr>"""

    maps_items = ""
    for place in travel_guide.get("maps") or []:
        label = html.escape(str(place.get("label", "Map")))
        url = html.escape(str(place.get("url", "#")))
        maps_items += f"""
        <li style="margin-bottom:8px;">
          <a href="{url}" style="color:{PRIMARY};text-decoration:none;font-weight:700;">{label}</a>
        </li>"""

    highlights = "".join(
        f"<li style='margin-bottom:6px;color:{PRIMARY};'>{html.escape(str(h))}</li>"
        for h in (travel_guide.get("highlights") or [])
    )

    dashboard_url = f"{app_url.rstrip('/')}/dashboard?orderId={html.escape(order_number)}"

    body = f"""
      <p style="margin:0 0 20px;">
        Thank you for your order <strong style="color:{PRIMARY};">{html.escape(order_number)}</strong>.
        Your <em>{html.escape(package_name)}</em> plan is provisioned and ready to install.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};border-radius:12px;margin-bottom:28px;border:1px solid #E5E7EB;">
        <tr><td style="padding:24px;text-align:center;">
          <p style="margin:0 0 12px;color:{PRIMARY};font-size:13px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;">
            Scan to install
          </p>
          <img src="{html.escape(qr_code_url)}" alt="eSIM QR Code" width="200" height="200" style="border-radius:8px;border:3px solid {ACCENT};"/>
          <p style="margin:16px 0 0;font-family:ui-monospace,Menlo,monospace;font-size:15px;color:{PRIMARY};letter-spacing:1px;">
            {html.escape(activation_code)}
          </p>
        </td></tr>
      </table>

      <h2 style="margin:0 0 12px;color:{PRIMARY};font-size:18px;font-weight:700;border-bottom:3px solid {ACCENT};padding-bottom:8px;display:inline-block;">
        Your travel assistant
      </h2>
      <ul style="padding-left:20px;margin:12px 0 20px;">{highlights}</ul>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
        {itinerary_rows}
      </table>

      <h3 style="color:{PRIMARY};font-size:15px;margin:0 0 10px;">Explore on Google Maps</h3>
      <ul style="padding-left:20px;margin:0 0 28px;">{maps_items}</ul>

      <p style="text-align:center;margin:0;">
        {cta_button(href=dashboard_url, label="View order in dashboard")}
      </p>
    """
    return wrap_branded_email(
        eyebrow="eSIM delivered",
        title=f"{flag} Your {html.escape(country)} eSIM is ready".strip(),
        body_html=body,
        app_url=app_url,
        tip="Install on Wi‑Fi before travel. After landing, turn on Data Roaming for the NoorLink line and set it as your Mobile Data SIM.",
    )


def send_fulfillment_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
) -> str:
    return send_email(to_email=to_email, subject=subject, html_body=html_body)


def build_support_ticket_email_html(
    *,
    name: str,
    ticket_id: str,
    subject: Optional[str],
    message: str,
    app_url: str,
) -> str:
    safe_name = html.escape(name.strip() or "there")
    safe_ticket = html.escape(ticket_id)
    safe_subject = html.escape((subject or "Support request").strip())
    safe_message = html.escape(message.strip()).replace("\n", "<br/>")

    body = f"""
      <p style="margin:0 0 16px;">Hi {safe_name},</p>
      <p style="margin:0 0 16px;">
        Your support ticket has been created. Our team typically replies within 24 hours.
      </p>
      <p style="margin:0 0 8px;"><strong style="color:{PRIMARY};">Ticket ID:</strong> {safe_ticket}</p>
      <p style="margin:0 0 16px;"><strong style="color:{PRIMARY};">Subject:</strong> {safe_subject}</p>
      <div style="margin:0 0 8px;padding:16px;background:{BG};border-radius:10px;border:1px solid #E5E7EB;">
        <p style="margin:0 0 8px;font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:0.08em;font-weight:700;">Your message</p>
        <p style="margin:0;">{safe_message}</p>
      </div>
    """
    return wrap_branded_email(
        eyebrow="Support",
        title="We received your message",
        body_html=body,
        app_url=app_url,
        tip="Include your ticket ID in any follow-up — it helps us find your case faster.",
    )


def send_support_ticket_confirmation(
    *,
    to_email: str,
    name: str,
    ticket_id: str,
    subject: Optional[str],
    message: str,
) -> str:
    settings = get_settings()
    email_subject = f"Support ticket {ticket_id} created — NoorLink"
    html_body = build_support_ticket_email_html(
        name=name,
        ticket_id=ticket_id,
        subject=subject,
        message=message,
        app_url=settings.app_url,
    )
    return send_email(to_email=to_email, subject=email_subject, html_body=html_body)


def send_checkout_acknowledgment(
    *,
    to_email: str,
    order_number: str,
    country: str,
    package_name: str,
    amount: float,
    currency: str = "USD",
    flag_emoji: Optional[str] = None,
    checkout_url: Optional[str] = None,
) -> str:
    settings = get_settings()
    subject = f"Order {order_number} received — complete payment for your {country} eSIM"
    html_body = build_checkout_ack_email_html(
        order_number=order_number,
        country=country,
        package_name=package_name,
        amount=amount,
        currency=currency,
        flag_emoji=flag_emoji,
        checkout_url=checkout_url,
        app_url=settings.app_url,
    )
    return send_email(to_email=to_email, subject=subject, html_body=html_body)
