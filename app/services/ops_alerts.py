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


def notify_security_threat(
    *,
    title: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Best-effort Slack + email for external security signals.
    Never raises — auth/API paths must not fail because alerting failed.
    """
    settings = get_settings()
    slack_url = (settings.slack_webhook_url or "").strip()
    ops_email = (settings.ops_alert_email or "").strip()

    if not slack_url and not ops_email:
        logger.warning("Security alert not sent (no OPS_ALERT_EMAIL or SLACK_WEBHOOK_URL): %s", title)
        return

    subject = f"[NoorLink Security] {title}"
    detail_lines = []
    if details:
        for key, value in details.items():
            detail_lines.append(f"{key}: {_escape(value)}")
    text_body = summary + ("\n" + "\n".join(detail_lines) if detail_lines else "")

    html_items = "".join(
        f"<li><strong>{_escape(key)}:</strong> {_escape(value)}</li>"
        for key, value in (details or {}).items()
    )
    html_body = (
        f"<h2>{_escape(title)}</h2>"
        f"<p>{_escape(summary)}</p>"
        + (f"<ul>{html_items}</ul>" if html_items else "")
        + "<p>Review <a href=\"https://api.noorlink.co/admin/operations\">Operations → Security</a> "
        "or filter Event log by <code>security_</code>.</p>"
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
            logger.error("Security alert email failed: %s", exc)

    if slack_url:
        try:
            mrkdwn_lines = [f"*{title}*", summary]
            if details:
                mrkdwn_lines.extend(f"*{k}:* `{v}`" for k, v in details.items())
            payload = {
                "text": subject,
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "Security alert"},
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "\n".join(mrkdwn_lines)},
                    },
                ],
            }
            with httpx.Client(timeout=10.0) as client:
                response = client.post(slack_url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.error("Slack security alert failed: %s", exc)


def notify_email_complaint(
    *,
    recipient: str,
    subject: Optional[str] = None,
    resend_event: Optional[str] = None,
) -> None:
    """Alert ops when a recipient marks NoorLink email as spam (Resend email.complained)."""
    settings = get_settings()
    slack_url = (settings.slack_webhook_url or "").strip()
    ops_email = (settings.ops_alert_email or "").strip()

    if not slack_url and not ops_email:
        logger.warning("Email complaint from %s but no OPS_ALERT_EMAIL or SLACK_WEBHOOK_URL", recipient)
        return

    title = "Email spam complaint"
    summary = f"{recipient} marked a NoorLink email as spam. Review Resend suppressions and newsletter list."
    details = {
        "recipient": recipient,
        "subject": subject or "(unknown)",
        "resend_event": resend_event or "email.complained",
    }

    subject_line = f"[NoorLink] Spam complaint — {recipient}"
    text_body = summary + "\n" + "\n".join(f"{k}: {v}" for k, v in details.items())
    html_items = "".join(
        f"<li><strong>{_escape(k)}:</strong> {_escape(v)}</li>" for k, v in details.items()
    )
    html_body = (
        f"<h2>{_escape(title)}</h2>"
        f"<p>{_escape(summary)}</p>"
        f"<ul>{html_items}</ul>"
        "<p>Check Resend dashboard → Suppressions. Complainer was auto-unsubscribed from newsletter if applicable.</p>"
    )

    if ops_email:
        try:
            send_email(
                to_email=ops_email,
                subject=subject_line,
                html_body=html_body,
                text_body=text_body,
            )
        except EmailDeliveryError as exc:
            logger.error("Complaint alert email failed: %s", exc)

    if slack_url:
        try:
            payload = {
                "text": subject_line,
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "Email spam complaint"}},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Recipient:* `{recipient}`\n"
                                f"*Subject:* {subject or 'unknown'}\n"
                                f"*Action:* Review suppressions; customer may need a personal reply."
                            ),
                        },
                    },
                ],
            }
            with httpx.Client(timeout=10.0) as client:
                response = client.post(slack_url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.error("Slack complaint alert failed: %s", exc)


def notify_staff_governance(
    *,
    title: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Alert when staff accounts are created, roles change, or accounts are deactivated."""
    settings = get_settings()
    slack_url = (settings.slack_webhook_url or "").strip()
    ops_email = (settings.ops_alert_email or "").strip()

    if not slack_url and not ops_email:
        logger.warning("Staff governance alert not sent (no alert channel): %s", title)
        return

    subject = f"[NoorLink Security] {title}"
    detail_lines = []
    if details:
        for key, value in details.items():
            detail_lines.append(f"{key}: {_escape(value)}")
    text_body = summary + ("\n" + "\n".join(detail_lines) if detail_lines else "")
    html_items = "".join(
        f"<li><strong>{_escape(key)}:</strong> {_escape(value)}</li>"
        for key, value in (details or {}).items()
    )
    html_body = (
        f"<h2>{_escape(title)}</h2>"
        f"<p>{_escape(summary)}</p>"
        + (f"<ul>{html_items}</ul>" if html_items else "")
        + "<p>If unexpected, run <code>scripts/recover_owner.py</code> on Railway and deactivate the rogue account.</p>"
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
            logger.error("Staff governance alert email failed: %s", exc)

    if slack_url:
        try:
            mrkdwn_lines = [f"*{title}*", summary]
            if details:
                mrkdwn_lines.extend(f"*{k}:* `{v}`" for k, v in details.items())
            payload = {
                "text": subject,
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "Staff account change"},
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "\n".join(mrkdwn_lines)},
                    },
                ],
            }
            with httpx.Client(timeout=10.0) as client:
                response = client.post(slack_url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.error("Slack staff governance alert failed: %s", exc)


def notify_device_catalog_review(*, subject: str, html_body: str, text_body: Optional[str] = None) -> None:
    """Slack alert for device catalog drift — email goes to admin report recipients separately."""
    settings = get_settings()
    slack_url = (settings.slack_webhook_url or "").strip()
    if not slack_url:
        return
    try:
        payload = {
            "text": subject,
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "eSIM device catalog review"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": _escape(text_body or subject)}},
            ],
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(slack_url, json=payload)
            response.raise_for_status()
    except Exception as exc:
        logger.error("Slack device catalog alert failed: %s", exc)


def notify_affiliate_payout_request(
    *,
    code: str,
    display_name: str,
    email: str,
    balance_cents: int,
    payout_email: Optional[str] = None,
) -> None:
    """Alert ops when a partner requests a payout from the self-service dashboard."""
    settings = get_settings()
    slack_url = (settings.slack_webhook_url or "").strip()
    ops_email = (settings.ops_alert_email or "").strip()

    if not slack_url and not ops_email:
        logger.warning("Affiliate payout request from %s but no alert channel configured", code)
        return

    amount = f"${balance_cents / 100:.2f}"
    subject = f"[NoorLink] Affiliate payout request — {code} ({amount})"
    summary = f"{display_name} ({code}) requested a payout of {amount}."
    pay_to = payout_email or email
    text_body = (
        f"{summary}\n"
        f"Contact: {email}\n"
        f"Payout email on file: {pay_to}\n"
        f"Open Admin → Affiliate payout wizard to mark paid after sending funds."
    )
    html_body = (
        f"<h2>Affiliate payout request</h2>"
        f"<p>{_escape(summary)}</p>"
        "<ul>"
        f"<li><strong>Code:</strong> {_escape(code)}</li>"
        f"<li><strong>Balance:</strong> {_escape(amount)}</li>"
        f"<li><strong>Contact:</strong> {_escape(email)}</li>"
        f"<li><strong>Payout email:</strong> {_escape(pay_to)}</li>"
        "</ul>"
        "<p>Record payment in <strong>Admin → Affiliate payout</strong> after PayPal/Wise/bank transfer.</p>"
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
            logger.error("Affiliate payout request email failed: %s", exc)

    if slack_url:
        try:
            payload = {
                "text": subject,
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "Affiliate payout request"}},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*{display_name}* (`{code}`)\n"
                                f"*Amount:* {amount}\n"
                                f"*Contact:* {email}\n"
                                f"*Payout to:* {pay_to}"
                            ),
                        },
                    },
                ],
            }
            with httpx.Client(timeout=10.0) as client:
                response = client.post(slack_url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.error("Slack affiliate payout alert failed: %s", exc)
