"""
Zesimo reseller client + provision tests (mocked HTTP).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from app.services.fulfillment_map import (
    FulfillmentMapError,
    FulfillmentTarget,
    enforce_provider_credentials,
    enforce_saudi_access_policy,
)
from app.services.zesimo import (
    ZesimoAuthError,
    ZesimoClient,
    ZesimoInsufficientBalanceError,
    first_esim_from_order_payload,
)
from app.services.zesimo_sku_map import ZESIMO_SKU_MAP, by_phase

BASE = "https://zesimo.com/api/v1"


def test_sku_map_complete():
    assert len(ZESIMO_SKU_MAP) == 146
    assert len(by_phase(1)) == 4
    assert len(by_phase(2)) == 11
    assert len(by_phase(3)) == 9
    assert len(by_phase(4)) == 6
    assert len(by_phase(5)) == 116
    assert all(row.get("package_id") for row in ZESIMO_SKU_MAP)


def test_first_esim_from_order_payload():
    esim = first_esim_from_order_payload(
        {
            "order": {
                "id": 99,
                "esims": [
                    {
                        "iccid": "8944",
                        "activation_code": "LPA:1$smdp.example$ABC",
                    }
                ],
            }
        }
    )
    assert esim["iccid"] == "8944"
    assert esim["activation_code"].startswith("LPA:")


@pytest.mark.asyncio
@respx.mock
async def test_place_order_sends_bearer_and_idempotency():
    route = respx.post(f"{BASE}/orders").mock(
        return_value=Response(
            201,
            json={
                "order": {
                    "id": 42,
                    "esims": [
                        {
                            "iccid": "8944",
                            "activation_code": "LPA:1$smdp.example$XYZ",
                        }
                    ],
                }
            },
        )
    )
    async with ZesimoClient(api_key="zk_test", base_url=BASE) as client:
        payload = await client.place_order(
            package_id=583,
            quantity=1,
            idempotency_key="NL-ORDER-1",
        )

    assert payload["order"]["id"] == 42
    assert route.calls.last.request.headers["Authorization"] == "Bearer zk_test"
    assert route.calls.last.request.headers["Idempotency-Key"] == "NL-ORDER-1"
    body = route.calls.last.request.read()
    assert b'"package_id":583' in body or b'"package_id": 583' in body


@pytest.mark.asyncio
@respx.mock
async def test_place_order_402_insufficient_balance():
    respx.post(f"{BASE}/orders").mock(
        return_value=Response(402, json={"message": "Insufficient wallet balance."})
    )
    async with ZesimoClient(api_key="zk_test", base_url=BASE) as client:
        with pytest.raises(ZesimoInsufficientBalanceError):
            await client.place_order(
                package_id=583,
                quantity=1,
                idempotency_key="NL-1",
            )


@pytest.mark.asyncio
@respx.mock
async def test_place_order_401_auth():
    respx.post(f"{BASE}/orders").mock(
        return_value=Response(401, json={"message": "Unauthenticated"})
    )
    async with ZesimoClient(api_key="bad", base_url=BASE) as client:
        with pytest.raises(ZesimoAuthError):
            await client.place_order(
                package_id=1,
                quantity=1,
                idempotency_key="NL-1",
            )


def test_enforce_saudi_allows_zesimo_unlimited(monkeypatch):
    monkeypatch.setattr(
        "app.services.fulfillment_map.get_settings",
        lambda: MagicMock(
            esim_access_enforce_saudi=True,
            esim_access_access_code="x",
            zesimo_api_key="zk_test",
        ),
    )
    target = FulfillmentTarget(
        catalog_key="sa-unlimited-3gb-7d",
        provider="zesimo",
        provider_sku="10903",
        provider_slug="zesimo-sa-unlimited-7d",
        wholesale_cents=2142,
        period_num=None,
        source="test",
    )
    enforce_saudi_access_policy({"country": "Saudi Arabia"}, target)


def test_enforce_saudi_rejects_zesimo_fixed_gb(monkeypatch):
    monkeypatch.setattr(
        "app.services.fulfillment_map.get_settings",
        lambda: MagicMock(
            esim_access_enforce_saudi=True,
            esim_access_access_code="x",
            zesimo_api_key="zk_test",
        ),
    )
    target = FulfillmentTarget(
        catalog_key="sa-10gb-30",
        provider="zesimo",
        provider_sku="999",
        provider_slug="bad",
        wholesale_cents=100,
        period_num=None,
        source="test",
    )
    with pytest.raises(FulfillmentMapError, match="esimaccess"):
        enforce_saudi_access_policy({"country": "Saudi Arabia"}, target)


def test_enforce_provider_credentials_requires_zesimo_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.fulfillment_map.get_settings",
        lambda: MagicMock(zesimo_api_key="", esim_access_access_code="x"),
    )
    target = FulfillmentTarget(
        catalog_key="us-10gb-30",
        provider="zesimo",
        provider_sku="7673",
        provider_slug="zesimo-us-10gb-30d",
        wholesale_cents=809,
        period_num=None,
        source="test",
    )
    with pytest.raises(FulfillmentMapError, match="ZESIMO_API_KEY"):
        enforce_provider_credentials(target)


def test_enforce_provider_credentials_ok_with_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.fulfillment_map.get_settings",
        lambda: MagicMock(zesimo_api_key="zk_live", esim_access_access_code="x"),
    )
    target = FulfillmentTarget(
        catalog_key="us-10gb-30",
        provider="zesimo",
        provider_sku="7673",
        provider_slug="zesimo-us-10gb-30d",
        wholesale_cents=809,
        period_num=None,
        source="test",
    )
    enforce_provider_credentials(target)


@pytest.mark.asyncio
@respx.mock
async def test_get_esim_and_topup_packages():
    respx.get(f"{BASE}/esims/1001").mock(
        return_value=Response(
            200,
            json={
                "esim": {
                    "id": 1001,
                    "status": "active",
                    "data_package_mb": 3072,
                    "data_used_mb": 512,
                    "data_left_mb": 2560,
                }
            },
        )
    )
    respx.get(f"{BASE}/esims/1001/topup-packages").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 565,
                        "package_code": "EU-3GB-30",
                        "reseller_price": 4.5,
                        "data_gb": 3,
                        "duration_days": 30,
                        "topup_behaviour": "accumulates",
                    }
                ]
            },
        )
    )
    respx.post(f"{BASE}/esims/1001/topup").mock(
        return_value=Response(200, json={"ok": True, "topup_id": 91})
    )

    async with ZesimoClient(api_key="zk_test", base_url=BASE) as client:
        esim = await client.get_esim(1001)
        assert esim["id"] == 1001
        assert esim["data_used_mb"] == 512
        packages = await client.list_topup_packages(1001)
        assert len(packages) == 1
        assert packages[0]["topup_behaviour"] == "accumulates"
        result = await client.topup_esim(1001, package_id=565)
        assert result["ok"] is True
