"""Tests for customer order enrichment and ops alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.order_customer_view import (
    compute_data_remaining_gb,
    compute_days_remaining,
    enrich_order_row,
    fulfillment_pending,
)


def test_fulfillment_pending_when_paid_without_qr():
    assert fulfillment_pending({"status": "paid", "qr_code_url": None}) is True
    assert fulfillment_pending({"status": "delivered", "qr_code_url": "https://x"}) is False


def test_compute_data_remaining():
    assert compute_data_remaining_gb(data_total_gb=10, data_used_gb=3) == 7.0
    assert compute_data_remaining_gb(allowance_mb=10240, used_mb=2048) == 8.0


def test_compute_days_remaining():
    start = datetime(2026, 8, 26, tzinfo=timezone.utc)
    now = start + timedelta(hours=1)
    assert compute_days_remaining(validity_days=15, start_at=start, now=now) == 15


def test_enrich_order_row_includes_validity_from_metadata():
    row = {
        "id": "uuid-1",
        "order_number": "NL-999",
        "email": "test@example.com",
        "country": "turkey",
        "package_name": "Turkey 10GB",
        "amount_cents": 2999,
        "currency": "USD",
        "status": "delivered",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "qr_code_url": "https://example.com/qr",
        "data_total_gb": 10,
        "data_used_gb": 2,
        "metadata": {"validity_days": 15},
    }
    _, order = enrich_order_row(row)
    assert order.validity_days == 15
    assert order.data_remaining_gb == 8.0
    assert order.days_remaining is not None
    assert order.fulfillment_pending is False


def test_notify_fulfillment_failure_no_config(caplog):
    from app.services.ops_alerts import notify_fulfillment_failure

    notify_fulfillment_failure(
        order_number="NL-1",
        email="a@b.com",
        country="Turkey",
        package_name="Plan",
        error="test error",
    )
    # Should not raise when alerts not configured
