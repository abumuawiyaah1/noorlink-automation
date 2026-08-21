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
