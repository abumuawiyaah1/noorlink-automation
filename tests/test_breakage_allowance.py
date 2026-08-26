"""Tests for virtual bundle allowance ledger logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.breakage_allowance import (
    allowance_valid_until,
    breakage_profit_estimate,
    evaluate_allowance_status,
    prepare_allowance_record,
    remaining_mb,
    should_create_allowance,
)


def test_should_create_allowance_for_turkey_traveler():
    assert should_create_allowance(
        country="turkey",
        data_gb=10,
        validity_days=15,
    )


def test_should_not_create_allowance_for_jamaica():
    assert not should_create_allowance(
        country="jamaica",
        data_gb=10,
        validity_days=15,
    )


def test_should_not_create_for_topup():
    assert not should_create_allowance(
        country="turkey",
        data_gb=10,
        validity_days=15,
        wants_topup=True,
    )


def test_prepare_allowance_record_shape():
    row = prepare_allowance_record(
        order_id="oid-1",
        order_number="NL-1001",
        country="turkey",
        data_gb=10,
        validity_days=15,
        retail_usd=29.99,
        plan_key="traveler",
    )
    assert row["allowance_mb"] == 10240
    assert row["order_number"] == "NL-1001"
    assert row["status"] == "pending"
    assert row["metadata"]["breakage_eligible"] is True


def test_evaluate_status_exhausted():
    status = evaluate_allowance_status(
        {"status": "active", "allowance_mb": 1024, "used_mb": 1024, "valid_until": None}
    )
    assert status == "exhausted"


def test_evaluate_status_expired():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    status = evaluate_allowance_status(
        {
            "status": "active",
            "allowance_mb": 5120,
            "used_mb": 1000,
            "valid_until": past.isoformat(),
        }
    )
    assert status == "expired"


def test_remaining_mb():
    assert remaining_mb({"allowance_mb": 10240, "used_mb": 3000}) == 7240


def test_breakage_profit_on_expired_unused():
    est = breakage_profit_estimate(
        {
            "retail_usd": 29.99,
            "wholesale_cost_usd": 5.50,
            "allowance_mb": 10240,
            "used_mb": 2048,
            "status": "expired",
        }
    )
    assert est["unused_mb"] == 8192
    assert est["is_breakage_event"] is True
    assert est["margin_usd_so_far"] == 24.49


def test_allowance_valid_until():
    start = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    end = allowance_valid_until(validity_days=15, from_dt=start)
    assert end == start + timedelta(days=15)
