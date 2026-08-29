"""Tests for Resend delivery webhook handling."""

import base64
import hashlib
import hmac
import json
from unittest.mock import patch

from app.services.resend_events import handle_resend_email_event, verify_resend_webhook_signature


def test_verify_svix_signature():
    secret = base64.b64encode(b"test-secret").decode()
    whsec = f"whsec_{secret}"
    body = json.dumps({"type": "email.bounced", "data": {"to": "a@example.com"}})
    msg_id = "msg_123"
    timestamp = "1700000000"
    signed = f"{msg_id}.{timestamp}.{body}".encode()
    digest = base64.b64encode(hmac.new(base64.b64decode(secret), signed, hashlib.sha256).digest()).decode()
    assert verify_resend_webhook_signature(
        payload=body.encode(),
        secret=whsec,
        svix_id=msg_id,
        svix_timestamp=timestamp,
        svix_signature=f"v1,{digest}",
    )


@patch("app.services.resend_events.log_email_delivery")
@patch("app.services.resend_events.db.unsubscribe_newsletter_subscriber", return_value=True)
def test_bounce_unsubscribes_newsletter(mock_unsub, mock_log):
    result = handle_resend_email_event(
        event_type="email.bounced",
        data={"to": "bounce@example.com", "email_id": "em_1", "subject": "Insider"},
    )
    assert result["logged"] is True
    assert result["newsletter_unsubscribed"] is True
    mock_log.assert_called_once()
