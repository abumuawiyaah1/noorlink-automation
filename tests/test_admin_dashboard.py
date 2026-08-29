"""Tests for admin dashboard helpers."""

from unittest.mock import patch

import pytest

from app.admin.passwords import MIN_PASSWORD_LENGTH, hash_password, verify_password
from app.services.admin_orders import AdminOrderError, resend_order_esim_email


def test_password_hash_roundtrip():
    raw = "super-secure-pass-123"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed)
    assert not verify_password("wrong-password", hashed)


def test_min_password_length_constant():
    assert MIN_PASSWORD_LENGTH >= 12


def test_resend_requires_delivered_status():
    with pytest.raises(AdminOrderError, match="delivered or active"):
        resend_order_esim_email(
            {
                "order_number": "NL-TEST",
                "status": "paid",
                "email": "a@example.com",
                "qr_code_url": "https://example.com/qr",
                "activation_code": "LPA:1$test",
                "metadata": {},
            }
        )


def test_resend_requires_qr():
    with pytest.raises(AdminOrderError, match="QR code"):
        resend_order_esim_email(
            {
                "order_number": "NL-TEST",
                "status": "delivered",
                "email": "a@example.com",
                "qr_code_url": "",
                "activation_code": "",
                "metadata": {},
            }
        )


@patch("app.services.admin_orders.send_fulfillment_email", return_value="msg_123")
def test_resend_success(mock_send):
    message_id = resend_order_esim_email(
        {
            "order_number": "NL-ABC123",
            "status": "delivered",
            "email": "buyer@example.com",
            "country": "Turkey",
            "package_name": "Traveler 10GB",
            "flag_emoji": "🇹🇷",
            "qr_code_url": "https://example.com/qr.png",
            "activation_code": "LPA:1$abc",
            "metadata": {"travel_assistant": {"itinerary": []}},
        }
    )
    assert message_id == "msg_123"
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to_email"] == "buyer@example.com"
    assert "Turkey" in kwargs["subject"]


@patch("app.services.admin_orders.send_fulfillment_email", return_value="msg_gift")
def test_resend_gift_goes_to_recipient(mock_send):
    resend_order_esim_email(
        {
            "order_number": "NL-GIFT1",
            "status": "delivered",
            "email": "buyer@example.com",
            "country": "Saudi Arabia",
            "package_name": "Pilgrim 5GB",
            "qr_code_url": "https://example.com/qr.png",
            "activation_code": "LPA:1$gift",
            "metadata": {
                "gift": {
                    "is_gift": True,
                    "recipient_email": "friend@example.com",
                    "recipient_name": "Sara",
                    "sender_name": "Ahmed",
                },
                "travel_assistant": {},
            },
        }
    )
    assert mock_send.call_args.kwargs["to_email"] == "friend@example.com"


def test_admin_models_import():
    from app.db.models import AdminUser, Order, EsimPackage  # noqa: F401

    assert Order.__tablename__ == "orders"
    assert EsimPackage.__tablename__ == "esim_packages"
