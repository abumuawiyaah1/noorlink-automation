"""Tests for eSIM usage sync and top-up helpers."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.esim_topup import topup_capabilities, topup_retail_cents
from app.services.esim_usage_sync import (
    build_usage_snapshot,
    parse_esimaccess_webhook_usage,
    resolve_order_provider,
)


def test_resolve_order_provider_from_metadata():
    row = {
        "metadata": {
            "fulfillment": {"provider": "citrus"},
        }
    }
    assert resolve_order_provider(row) == "citrus"


def test_build_usage_snapshot_citrus_wallet():
    row = {
        "order_number": "NL-1",
        "iccid": "8944",
        "data_total_gb": 10,
        "data_used_gb": 1,
        "metadata": {"validity_days": 15, "fulfillment": {"provider": "citrus"}},
        "fulfilled_at": "2026-08-01T12:00:00+00:00",
    }
    snapshot = build_usage_snapshot(
        provider="citrus",
        source="test",
        row=row,
        provider_payload={
            "status": "active",
            "wallet_balance_usd": 8.5,
            "data_used_gb": 1.5,
        },
    )
    assert snapshot["provider"] == "citrus"
    assert snapshot["topup_supported"] is True
    assert snapshot["activated"] is True
    assert snapshot["data_used_gb"] == 1.5
    assert snapshot["wallet_balance_usd"] == 8.5


def test_build_usage_snapshot_esimaccess_bytes():
    row = {
        "order_number": "NL-2",
        "iccid": "8945",
        "metadata": {"fulfillment": {"provider": "esimaccess"}},
        "fulfilled_at": "2026-08-01T12:00:00+00:00",
    }
    snapshot = build_usage_snapshot(
        provider="esimaccess",
        source="webhook",
        row=row,
        provider_payload={
            "esimStatus": "IN_USE",
            "smdpStatus": "ENABLED",
            "totalVolume": 10 * 1024 * 1024 * 1024,
            "orderUsage": 2 * 1024 * 1024 * 1024,
        },
    )
    assert snapshot["data_total_gb"] == 10.0
    assert snapshot["data_used_gb"] == 2.0
    assert snapshot["activated"] is True


def test_parse_esimaccess_webhook_usage():
    overrides = parse_esimaccess_webhook_usage(
        {
            "totalVolume": 5 * 1024**3,
            "orderUsage": 1 * 1024**3,
            "esimStatus": "IN_USE",
            "smdpStatus": "ENABLED",
        }
    )
    assert overrides["data_used_gb"] == 1.0
    assert overrides["activated"] is True


def test_topup_capabilities_citrus():
    row = {
        "order_number": "NL-3",
        "status": "active",
        "iccid": "8944",
        "metadata": {"fulfillment": {"provider": "citrus"}},
    }
    caps = topup_capabilities(row)
    assert caps["supported"] is True
    assert 10.0 in caps["amounts_usd"]


def test_topup_capabilities_esimaccess_fixed_pack():
    row = {
        "order_number": "NL-4",
        "status": "active",
        "iccid": "8945",
        "metadata": {"fulfillment": {"provider": "esimaccess"}},
    }
    caps = topup_capabilities(row)
    assert caps["supported"] is False
    assert "repurchased" in (caps.get("reason") or "").lower()


def test_topup_retail_markup():
    assert topup_retail_cents(10.0) == int(round(10 * 1.35 * 100))


@pytest.mark.asyncio
async def test_fund_citrus_topup_mock():
    row = {
        "order_number": "NL-5",
        "status": "active",
        "iccid": "8944001",
        "metadata": {"fulfillment": {"provider": "citrus"}},
    }

    with patch("app.services.citrus.CitrusClient") as mock_client_cls:
        client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client
        client.fund_esim.return_value = {"ok": True}

        with patch("app.services.esim_topup.sync_order_usage_blocking"):
            with patch("app.services.esim_topup.db.get_order_row_by_order_number", return_value=row):
                with patch("app.services.esim_topup.db.merge_order_metadata"):
                    from app.services.esim_topup import fund_citrus_topup

                    result = await fund_citrus_topup(row, 10.0, source="test")
                    assert result["ok"] is True
                    client.fund_esim.assert_called_once()
