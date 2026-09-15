"""Tests for eSIM usage sync and top-up helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

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
        "metadata": {
            "validity_days": 15,
            "fulfillment": {"provider": "citrus", "funded_usd": 20.0},
        },
        "fulfilled_at": "2026-08-01T12:00:00+00:00",
    }
    snapshot = build_usage_snapshot(
        provider="citrus",
        source="test",
        row=row,
        provider_payload={
            "status": "active",
            "wallet_balance_usd": 8.5,
            "total_data_charged_usd": 11.5,
        },
    )
    assert snapshot["provider"] == "citrus"
    assert snapshot["usage_mode"] == "wallet"
    assert snapshot["topup_supported"] is True
    assert snapshot["activated"] is True
    assert snapshot["wallet_balance_usd"] == 8.5
    assert snapshot["wallet_charged_usd"] == 11.5
    assert snapshot["wallet_funded_usd"] == 20.0
    # Catalog GB must not masquerade as live remaining for Citrus PAYG.
    assert snapshot["data_remaining_gb"] is None
    assert snapshot["data_used_gb"] is None
    assert snapshot["usage_pct"] == 57.5


def test_build_usage_snapshot_citrus_explicit_gb():
    row = {
        "order_number": "NL-1b",
        "iccid": "8944",
        "metadata": {"fulfillment": {"provider": "citrus"}},
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
            "data_total_gb": 10,
        },
    )
    assert snapshot["usage_mode"] == "data_gb"
    assert snapshot["data_used_gb"] == 1.5
    assert snapshot["data_total_gb"] == 10.0
    assert snapshot["data_remaining_gb"] == 8.5


def test_build_usage_snapshot_esimaccess_unused_volume():
    row = {
        "order_number": "NL-2b",
        "iccid": "8945",
        "metadata": {"fulfillment": {"provider": "esimaccess"}},
        "fulfilled_at": "2026-08-01T12:00:00+00:00",
    }
    snapshot = build_usage_snapshot(
        provider="esimaccess",
        source="test",
        row=row,
        provider_payload={
            "esimStatus": "IN_USE",
            "smdpStatus": "ENABLED",
            "totalVolume": 5 * 1024 * 1024 * 1024,
            "unusedVolume": 3 * 1024 * 1024 * 1024,
        },
    )
    assert snapshot["usage_mode"] == "data_gb"
    assert snapshot["data_total_gb"] == 5.0
    assert snapshot["data_used_gb"] == 2.0
    assert snapshot["data_remaining_gb"] == 3.0


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
    assert caps["mode"] == "wallet"
    assert 10.0 in caps["amounts_usd"]


def test_topup_capabilities_esimaccess_enabled():
    row = {
        "order_number": "NL-4",
        "status": "active",
        "iccid": "8945",
        "metadata": {"fulfillment": {"provider": "esimaccess", "provider_slug": "SA_5_30"}},
    }
    caps = topup_capabilities(row)
    assert caps["supported"] is True
    assert caps["mode"] == "access_package"
    assert caps["amounts_usd"] == []


def test_topup_capabilities_esimaccess_max_topups():
    history = [{"at": f"2026-01-0{i}"} for i in range(1, 10)]
    row = {
        "order_number": "NL-4b",
        "status": "active",
        "iccid": "8945",
        "metadata": {
            "fulfillment": {"provider": "esimaccess"},
            "topups": {"history": history},
        },
    }
    caps = topup_capabilities(row)
    assert caps["supported"] is False
    assert "maximum" in (caps.get("reason") or "").lower()


def test_normalize_access_fixed_package():
    from app.services.esim_topup import normalize_access_topup_package

    offer = normalize_access_topup_package(
        {
            "slug": "SA_5_30",
            "packageCode": "CKH279",
            "name": "Saudi 5GB 30Days",
            "price": 72200,
            "volume": 5 * 1073741824,
            "duration": 30,
            "durationUnit": "DAY",
            "dataType": 1,
            "supportTopUpType": 2,
        }
    )
    assert offer is not None
    assert offer["slug"] == "SA_5_30"
    assert offer["period_num"] is None
    assert offer["wholesale_usd"] == 7.22
    assert offer["retail_cents"] == int(round(7.22 * 1.35 * 100))


def test_normalize_access_daypass_package():
    from app.services.esim_topup import normalize_access_topup_package

    offer = normalize_access_topup_package(
        {
            "slug": "SA_3_Daily_1Mbps",
            "packageCode": "PVEXXS543",
            "name": "Saudi Daily",
            "price": 68040,
            "volume": 0,
            "duration": 14,
            "durationUnit": "DAY",
            "dataType": 2,
            "supportTopUpType": 3,
        },
        period_num=14,
    )
    assert offer is not None
    assert offer["daypass"] is True
    assert offer["period_num"] == 14
    assert offer["wholesale_usd"] == 6.804


def test_topup_capabilities_zesimo_enabled():
    row = {
        "order_number": "NL-Z1",
        "status": "active",
        "iccid": "8944900",
        "metadata": {"fulfillment": {"provider": "zesimo", "esim_tran_no": "1001"}},
    }
    caps = topup_capabilities(row)
    assert caps["supported"] is True
    assert caps["mode"] == "zesimo_package"
    assert caps["provider"] == "zesimo"


def test_normalize_zesimo_accumulates_package():
    from app.services.esim_topup import normalize_zesimo_topup_package

    offer = normalize_zesimo_topup_package(
        {
            "id": 565,
            "package_code": "EU-3GB-30",
            "name": "Europe 3 GB / 30 days",
            "reseller_price": 4.5,
            "data_gb": 3,
            "duration_days": 30,
            "topup_behaviour": "accumulates",
        }
    )
    assert offer is not None
    assert offer["package_id"] == 565
    assert offer["package_code"] == "EU-3GB-30"
    assert offer["wholesale_usd"] == 4.5
    assert offer["retail_cents"] == int(round(4.5 * 1.35 * 100))
    assert offer["name"] == "3 GB / 30 days"
    assert offer["topup_behaviour"] == "accumulates"


def test_normalize_zesimo_skips_replaces_package():
    from app.services.esim_topup import normalize_zesimo_topup_package

    offer = normalize_zesimo_topup_package(
        {
            "id": 566,
            "package_code": "EU-5GB-30",
            "name": "Europe 5 GB",
            "reseller_price": 6.0,
            "data_gb": 5,
            "duration_days": 30,
            "topup_behaviour": "replaces",
        }
    )
    assert offer is None


def test_build_usage_snapshot_zesimo_esim_detail():
    row = {
        "order_number": "NL-Z2",
        "iccid": "8944901",
        "metadata": {"fulfillment": {"provider": "zesimo"}, "validity_days": 30},
        "fulfilled_at": "2026-08-01T12:00:00+00:00",
    }
    snapshot = build_usage_snapshot(
        provider="zesimo",
        source="test",
        row=row,
        provider_payload={
            "esim": {
                "id": 1001,
                "status": "active",
                "status_qr": "Installed",
                "data_package_mb": 3072.0,
                "data_used_mb": 1024.0,
                "data_left_mb": 2048.0,
                "plan_activated_at": "2026-08-02T10:00:00+00:00",
                "plan_expired_at": "2026-09-01T10:00:00+00:00",
            },
            "source": "get_esim",
        },
    )
    assert snapshot["activated"] is True
    assert snapshot["topup_supported"] is True
    assert snapshot["data_total_gb"] == 3.0
    assert snapshot["data_used_gb"] == 1.0
    assert snapshot["valid_until"] == "2026-09-01T10:00:00+00:00"


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


@pytest.mark.asyncio
async def test_apply_access_topup_mock():
    row = {
        "order_number": "NL-6",
        "status": "active",
        "iccid": "8944002",
        "metadata": {
            "fulfillment": {
                "provider": "esimaccess",
                "provider_slug": "SA_5_30",
                "esim_tran_no": "T-ACCESS-1",
            }
        },
    }
    offer = {
        "offer_id": "SA_5_30-abc",
        "slug": "SA_5_30",
        "package_code": "CKH279",
        "name": "5 GB / 30 days",
        "daypass": False,
        "wholesale_usd": 7.22,
        "retail_usd": 9.75,
        "period_num": None,
    }

    with patch("app.services.esim_access.EsimAccessClient") as mock_client_cls:
        client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client
        client.topup_esim.return_value = {"ok": True, "transactionId": "x"}

        with patch("app.services.esim_topup.sync_order_usage_blocking"):
            with patch("app.services.esim_topup.db.get_order_row_by_order_number", return_value=row):
                with patch("app.services.esim_topup.db.merge_order_metadata") as merge:
                    from app.services.esim_topup import apply_access_topup

                    result = await apply_access_topup(row, offer, source="test")
                    assert result["ok"] is True
                    client.topup_esim.assert_called_once()
                    kwargs = client.topup_esim.await_args.kwargs
                    assert kwargs["iccid"] == "8944002"
                    assert kwargs["slug"] == "SA_5_30"
                    merge.assert_called_once()


@pytest.mark.asyncio
@respx.mock
async def test_list_access_topup_offers_from_iccid():
    from app.services.esim_topup import list_access_topup_offers

    respx.post("https://api.esimaccess.com/api/v1/open/package/list").mock(
        return_value=Response(
            200,
            json={
                "success": True,
                "obj": {
                    "packageList": [
                        {
                            "slug": "SA_5_30",
                            "packageCode": "CKH279",
                            "name": "Saudi 5GB",
                            "price": 72200,
                            "volume": 5368709120,
                            "duration": 30,
                            "durationUnit": "DAY",
                            "dataType": 1,
                            "supportTopUpType": 2,
                        }
                    ]
                },
            },
        )
    )
    row = {
        "order_number": "NL-7",
        "iccid": "8944999",
        "metadata": {"fulfillment": {"provider": "esimaccess", "provider_slug": "SA_5_30"}},
    }
    with patch("app.services.esim_access.get_settings") as settings:
        settings.return_value = MagicMock(
            esim_access_access_code="test_code",
            esim_access_api_base_url="https://api.esimaccess.com/api/v1/open",
        )
        offers = await list_access_topup_offers(row)
    assert len(offers) == 1
    assert offers[0]["slug"] == "SA_5_30"