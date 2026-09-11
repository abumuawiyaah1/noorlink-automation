"""Tests for post-purchase install-help and install-congrats reminders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services.install_reminders import (
    maybe_send_install_congrats,
    order_eligible_for_install_congrats,
    order_eligible_for_install_help,
    order_looks_installed,
    process_install_congrats,
    process_install_reminders,
)


def _base_row(**overrides):
    now = datetime.now(timezone.utc)
    fulfilled = (now - timedelta(hours=30)).isoformat()
    row = {
        "id": "oid-install-1",
        "order_number": "NL-INST1",
        "email": "traveler@example.com",
        "country": "United States",
        "package_name": "United States 10GB · 30 Days",
        "flag_emoji": "🇺🇸",
        "status": "delivered",
        "fulfilled_at": fulfilled,
        "paid_at": fulfilled,
        "qr_code_url": "https://quickchart.io/qr?text=test",
        "lpa_string": "LPA:1$example$CODE",
        "activation_code": "CODE",
        "metadata": {},
    }
    row.update(overrides)
    return row


def test_skips_when_already_installed_via_snapshot():
    row = _base_row(
        metadata={
            "usage_snapshot": {
                "activated": True,
                "activation_status": "active",
            }
        }
    )
    assert order_looks_installed(row) is True
    assert order_eligible_for_install_help(row, wait_hours=24) is False


def test_skips_when_order_status_active():
    row = _base_row(status="active")
    assert order_eligible_for_install_help(row, wait_hours=24) is False


def test_skips_before_wait_window():
    now = datetime.now(timezone.utc)
    row = _base_row(fulfilled_at=(now - timedelta(hours=2)).isoformat())
    assert order_eligible_for_install_help(row, now=now, wait_hours=24) is False


def test_eligible_after_wait_when_not_installed():
    now = datetime.now(timezone.utc)
    row = _base_row(fulfilled_at=(now - timedelta(hours=30)).isoformat())
    assert order_eligible_for_install_help(row, now=now, wait_hours=24) is True


def test_skips_when_already_sent():
    now = datetime.now(timezone.utc)
    row = _base_row(
        metadata={"reminders": {"install_help_sent_at": now.isoformat()}},
    )
    assert order_eligible_for_install_help(row, now=now, wait_hours=24) is False


def test_process_sends_once_and_stamps_metadata():
    row = _base_row()

    with (
        patch(
            "app.services.install_reminders.db.list_orders_for_install_reminders",
            return_value=[row],
        ),
        patch(
            "app.services.install_reminders.send_esim_install_help_email",
            return_value="msg-1",
        ) as send_mail,
        patch("app.services.install_reminders.db.merge_order_metadata") as merge,
        patch(
            "app.services.install_reminders.get_settings",
        ) as settings,
    ):
        settings.return_value.install_reminder_hours = 24
        settings.return_value.install_reminder_lookback_days = 14
        settings.return_value.app_url = "https://noorlink.co"
        result = process_install_reminders()

    assert result["sent"] == 1
    assert result["skipped"] == 0
    send_mail.assert_called_once()
    merge.assert_called_once()
    assert "install_help_sent_at" in merge.call_args[0][1]["reminders"]


def test_process_skips_installed_orders():
    row = _base_row(
        status="active",
        metadata={"usage_snapshot": {"activated": True, "activation_status": "active"}},
    )

    with (
        patch(
            "app.services.install_reminders.db.list_orders_for_install_reminders",
            return_value=[row],
        ),
        patch(
            "app.services.install_reminders.send_esim_install_help_email",
        ) as send_mail,
        patch("app.services.install_reminders.db.merge_order_metadata") as merge,
        patch(
            "app.services.install_reminders.get_settings",
        ) as settings,
    ):
        settings.return_value.install_reminder_hours = 24
        settings.return_value.install_reminder_lookback_days = 14
        settings.return_value.app_url = "https://noorlink.co"
        result = process_install_reminders()

    assert result["sent"] == 0
    assert result["skipped"] == 1
    send_mail.assert_not_called()
    merge.assert_not_called()


def test_congrats_eligible_when_installed():
    row = _base_row(
        status="active",
        metadata={"usage_snapshot": {"activated": True, "activation_status": "installed"}},
    )
    assert order_eligible_for_install_congrats(row) is True


def test_congrats_skips_when_already_sent():
    now = datetime.now(timezone.utc)
    row = _base_row(
        status="active",
        metadata={
            "usage_snapshot": {"activated": True, "activation_status": "installed"},
            "reminders": {"install_congrats_sent_at": now.isoformat()},
        },
    )
    assert order_eligible_for_install_congrats(row) is False


def test_maybe_send_install_congrats_stamps_once():
    row = _base_row(
        status="active",
        metadata={"usage_snapshot": {"activated": True, "activation_status": "installed"}},
    )
    with (
        patch(
            "app.services.install_reminders.db.get_order_row_by_order_number",
            return_value=row,
        ),
        patch(
            "app.services.install_reminders.send_esim_install_congrats_email",
            return_value="msg-c",
        ) as send_mail,
        patch("app.services.install_reminders.db.merge_order_metadata") as merge,
        patch("app.services.install_reminders.get_settings") as settings,
    ):
        settings.return_value.app_url = "https://noorlink.co"
        assert maybe_send_install_congrats("NL-INST1") is True

    send_mail.assert_called_once()
    assert "install_congrats_sent_at" in merge.call_args[0][1]["reminders"]


def test_process_install_congrats_sends_for_active_orders():
    row = _base_row(
        status="active",
        metadata={"usage_snapshot": {"activated": True, "activation_status": "active"}},
    )
    with (
        patch(
            "app.services.install_reminders.db.list_orders_for_install_reminders",
            return_value=[row],
        ),
        patch(
            "app.services.install_reminders.maybe_send_install_congrats",
            return_value=True,
        ) as maybe,
        patch("app.services.install_reminders.get_settings") as settings,
    ):
        settings.return_value.install_reminder_lookback_days = 14
        result = process_install_congrats()

    assert result["sent"] == 1
    maybe.assert_called_once_with("NL-INST1")
