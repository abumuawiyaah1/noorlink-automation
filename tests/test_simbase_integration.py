"""
Simbase sandbox integration tests (mocked HTTP / DB).

Covers:
1. Auth + account balance
2. LPA assembly + Base64 QR
3. Webhook auto-suspend margin guard
4. 401 / 404 error resilience
"""

from __future__ import annotations

import base64
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.services.simbase import (
    SimbaseAuthError,
    SimbaseClient,
    SimbaseNotFoundError,
)
from app.utils.qr_generator import format_lpa_string, generate_qr_code_base64


BASE = "https://api.simbase.com/v2"


@pytest.mark.asyncio
@respx.mock
async def test_1_authentication_and_balance_check():
    route = respx.get(f"{BASE}/account/balance").mock(
        return_value=Response(200, json={"balance": 42.5, "currency": "EUR"})
    )
    async with SimbaseClient(api_key="sb_test_key", base_url=BASE) as client:
        payload = await client.get_account_balance()

    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer sb_test_key"
    assert payload
    assert payload.get("balance") == 42.5


def test_2_lpa_assembly_and_qr_code_generation():
    lpa = format_lpa_string("rsp.simbase.com", "ACT-CODE-999")
    assert lpa == "LPA:1$rsp.simbase.com$ACT-CODE-999"

    data_uri = generate_qr_code_base64(lpa)
    assert data_uri.startswith("data:image/png;base64,")
    raw = data_uri.split(",", 1)[1]
    decoded = base64.b64decode(raw)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_3_webhook_auto_suspend_margin_guard():
    from app.api.main import app

    iccid = "8900000000000000000"
    order_row: Dict[str, Any] = {
        "id": "ord-1",
        "order_number": "NL-TEST001",
        "iccid": iccid,
        "status": "active",
        "data_limit_bytes": 10_000_000_000,
        "metadata": {},
    }
    suspended_row = {**order_row, "status": "suspended"}

    mock_client = MagicMock()
    mock_client.update_sim_state = AsyncMock(return_value={"state": "disabled"})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.api.webhooks.SimbaseClient", return_value=mock_client), patch(
        "app.api.webhooks.db.get_order_row_by_iccid", return_value=order_row
    ), patch(
        "app.api.webhooks.db.suspend_order_by_iccid", return_value=suspended_row
    ) as suspend_mock:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/webhooks/simbase",
                headers={"x-simbase-requesttoken": "test_webhook_secret_key"},
                json={
                    "event": "usage_exceeds_threshold",
                    "iccid": iccid,
                    "current_bytes": 11_000_000_000,
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["handled"] is True
    assert body["action"] == "suspended"
    mock_client.update_sim_state.assert_awaited_once_with(iccid, "disabled")
    suspend_mock.assert_called_once()
    assert suspend_mock.call_args.kwargs.get("usage_bytes") == 11_000_000_000


@pytest.mark.asyncio
@respx.mock
async def test_4_error_handling_resilience():
    respx.get(f"{BASE}/account/balance").mock(
        return_value=Response(401, json={"error": "unauthorized"})
    )
    respx.get(f"{BASE}/simcards/bad-iccid").mock(
        return_value=Response(404, json={"error": "not found"})
    )

    async with SimbaseClient(api_key="bad-key", base_url=BASE) as client:
        with pytest.raises(SimbaseAuthError) as auth_exc:
            await client.get_account_balance()
        assert auth_exc.value.status_code == 401

        with pytest.raises(SimbaseNotFoundError) as nf_exc:
            await client.get_sim_details("bad-iccid")
        assert nf_exc.value.status_code == 404

    # Webhook path: Simbase disable failure should return 502, not crash
    from app.api.main import app

    iccid = "8900000000000000000"
    order_row = {
        "id": "ord-2",
        "order_number": "NL-TEST002",
        "iccid": iccid,
        "status": "active",
        "data_limit_bytes": 1_000,
        "metadata": {},
    }

    failing = MagicMock()
    failing.update_sim_state = AsyncMock(
        side_effect=SimbaseAuthError("bad key", status_code=401)
    )
    failing.__aenter__ = AsyncMock(return_value=failing)
    failing.__aexit__ = AsyncMock(return_value=None)

    with patch("app.api.webhooks.SimbaseClient", return_value=failing), patch(
        "app.api.webhooks.db.get_order_row_by_iccid", return_value=order_row
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/webhooks/simbase",
                headers={"x-simbase-requesttoken": "test_webhook_secret_key"},
                json={
                    "event": "usage_limits",
                    "iccid": iccid,
                    "current_bytes": 5_000,
                },
            )

    assert response.status_code == 502
    assert "Failed to disable SIM" in response.json()["detail"]
