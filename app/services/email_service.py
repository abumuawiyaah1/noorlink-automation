"""Resend transactional email delivery."""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional

import resend

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when Resend fails to send."""


def _configure_resend() -> None:
    settings = get_settings()
    resend.api_key = settings.resend_api_key


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
          <td style="padding:12px 0;border-bottom:1px solid #e8e4dc;color:#6b6560;font-size:13px;">
            {html.escape(str(item.get('day', '')))}
          </td>
          <td style="padding:12px 0;border-bottom:1px solid #e8e4dc;">
            <strong style="color:#1a3a2f;">{html.escape(str(item.get('title', '')))}</strong><br/>
            <span style="color:#4a4540;font-size:14px;">{html.escape(str(item.get('detail', '')))}</span>
          </td>
        </tr>"""

    maps_items = ""
    for place in travel_guide.get("maps") or []:
        label = html.escape(str(place.get("label", "Map")))
        url = html.escape(str(place.get("url", "#")))
        maps_items += f"""
        <li style="margin-bottom:8px;">
          <a href="{url}" style="color:#0d6b4d;text-decoration:none;font-weight:600;">{label}</a>
        </li>"""

    highlights = "".join(
        f"<li style='margin-bottom:6px;color:#4a4540;'>{html.escape(str(h))}</li>"
        for h in (travel_guide.get("highlights") or [])
    )

    dashboard_url = f"{app_url.rstrip('/')}/dashboard?orderId={html.escape(order_number)}"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width"/></head>
<body style="margin:0;padding:0;background:#f6f3ed;font-family:Georgia,'Times New Roman',serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f6f3ed;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(26,58,47,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a3a2f 0%,#0d6b4d 100%);padding:32px 40px;">
            <p style="margin:0;color:#c5e8d8;font-size:13px;letter-spacing:2px;text-transform:uppercase;">NoorLink</p>
            <h1 style="margin:8px 0 0;color:#ffffff;font-size:28px;font-weight:normal;">
              {flag} Your {html.escape(country)} eSIM is ready
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:40px;">
            <p style="color:#4a4540;font-size:16px;line-height:1.6;margin:0 0 24px;">
              Thank you for your order <strong style="color:#1a3a2f;">{html.escape(order_number)}</strong>.
              Your <em>{html.escape(package_name)}</em> plan is provisioned and ready to install.
            </p>

            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0faf5;border-radius:8px;margin-bottom:32px;">
              <tr><td style="padding:24px;text-align:center;">
                <p style="margin:0 0 12px;color:#1a3a2f;font-size:14px;font-weight:bold;">Scan to install</p>
                <img src="{html.escape(qr_code_url)}" alt="eSIM QR Code" width="200" height="200" style="border-radius:8px;"/>
                <p style="margin:16px 0 0;font-family:monospace;font-size:15px;color:#0d6b4d;letter-spacing:1px;">
                  {html.escape(activation_code)}
                </p>
              </td></tr>
            </table>

            <h2 style="color:#1a3a2f;font-size:20px;font-weight:normal;border-bottom:2px solid #c5e8d8;padding-bottom:8px;">
              Your travel assistant
            </h2>
            <ul style="padding-left:20px;margin:16px 0 24px;">{highlights}</ul>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
              {itinerary_rows}
            </table>

            <h3 style="color:#1a3a2f;font-size:16px;margin:0 0 12px;">Explore on Google Maps</h3>
            <ul style="padding-left:20px;margin:0 0 32px;">{maps_items}</ul>

            <p style="text-align:center;margin:0;">
              <a href="{dashboard_url}" style="display:inline-block;background:#1a3a2f;color:#ffffff;padding:14px 32px;border-radius:6px;text-decoration:none;font-size:15px;">
                View order in dashboard
              </a>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 40px;background:#f6f3ed;text-align:center;">
            <p style="margin:0;color:#6b6560;font-size:12px;">
              Need help? Reply to this email or visit our support page.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_fulfillment_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
) -> str:
    settings = get_settings()
    _configure_resend()
    try:
        response = resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            }
        )
    except Exception as exc:
        logger.exception("Resend delivery failed for %s", to_email)
        raise EmailDeliveryError(str(exc)) from exc

    message_id = ""
    if isinstance(response, dict):
        message_id = str(response.get("id") or "")
    else:
        message_id = str(getattr(response, "id", "") or response)
    logger.info("Fulfillment email sent to %s (id=%s)", to_email, message_id)
    return message_id
