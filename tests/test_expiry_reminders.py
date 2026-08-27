"""Tests for eSIM expiry reminder qualification logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services.expiry_reminders import (
    _country_plans_url,
    process_esim_expiry_reminders,
)


def test_country_plans_url():
    assert _country_plans_url("https://noorlink.co", "Turkey") == (
        "https://noorlink.co/plans/turkey"
    )
    assert "regional/europe" in _country_plans_url(
        "https://noorlink.co", "regional-europe"
    )


def test_process_sends_expired_email_once():
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=16)).isoformat()
    row = {
        "id": "oid-1",
        "order_number": "NL-EXP1",
        "email": "traveler@example.com",
        "country": "turkey",
        "package_name": "Turkey 10GB",
        "flag_emoji": "🇹🇷",
        "status": "delivered",
        "created_at": created,
        "fulfilled_at": created,
        "paid_at": created,
        "data_total_gb": 10,
        "data_used_gb": 2,
        "amount_cents": 2999,
        "currency": "USD",
        "metadata": {"validity_days": 15},
    }

    with (
        patch(
            "app.services.expiry_reminders.db.list_orders_for_expiry_reminders",
            return_value=[row],
        ),
        patch(
            "app.services.expiry_reminders.db.get_breakage_allowance_by_order_id",
            return_value=None,
        ),
        patch(
            "app.services.expiry_reminders.send_esim_expired_email",
            return_value="msg-1",
        ) as send_expired,
        patch(
            "app.services.expiry_reminders.send_esim_expiring_soon_email"
        ) as send_soon,
        patch("app.services.expiry_reminders.db.merge_order_metadata") as merge,
    ):
        result = process_esim_expiry_reminders()

    assert result["expired_sent"] == 1
    assert result["expiring_soon_sent"] == 0
    send_expired.assert_called_once()
    send_soon.assert_not_called()
    merge.assert_called_once()
    assert "expiry_sent_at" in merge.call_args[0][1]["reminders"]


def test_skips_when_expiry_already_sent():
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=20)).isoformat()
    row = {
        "id": "oid-2",
        "order_number": "NL-EXP2",
        "email": "traveler@example.com",
        "country": "france",
        "package_name": "France 5GB",
        "status": "delivered",
        "created_at": created,
        "fulfilled_at": created,
        "data_total_gb": 5,
        "data_used_gb": 1,
        "amount_cents": 1999,
        "currency": "USD",
        "metadata": {
            "validity_days": 7,
            "reminders": {"expiry_sent_at": now.isoformat()},
        },
    }

    with (
        patch(
            "app.services.expiry_reminders.db.list_orders_for_expiry_reminders",
            return_value=[row],
        ),
        patch(
            "app.services.expiry_reminders.db.get_breakage_allowance_by_order_id",
            return_value=None,
        ),
        patch("app.services.expiry_reminders.send_esim_expired_email") as send_expired,
    ):
        result = process_esim_expiry_reminders()

    assert result["expired_sent"] == 0
    send_expired.assert_not_called()


def test_expiring_soon_when_one_day_left():
    now = datetime.now(timezone.utc)
    # 6 days ago + 7 day validity ≈ 1 day left
    created = (now - timedelta(days=6)).isoformat()
    row = {
        "id": "oid-3",
        "order_number": "NL-SOON1",
        "email": "soon@example.com",
        "country": "germany",
        "package_name": "Germany 3GB",
        "status": "delivered",
        "created_at": created,
        "fulfilled_at": created,
        "data_total_gb": 3,
        "data_used_gb": 0.5,
        "amount_cents": 1499,
        "currency": "USD",
        "metadata": {"validity_days": 7},
    }

    with (
        patch(
            "app.services.expiry_reminders.db.list_orders_for_expiry_reminders",
            return_value=[row],
        ),
        patch(
            "app.services.expiry_reminders.db.get_breakage_allowance_by_order_id",
            return_value=None,
        ),
        patch("app.services.expiry_reminders.send_esim_expired_email") as send_expired,
        patch(
            "app.services.expiry_reminders.send_esim_expiring_soon_email",
            return_value="msg-2",
        ) as send_soon,
        patch("app.services.expiry_reminders.db.merge_order_metadata"),
    ):
        result = process_esim_expiry_reminders()

    assert result["expiring_soon_sent"] == 1
    assert result["expired_sent"] == 0
    send_soon.assert_called_once()
    send_expired.assert_not_called()
