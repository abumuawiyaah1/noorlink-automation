"""
eSIM Access + virtual catalog fulfillment map tests (mocked HTTP / no live wallet).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

from app.services.esim_access import (
    EsimAccessClient,
    EsimAccessInsufficientBalanceError,
    api_price_to_usd,
    build_signed_headers,
    usd_to_api_price,
)
from app.services.fulfillment_map import (
    FulfillmentMapError,
    enforce_saudi_access_policy,
    is_saudi_destination,
    resolve_fulfillment_target,
)


BASE = "https://api.esimaccess.com/api/v1/open"


def test_price_scale():
    assert usd_to_api_price(7.22) == 72200
    assert api_price_to_usd(72200) == 7.22


def test_signed_headers_stable_hmac():
    body = "{}"
    headers = build_signed_headers("test_access_code", body)
    assert headers["RT-AccessCode"] == "test_access_code"
    assert headers["RT-Timestamp"].isdigit()
    assert headers["RT-RequestID"]
    expected = hmac.new(
        b"test_access_code",
        f"{headers['RT-Timestamp']}{headers['RT-RequestID']}test_access_code{body}".encode(),
        hashlib.sha256,
    ).hexdigest().lower()
    assert headers["RT-Signature"] == expected


def test_saudi_destination_aliases():
    assert is_saudi_destination("Saudi Arabia")
    assert is_saudi_destination("umrah")
    assert is_saudi_destination("hajj")
    assert is_saudi_destination(None, "SA")
    assert not is_saudi_destination("France")


def test_resolve_static_sa_map(monkeypatch):
    monkeypatch.setattr(
        "app.services.fulfillment_map._fetch_db_maps",
        lambda: [],
    )
    target = resolve_fulfillment_target(
        {"country": "Saudi Arabia", "data_total_gb": 10},
        package={"validity_days": 30},
    )
    assert target is not None
    assert target.provider == "esimaccess"
    assert target.provider_sku == "CKH280"
    assert target.catalog_key == "sa-10gb-30"


def test_enforce_saudi_requires_access(monkeypatch):
    monkeypatch.setattr(
        "app.services.fulfillment_map._fetch_db_maps",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.services.fulfillment_map.get_settings",
        lambda: MagicMock(
            esim_access_enforce_saudi=True,
            esim_access_access_code="",
        ),
    )
    target = resolve_fulfillment_target(
        {"country": "Saudi Arabia", "data_total_gb": 5},
        package={"validity_days": 30},
    )
    with pytest.raises(FulfillmentMapError, match="ESIM_ACCESS_ACCESS_CODE"):
        enforce_saudi_access_policy(
            {"country": "Saudi Arabia"},
            target,
        )


@pytest.mark.asyncio
@respx.mock
async def test_esim_access_balance_and_order():
    balance_route = respx.post(f"{BASE}/balance/query").mock(
        return_value=Response(
            200,
            json={"success": True, "errorCode": "0", "obj": {"balance": 500000}},
        )
    )
    order_route = respx.post(f"{BASE}/esim/order").mock(
        return_value=Response(
            200,
            json={
                "success": True,
                "obj": {"orderNo": "BTEST001", "transactionId": "NL-1"},
            },
        )
    )
    query_route = respx.post(f"{BASE}/esim/query").mock(
        return_value=Response(
            200,
            json={
                "success": True,
                "obj": {
                    "esimList": [
                        {
                            "esimTranNo": "T1",
                            "orderNo": "BTEST001",
                            "iccid": "8944000000000000001",
                            "ac": "LPA:1$rsp.example$ABC",
                            "qrCodeUrl": "https://p.qrsim.net/demo.png",
                            "smdpStatus": "RELEASED",
                            "esimStatus": "GOT_RESOURCE",
                        }
                    ]
                },
            },
        )
    )

    async with EsimAccessClient(access_code="test_code", base_url=BASE) as client:
        bal = await client.get_balance()
        assert bal["balance_usd"] == 50.0
        order = await client.order_esim(
            transaction_id="NL-1",
            package_code="CKH279",
        )
        assert order["orderNo"] == "BTEST001"
        profile = await client.wait_for_profile(order_no="BTEST001", attempts=1, delay_seconds=0)

    assert balance_route.called
    assert order_route.called
    assert query_route.called
    assert profile["iccid"].startswith("8944")
    # Signature headers present
    assert "RT-Signature" in order_route.calls.last.request.headers


@pytest.mark.asyncio
@respx.mock
async def test_esim_access_insufficient_balance():
    respx.post(f"{BASE}/balance/query").mock(
        return_value=Response(
            200,
            json={
                "success": False,
                "errorCode": "200007",
                "errorMsg": "Insufficient account balance",
                "obj": None,
            },
        )
    )
    async with EsimAccessClient(access_code="test_code", base_url=BASE) as client:
        with pytest.raises(EsimAccessInsufficientBalanceError):
            await client.get_balance()


@pytest.mark.asyncio
async def test_provision_routes_sa_to_access(monkeypatch):
    from app.services import esim_provision

    monkeypatch.setattr(
        "app.services.fulfillment_map._fetch_db_maps",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.services.esim_provision.get_settings",
        lambda: MagicMock(
            esim_provider="citrus",
            citrus_api_key="rsk_x",
            esim_access_access_code="access_x",
            esim_access_enforce_saudi=True,
            esim_access_api_base_url=BASE,
        ),
    )
    monkeypatch.setattr(
        "app.services.fulfillment_map.get_settings",
        lambda: MagicMock(
            esim_access_enforce_saudi=True,
            esim_access_access_code="access_x",
        ),
    )

    async def fake_access(order_row: Dict[str, Any], target: Any) -> Dict[str, Any]:
        return {
            "activation_code": "ABC",
            "qr_code_url": "https://p.qrsim.net/x.png",
            "lpa_string": "LPA:1$rsp.example$ABC",
            "provider": "esimaccess",
            "iccid": "8944",
            "provider_order_id": "B1",
            "provider_sku": target.provider_sku,
            "catalog_key": target.catalog_key,
        }

    monkeypatch.setattr(
        esim_provision,
        "_esimaccess_provision",
        lambda order_row, target: {
            "activation_code": "ABC",
            "qr_code_url": "https://p.qrsim.net/x.png",
            "lpa_string": "LPA:1$rsp.example$ABC",
            "provider": "esimaccess",
            "iccid": "8944",
            "provider_order_id": "B1",
            "provider_sku": target.provider_sku,
            "catalog_key": target.catalog_key,
        },
    )

    result = esim_provision.provision_esim(
        {
            "order_number": "NLTEST1",
            "country": "Saudi Arabia",
            "data_total_gb": 20,
            "email": "t@example.com",
        }
    )
    assert result["provider"] == "esimaccess"
    assert result["catalog_key"] == "sa-20gb-30"
    assert result["provider_sku"] == "CKH800"
