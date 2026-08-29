"""Tests for phase 2/3 admin services."""

from unittest.mock import MagicMock, patch

import pytest

from app.admin.tools_catalog import tools_for_role
from app.admin.wizard_catalog import wizards_for_role
from app.services.admin_insider_wizard import AdminInsiderError, parse_insider_wizard_form
from app.services.admin_newsletter import subscriber_stats
from app.services.admin_order_context import AdminOrderContextError, build_order_context
from app.services.admin_staff_user import AdminStaffUserError, create_staff_user_from_wizard


def test_tools_for_support():
    keys = {t.key for t in tools_for_role("support")}
    assert "fulfill-order" in keys
    assert "affiliate-payout" not in keys


def test_wizards_include_insider_for_marketing():
    keys = {w.key for w in wizards_for_role("marketing")}
    assert "insider-wizard" in keys
    assert "new-promo" in keys


def test_parse_insider_wizard_requires_preview():
    with pytest.raises(AdminInsiderError, match="Preview"):
        parse_insider_wizard_form({"subject": "Hello"})


@patch("app.services.admin_order_context.db.get_order_row_by_order_number")
@patch("app.services.admin_order_context.db.get_breakage_allowance_by_order_number")
def test_build_order_context_gift(mock_breakage, mock_order):
    mock_order.return_value = {
        "order_number": "NL-GIFT1",
        "status": "delivered",
        "email": "buyer@example.com",
        "country": "Turkey",
        "package_name": "10GB",
        "amount_cents": 1999,
        "metadata": {
            "gift": {
                "is_gift": True,
                "recipient_email": "friend@example.com",
                "recipient_name": "Friend",
                "sender_name": "Buyer",
            },
            "reminders": {"low_data_70_sent_at": "2026-01-01T00:00:00Z"},
        },
    }
    mock_breakage.return_value = None
    ctx = build_order_context(order_number="NL-GIFT1")
    assert ctx["is_gift"] is True
    assert ctx["gift_recipient_email"] == "friend@example.com"
    assert len(ctx["reminder_labels"]) >= 1


def test_build_order_context_not_found():
    with patch("app.services.admin_order_context.db.get_order_row_by_order_number", return_value=None):
        with pytest.raises(AdminOrderContextError, match="not found"):
            build_order_context(order_number="NL-NOPE")


def test_create_staff_user_short_password():
    with pytest.raises(AdminStaffUserError, match="12 characters"):
        create_staff_user_from_wizard(
            form={"username": "newuser", "password": "short", "role": "support"}
        )


@patch("app.services.admin_newsletter.list_subscriber_rows")
def test_subscriber_stats(mock_list):
    mock_list.return_value = [
        {"email": "a@x.com", "unsubscribed_at": None},
        {"email": "b@x.com", "unsubscribed_at": "2026-01-01"},
    ]
    stats = subscriber_stats()
    assert stats["active"] == 1
    assert stats["unsubscribed"] == 1
