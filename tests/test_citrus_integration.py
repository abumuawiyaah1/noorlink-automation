"""
Citrus Mobile reseller integration tests (mocked HTTP / DB).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.services.citrus import CitrusAuthError, CitrusClient, CitrusNotFoundError


BASE = "https://citrusmobile.com/api/v2/reseller"


@pytest.mark.asyncio
@respx.mock
async def test_citrus_get_rates_ok():
    route = respx.get(f"{BASE}/rates").mock(
        return_value=Response(
            200,
            json={
                "countries": [
                    {
                        "name": "Ghana",
                        "iso2": "GH",
                        "cheapest_per_gb_usd": 1.38,
                        "networks": [
                            {"operator": "Vodafone Ghana", "per_gb_usd": 1.38},
                            {"operator": "MTN", "per_gb_usd": 5.52},
                        ],
                    }
                ]
            },
        )
    )
    async with CitrusClient(api_key="rsk_test", base_url=BASE) as client:
        payload = await client.get_rates(country="Ghana")

    assert route.called
    assert payload["countries"][0]["cheapest_per_gb_usd"] == 1.38


def test_citrus_funding_per_gb_mid_high_filters_outliers():
    from app.services.esim_provision import (
        _citrus_cheapest_per_gb_usd,
        _citrus_funding_per_gb_usd,
    )

    ghana_rates = {
        "countries": [
            {
                "name": "Ghana",
                "networks": [
                    {"operator": "Vodafone Ghana", "per_gb_usd": 1.38},
                    {"operator": "tiGO", "per_gb_usd": 2.58},
                    {"operator": "Airtel", "per_gb_usd": 2.58},
                    {"operator": "MTN", "per_gb_usd": 5.52},
                    {"operator": "Glo Ghana", "per_gb_usd": 87.55},
                ],
            }
        ]
    }
    assert _citrus_cheapest_per_gb_usd(ghana_rates) == 1.38
    # median 2.58 + high 5.52 (Glo dropped) → mid/high 4.05
    assert _citrus_funding_per_gb_usd(ghana_rates) == 4.05


def test_resolve_citrus_fund_usd_priority():
    from app.services.esim_provision import resolve_citrus_fund_usd

    # Mid/high GB×rate, capped at retail so we never fund more than they paid.
    rates = {
        "order_number": "NL-2",
        "amount_cents": 1799,
        "metadata": {"fulfillment_plan": {"data_gb": 5.0}},
    }
    assert resolve_citrus_fund_usd(rates, per_gb_usd=4.05) == 17.99  # min(20.25, 17.99)

    wholesale = {
        "order_number": "NL-1",
        "amount_cents": 1799,
        "metadata": {
            "fulfillment_plan": {"wholesale_cents": 690, "data_gb": 5},
        },
    }
    # With per_gb present, data_gb×rate wins (then retail cap).
    assert resolve_citrus_fund_usd(wholesale, per_gb_usd=1.38) == 6.9

    retail = {
        "order_number": "NL-3",
        "amount_cents": 1799,
        "metadata": {},
    }
    assert resolve_citrus_fund_usd(retail) == 8.99  # max(5, 17.99*0.5)


@pytest.mark.asyncio
async def test_citrus_provision_always_funds():
    from app.services.esim_provision import _citrus_provision_async

    order_row = {
        "order_number": "NL-FUND1",
        "email": "buyer@example.com",
        "country": "Ghana",
        "amount_cents": 1799,
        "metadata": {
            "wants_topup": True,
            "fulfillment_plan": {"data_gb": 5.0, "provider": "citrus"},
        },
    }

    mock_client = MagicMock()
    mock_client.provision_esim = AsyncMock(
        return_value={
            "iccid": "8910300000058398140",
            "lpa_string": "LPA:1$consumer.e-sim.global$ABC",
            "qr_code": "https://example.com/qr.png",
        }
    )
    mock_client.get_rates = AsyncMock(
        return_value={
            "countries": [
                {
                    "name": "Ghana",
                    "networks": [
                        {"operator": "Vodafone Ghana", "per_gb_usd": 1.38},
                        {"operator": "tiGO", "per_gb_usd": 2.58},
                        {"operator": "Airtel", "per_gb_usd": 2.58},
                        {"operator": "MTN", "per_gb_usd": 5.52},
                        {"operator": "Glo Ghana", "per_gb_usd": 87.55},
                    ],
                }
            ]
        }
    )
    mock_client.fund_esim = AsyncMock(
        return_value={"wallet_balance_usd": 17.99, "funded_usd": 17.99}
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.citrus.CitrusClient", return_value=mock_client):
        result = await _citrus_provision_async(order_row)

    # 5GB × $4.05 mid/high = $20.25, capped at retail $17.99
    mock_client.fund_esim.assert_awaited_once_with("8910300000058398140", 17.99)
    assert result["funded_usd"] == 17.99
    assert result["fund_rate_tier"] == "mid_high"
    assert result["provider"] == "citrus"


@pytest.mark.asyncio
async def test_citrus_provision_fails_when_fund_fails():
    from app.services.citrus import CitrusInsufficientBalanceError
    from app.services.esim_provision import _citrus_provision_async

    order_row = {
        "order_number": "NL-FUND2",
        "email": "buyer@example.com",
        "country": "Ghana",
        "amount_cents": 1799,
        "metadata": {"fulfillment_plan": {"wholesale_cents": 690, "data_gb": 5}},
    }

    mock_client = MagicMock()
    mock_client.provision_esim = AsyncMock(
        return_value={
            "iccid": "8910300000058398140",
            "lpa_string": "LPA:1$consumer.e-sim.global$ABC",
        }
    )
    mock_client.get_rates = AsyncMock(return_value={})
    mock_client.fund_esim = AsyncMock(
        side_effect=CitrusInsufficientBalanceError("Insufficient Citrus balance")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.citrus.CitrusClient", return_value=mock_client):
        with pytest.raises(CitrusInsufficientBalanceError):
            await _citrus_provision_async(order_row)


def test_citrus_sold_data_cap_stops_at_package_gb_not_wallet():
    """Sold 5GB with $10 wallet (~7GB) must stop at 5GB spend, not $0."""
    from app.services.esim_usage_sync import citrus_sold_data_cap_reached

    row = {
        "order_number": "NL-CAP5",
        "status": "active",
        "iccid": "8910300000058398140",
        "country": "Ghana",
        "metadata": {
            "fulfillment": {
                "provider": "citrus",
                "funded_usd": 10.0,
                "package_data_gb": 5.0,
                "fund_per_gb_usd": 1.38,
            },
            "fulfillment_plan": {"data_gb": 5.0, "provider": "citrus"},
        },
    }
    # ~5GB spent at $1.38 → should stop even though ~$3 left in wallet
    under = {"wallet_charged_usd": 5.0, "wallet_balance_usd": 5.0}
    assert citrus_sold_data_cap_reached(row, under, per_gb_usd=1.38) is None

    at_cap = {"wallet_charged_usd": 6.9, "wallet_balance_usd": 3.1}
    assert (
        citrus_sold_data_cap_reached(row, at_cap, per_gb_usd=1.38)
        == "package_data_exhausted"
    )

    expired = {
        "wallet_charged_usd": 2.0,
        "wallet_balance_usd": 8.0,
        "days_remaining": 0,
    }
    assert (
        citrus_sold_data_cap_reached(row, expired, per_gb_usd=1.38)
        == "validity_expired"
    )


@pytest.mark.asyncio
@respx.mock
async def test_citrus_get_account_ok():
    route = respx.get(f"{BASE}/account").mock(
        return_value=Response(
            200,
            json={
                "company_name": "Noorlink llc",
                "balance_usd": 3.5,
                "account_status": "active",
            },
        )
    )
    async with CitrusClient(api_key="rsk_test", base_url=BASE) as client:
        payload = await client.get_account()

    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer rsk_test"
    assert payload["balance_usd"] == 3.5


@pytest.mark.asyncio
@respx.mock
async def test_citrus_auth_and_not_found_errors():
    respx.get(f"{BASE}/account").mock(return_value=Response(401, json={"error": "nope"}))
    respx.get(f"{BASE}/esim/bad-iccid").mock(
        return_value=Response(404, json={"error": "missing"})
    )

    async with CitrusClient(api_key="bad", base_url=BASE) as client:
        with pytest.raises(CitrusAuthError):
            await client.get_account()
        with pytest.raises(CitrusNotFoundError):
            await client.get_esim("bad-iccid")


@pytest.mark.asyncio
async def test_citrus_webhook_balance_depleted_suspends():
    from app.api.main import app

    secret = "whsec_test_secret"
    iccid = "8999201200000000001"
    body = {
        "id": "evt_test",
        "event": "esim.balance_depleted",
        "created_at": "2026-08-21T00:00:00.000Z",
        "data": {"iccid": iccid, "wallet_balance_usd": 0},
    }
    raw = json.dumps(body).encode("utf-8")
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    order_row: Dict[str, Any] = {
        "id": "ord-c1",
        "order_number": "NL-CITRUS1",
        "iccid": iccid,
        "status": "active",
        "metadata": {},
    }
    suspended = {**order_row, "status": "suspended"}

    mock_client = MagicMock()
    mock_client.disable_esim = AsyncMock(return_value={"status": "suspended"})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.api.webhooks.get_settings") as gs, patch(
        "app.api.webhooks.CitrusClient", return_value=mock_client
    ), patch(
        "app.api.webhooks.db.get_order_row_by_iccid", return_value=order_row
    ), patch(
        "app.api.webhooks.db.suspend_order_by_iccid", return_value=suspended
    ) as suspend_mock:
        settings = MagicMock()
        settings.citrus_webhook_secret = secret
        gs.return_value = settings

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/webhooks/citrus",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-Citrus-Signature": signature,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["handled"] is True
    assert payload["action"] == "suspended"
    mock_client.disable_esim.assert_awaited_once_with(iccid)
    suspend_mock.assert_called_once_with(iccid)
