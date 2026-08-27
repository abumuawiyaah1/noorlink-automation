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
    review_request_block,
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
    bcc: Optional[list[str]] = None,
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
    bcc_list = [addr.strip() for addr in (bcc or []) if addr and addr.strip()]
    if bcc_list:
        payload["bcc"] = bcc_list

    try:
        response = resend.Emails.send(payload)
    except TypeError:
        # Older SDK may not accept reply_to / bcc
        payload.pop("reply_to", None)
        if "bcc" in payload:
            payload.pop("bcc", None)
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

    logger.info(
        "Email sent to %s (id=%s subject=%s bcc=%s)",
        to_email,
        message_id,
        subject,
        len(bcc_list),
    )
    return message_id


def _regional_email_context(country: str) -> Dict[str, Any]:
    """Build optional regional copy blocks for transactional emails."""
    from app.api.regional_inventory import (
        get_regional_product,
        resolve_regional_product_by_display_name,
    )

    product_id = resolve_regional_product_by_display_name(country)
    if not product_id:
        return {"is_regional": False}

    product = get_regional_product(product_id) or {}
    countries = product.get("countries") or []
    exclusions = product.get("exclusions") or []
    countries_line = " · ".join(countries[:12])
    if len(countries) > 12:
        countries_line += f" · +{len(countries) - 12} more"

    return {
        "is_regional": True,
        "display_name": product.get("display_name") or country,
        "countries": countries,
        "exclusions": exclusions,
        "countries_line": countries_line,
        "coverage_count": len(countries),
    }


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
    regional = _regional_email_context(country)
    regional_block = ""
    if regional.get("is_regional"):
        exclusions = regional.get("exclusions") or []
        exclusion_line = ""
        if exclusions:
            exclusion_line = (
                f"<p style=\"margin:0 0 16px;font-size:13px;color:{MUTED};\">"
                f"Not included on this plan: {html.escape(', '.join(exclusions))}."
                f"</p>"
            )
        regional_block = f"""
      <p style="margin:0 0 16px;">
        This is a <strong>multi-country</strong> plan covering
        <strong>{regional.get('coverage_count', 0)} countries</strong>.
        Install once — use data in any covered country without buying a new plan
        at each border.
      </p>
      <p style="margin:0 0 16px;font-size:14px;color:{PRIMARY};">
        {html.escape(str(regional.get('countries_line') or ''))}
      </p>
      {exclusion_line}"""
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
      {regional_block}
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
    regional = _regional_email_context(country)
    regional_intro = ""
    coverage_block = ""
    if regional.get("is_regional"):
        regional_intro = """
      <p style="margin:0 0 16px;">
        Install once — when you land in any covered country, turn on this line
        for mobile data. You do not need a new plan when you cross borders within
        this list.
      </p>"""
        exclusions = regional.get("exclusions") or []
        exclusion_html = ""
        if exclusions:
            exclusion_html = (
                f"<p style=\"margin:12px 0 0;font-size:13px;color:{MUTED};\">"
                f"Not included: {html.escape(', '.join(exclusions))}."
                f"</p>"
            )
        countries = regional.get("countries") or []
        country_items = "".join(
            f"<li style='margin-bottom:4px;color:{PRIMARY};'>{html.escape(c)}</li>"
            for c in countries
        )
        coverage_block = f"""
      <h3 style="color:{PRIMARY};font-size:15px;margin:24px 0 10px;">Countries covered</h3>
      <ul style="padding-left:20px;margin:0 0 8px;columns:2;column-gap:24px;">{country_items}</ul>
      {exclusion_html}"""

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
    from app.core.config import get_settings

    settings = get_settings()
    review_block = review_request_block(
        app_url=app_url,
        order_number=order_number,
        trustpilot_review_url=(settings.trustpilot_review_url or "").strip() or None,
        google_review_url=(settings.google_review_url or "").strip() or None,
    )

    body = f"""
      <p style="margin:0 0 20px;">
        Thank you for your order <strong style="color:{PRIMARY};">{html.escape(order_number)}</strong>.
        Your <em>{html.escape(package_name)}</em> plan is provisioned and ready to install.
      </p>
      {regional_intro}

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
      {coverage_block}

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
      {review_block}
    """
    return wrap_branded_email(
        eyebrow="eSIM delivered",
        title=f"{flag} Your {html.escape(country)} eSIM is ready".strip(),
        body_html=body,
        app_url=app_url,
        tip="Install on Wi‑Fi before travel. After landing, turn on Data Roaming for the NoorLink line and set it as your Mobile Data SIM."
        if not regional.get("is_regional")
        else "Regional plan: your data allowance is shared across the whole trip. Install on Wi‑Fi before you fly.",
    )


def send_fulfillment_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
) -> str:
    """Deliver eSIM QR email; BCC Trustpilot invite address when configured (AFS)."""
    settings = get_settings()
    bcc: list[str] = []
    invite = (settings.trustpilot_invite_bcc or "").strip()
    if invite:
        bcc.append(invite)
    return send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        bcc=bcc or None,
    )


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


def build_insider_issue_email_html(
    *,
    subject: str,
    preview: str,
    hero_image_url: str,
    web_path: str,
    promo_code: Optional[str],
    promo_percent: Optional[int],
    promo_ends: Optional[str],
    app_url: str,
    unsubscribe_url: Optional[str] = None,
) -> str:
    issue_url = f"{app_url.rstrip('/')}{web_path}"
    promo_block = ""
    if promo_code and promo_percent:
        ends_line = ""
        if promo_ends:
            ends_line = f"<p style=\"margin:8px 0 0;font-size:13px;color:rgba(255,255,255,0.75);\">Ends {html.escape(promo_ends[:10])} — code turns off automatically after.</p>"
        deal_href = f"{app_url.rstrip('/')}/destinations?promo={html.escape(promo_code)}"
        promo_block = f"""
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;background:#05191A;border-radius:12px;">
        <tr><td style="padding:20px 22px;text-align:center;">
          <p style="margin:0 0 8px;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:{ACCENT};font-weight:700;">Insider deal</p>
          <p style="margin:0;font-family:ui-monospace,Menlo,monospace;font-size:24px;font-weight:800;color:{ACCENT};">{html.escape(promo_code)}</p>
          <p style="margin:8px 0 0;font-size:15px;color:#fff;">{promo_percent}% off at checkout</p>
          {ends_line}
          <p style="margin:16px 0 0;">{cta_button(href=deal_href, label=f"Use {promo_code}")}</p>
        </td></tr>
      </table>"""

    hero_block = ""
    if hero_image_url:
        hero_block = f"""
      <img src="{html.escape(hero_image_url)}" alt="" width="536" style="display:block;width:100%;max-width:536px;height:auto;border-radius:12px;margin:0 0 20px;"/>
    """

    unsub_block = ""
    if unsubscribe_url:
        unsub_block = f"""
      <p style="margin:28px 0 0;font-size:12px;color:{MUTED};text-align:center;">
        <a href="{html.escape(unsubscribe_url)}" style="color:{MUTED};text-decoration:underline;">Unsubscribe</a>
        from NoorLink Insider anytime.
      </p>
    """

    body = f"""
      {hero_block}
      <p style="margin:0 0 16px;font-size:16px;line-height:1.65;">{html.escape(preview)}</p>
      {promo_block}
      <p style="text-align:center;margin:28px 0 0;">
        {cta_button(href=issue_url, label="Read this issue")}
      </p>
      <p style="margin:20px 0 0;font-size:13px;color:{MUTED};text-align:center;">
        Travel tips, destination guides, and calm connectivity advice — once a month.
      </p>
      {unsub_block}
    """
    return wrap_branded_email(
        eyebrow="NoorLink Insider",
        title=html.escape(subject),
        body_html=body,
        app_url=app_url,
        tip="Install your eSIM on Wi‑Fi before you fly — it saves stress at the airport.",
    )


def send_insider_issue_email(
    *,
    to_email: str,
    subject: str,
    preview: str,
    hero_image_url: str,
    web_path: str,
    promo_code: Optional[str] = None,
    promo_percent: Optional[int] = None,
    promo_ends: Optional[str] = None,
) -> str:
    from urllib.parse import quote

    settings = get_settings()
    unsubscribe_url = (
        f"{settings.app_url.rstrip('/')}/unsubscribe?email={quote(to_email.strip().lower())}"
    )
    html_body = build_insider_issue_email_html(
        subject=subject,
        preview=preview,
        hero_image_url=hero_image_url,
        web_path=web_path,
        promo_code=promo_code,
        promo_percent=promo_percent,
        promo_ends=promo_ends,
        app_url=settings.app_url,
        unsubscribe_url=unsubscribe_url,
    )
    email_subject = f"NoorLink Insider — {subject}"
    return send_email(to_email=to_email, subject=email_subject, html_body=html_body)
