"""Operational alerts when paid orders fail fulfillment (no QR delivered)."""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger(__name__)


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


def notify_fulfillment_failure(
    *,
    order_number: str,
    email: str,
    country: str,
    package_name: str,
    error: str,
    context: Optional[str] = None,
    order_status: Optional[str] = None,
) -> None:
    """
    Best-effort Slack + email alert. Never raises — fulfillment path must not fail twice.
    Configure OPS_ALERT_EMAIL and/or SLACK_WEBHOOK_URL on Railway.
    """
    settings = get_settings()
    slack_url = (settings.slack_webhook_url or "").strip()
    ops_email = (settings.ops_alert_email or "").strip()

    if not slack_url and not ops_email:
        logger.warning(
            "Fulfillment failed for %s but no OPS_ALERT_EMAIL or SLACK_WEBHOOK_URL configured",
            order_number,
        )
        return

    subject = f"[NoorLink] Fulfillment failed — {order_number}"
    lines = [
        f"Order: {_escape(order_number)}",
        f"Customer: {_escape(email)}",
        f"Destination: {_escape(country)}",
        f"Plan: {_escape(package_name)}",
        f"Status: {_escape(order_status or 'paid')}",
        f"Error: {_escape(error)}",
    ]
    if context:
        lines.append(f"Context: {_escape(context)}")

    text_body = "\n".join(lines)
    html_body = (
        "<h2>Fulfillment failure — action required</h2>"
        "<p>Stripe payment succeeded but eSIM delivery did not complete.</p>"
        "<ul>"
        f"<li><strong>Order:</strong> {_escape(order_number)}</li>"
        f"<li><strong>Customer:</strong> {_escape(email)}</li>"
        f"<li><strong>Destination:</strong> {_escape(country)}</li>"
        f"<li><strong>Plan:</strong> {_escape(package_name)}</li>"
        f"<li><strong>Status:</strong> {_escape(order_status or 'paid')}</li>"
        f"<li><strong>Error:</strong> {_escape(error)}</li>"
        + (f"<li><strong>Context:</strong> {_escape(context)}</li>" if context else "")
        + "</ul>"
        "<p>Customer may be waiting on QR email. Check Railway logs and run "
        "<code>python scripts/fulfill_order.py</code> if needed.</p>"
    )

    if ops_email:
        try:
            send_email(
                to_email=ops_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except EmailDeliveryError as exc:
            logger.error("Ops alert email failed for %s: %s", order_number, exc)

    if slack_url:
        try:
            payload = {
                "text": subject,
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "Fulfillment failed"},
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Order:* `{order_number}`\n"
                                f"*Customer:* {email}\n"
                                f"*Plan:* {package_name} ({country})\n"
                                f"*Error:* {error}"
                            ),
                        },
                    },
                ],
            }
            with httpx.Client(timeout=10.0) as client:
                response = client.post(slack_url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.error("Slack ops alert failed for %s: %s", order_number, exc)
