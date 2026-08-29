"""Handle Resend delivery webhooks (bounce, complaint, delivered)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from app.api import supabase_repository as db
from app.services.ops_event_log import log_email_delivery

logger = logging.getLogger(__name__)

BOUNCE_EVENTS = {"email.bounced", "email.complained"}
DELIVERY_EVENTS = {"email.delivered", "email.sent", "email.delivery_delayed"}


def verify_resend_webhook_signature(
    *,
    payload: bytes,
    secret: str,
    svix_id: Optional[str],
    svix_timestamp: Optional[str],
    svix_signature: Optional[str],
) -> bool:
    """Verify Resend/Svix webhook signature (whsec_... secret from Resend dashboard)."""
    if not secret or not svix_id or not svix_timestamp or not svix_signature:
        return False

    key = secret[6:] if secret.startswith("whsec_") else secret
    try:
        secret_bytes = base64.b64decode(key)
    except Exception:
        return False

    body = payload.decode("utf-8")
    signed = f"{svix_id}.{svix_timestamp}.{body}".encode("utf-8")
    expected = hmac.new(secret_bytes, signed, hashlib.sha256).digest()

    for part in svix_signature.split(" "):
        if not part.startswith("v1,"):
            continue
        try:
            provided = base64.b64decode(part[3:])
        except Exception:
            continue
        if hmac.compare_digest(expected, provided):
            return True
    return False


def _parse_recipient(data: Dict[str, Any]) -> str:
    for key in ("to", "email", "recipient"):
        value = data.get(key)
        if isinstance(value, list) and value:
            value = value[0]
        text = str(value or "").strip()
        if "<" in text and ">" in text:
            return text.split("<", 1)[1].split(">", 1)[0].strip().lower()
        if text:
            return text.lower()
    return ""


def handle_resend_email_event(*, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Log delivery outcome and auto-unsubscribe on hard bounces / complaints."""
    recipient = _parse_recipient(data)
    email_type = str(data.get("tags", {}).get("type") if isinstance(data.get("tags"), dict) else "") or "transactional"
    if isinstance(data.get("tags"), list):
        email_type = "transactional"

    subject = str(data.get("subject") or "").strip() or None
    message_id = str(data.get("email_id") or data.get("id") or "").strip() or None

    mapped_event = "sent"
    if event_type in BOUNCE_EVENTS:
        mapped_event = "bounced" if event_type == "email.bounced" else "complained"
    elif event_type in DELIVERY_EVENTS:
        mapped_event = "delivered" if event_type == "email.delivered" else "sent"

    if recipient:
        log_email_delivery(
            event_type=mapped_event,
            recipient=recipient,
            email_type=email_type,
            subject=subject,
            message_id=message_id,
            details={
                "resend_event": event_type,
                "bounce_type": data.get("bounce_type") or data.get("type"),
            },
        )

    unsubscribed = False
    if event_type in BOUNCE_EVENTS and recipient:
        try:
            unsubscribed = db.unsubscribe_newsletter_subscriber(recipient)
        except Exception:
            logger.exception("Newsletter auto-unsubscribe failed for %s", recipient)

    if event_type == "email.complained" and recipient:
        from app.services.ops_alerts import notify_email_complaint

        notify_email_complaint(
            recipient=recipient,
            subject=subject,
            resend_event=event_type,
        )

    return {
        "event_type": event_type,
        "recipient": recipient or None,
        "logged": bool(recipient),
        "newsletter_unsubscribed": unsubscribed,
    }
