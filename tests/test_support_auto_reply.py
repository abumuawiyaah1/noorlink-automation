"""Tests for support auto-reply MVP."""

from unittest.mock import patch

from app.services.support_auto_reply import (
    build_auto_reply_body,
    classify_intent,
    extract_order_number,
    run_support_auto_reply,
)


def test_extract_order_number():
    assert extract_order_number("My order is NL-ABC12345 please help") == "NL-ABC12345"
    assert extract_order_number("nothing here") is None


def test_classify_refund():
    assert classify_intent(subject="Refund", message="I want my money back", category="refund") == "refund"


def test_classify_qr_missing():
    assert (
        classify_intent(subject="Order help", message="I didn't get my QR code", category="order_help")
        == "qr_missing"
    )


def test_classify_install():
    assert (
        classify_intent(subject="Install / QR code", message="How do I activate on iPhone?", category="install_qr")
        == "install"
    )


def test_build_reply_includes_links():
    with patch("app.services.support_auto_reply.get_settings") as mock_settings:
        mock_settings.return_value.app_url = "https://noorlink.co"
        body = build_auto_reply_body(
            name="Sam",
            intent="general",
            order_row=None,
            qr_resent=False,
            qr_resend_error=None,
        )
    assert "/dashboard" in body
    assert "Sam" in body


@patch("app.services.support_auto_reply._send_auto_outbound")
@patch("app.services.support_auto_reply._lookup_order_row")
def test_auto_reply_refund_needs_human(mock_lookup, mock_send):
    mock_lookup.return_value = None
    result = run_support_auto_reply(
        ticket_number="TCK-TEST0001",
        name="Sam",
        email="sam@example.com",
        subject="Refund",
        message="Please refund NL-ABCDEF12",
        order_number="NL-ABCDEF12",
        category="refund",
    )
    assert result["needs_human"] is True
    assert result["auto_resolved"] is False
    assert result["intent"] == "refund"
    mock_send.assert_called_once()


@patch("app.services.support_auto_reply._ensure_ticket_order")
@patch("app.services.support_auto_reply._send_auto_outbound")
@patch("app.services.support_auto_reply._lookup_order_row")
def test_auto_reply_qr_resend_resolves(mock_lookup, mock_send, mock_ensure):
    mock_lookup.return_value = {
        "order_number": "NL-ABCDEF12",
        "status": "delivered",
        "qr_code_url": "https://example.com/qr.png",
        "package_name": "Saudi 5GB",
        "country": "Saudi Arabia",
    }
    with patch(
        "app.services.customer_self_service.customer_resend_esim_email",
        return_value={"success": True},
    ):
        result = run_support_auto_reply(
            ticket_number="TCK-TEST0002",
            name="Sam",
            email="sam@example.com",
            subject="Install / QR code",
            message="Please resend my QR code NL-ABCDEF12",
            order_number="NL-ABCDEF12",
            category="install_qr",
        )
    assert result["qr_resent"] is True
    assert result["auto_resolved"] is True
    assert result["needs_human"] is False
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs.get("close") is True
