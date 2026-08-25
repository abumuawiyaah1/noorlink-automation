"""
Telna Connect Flex client tests (mocked HTTP).
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.services.telna import (
    TelnaAuthError,
    TelnaClient,
    normalize_product,
)

ORDERING = "https://ppo-api.telna.com/v1/ordering"
DIAGNOSTIC = "https://ppo-api.telna.com/v1/diagnostic"


SAMPLE_PRODUCT = {
    "id": "67f6c112d07af55d502bef78",
    "name": "Middle East Bundle-10 GB 30 Days",
    "sim_product": 132,
    "status": "AVAILABLE",
    "unit_cost": 28,
    "created_date": 1712683730000,
    "package_template": {
        "id": 1001,
        "name": "ME-10-30",
        "voice_usage_allowance": 0,
        "data_usage_allowance": 10240 * 1024 * 1024,
        "sms_usage_allowance": 0,
        "time_allowance": {"unit": "SECOND", "duration": 720 * 3600},
        "activation_time_allowance": 8760 * 3600,
        "supported_countries": ["SAU", "TUR", "EGY", "ARE"],
        "traffic_policy": 0,
        "activation_type": "AUTO",
    },
}


def test_normalize_product_extracts_cost_and_allowances():
    row = normalize_product(SAMPLE_PRODUCT)
    assert row["id"] == "67f6c112d07af55d502bef78"
    assert row["unit_cost_usd"] == 28.0
    assert row["data_mb"] == 10240.0
    assert row["duration_days"] == 30.0
    assert "SAU" in row["supported_countries"]
    assert row["country_count"] == 4


@pytest.mark.asyncio
@respx.mock
async def test_list_products_sends_raw_token_auth_header():
    route = respx.get(f"{ORDERING}/products").mock(
        return_value=Response(
            200,
            json={"total": 0, "offset": 0, "count": 0, "products": []},
        )
    )
    async with TelnaClient(
        api_token="tok_test",
        ordering_base_url=ORDERING,
        diagnostic_base_url=DIAGNOSTIC,
    ) as client:
        await client.list_products(count=1)

    assert route.calls.last.request.headers["Authorization"] == "tok_test"
    assert not route.calls.last.request.headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
@respx.mock
async def test_list_products_and_catalog_summary():
    respx.get(f"{ORDERING}/products").mock(
        return_value=Response(
            200,
            json={
                "total": 1,
                "offset": 0,
                "count": 1,
                "products": [SAMPLE_PRODUCT],
            },
        )
    )
    async with TelnaClient(
        api_token="tok_test",
        ordering_base_url=ORDERING,
        diagnostic_base_url=DIAGNOSTIC,
    ) as client:
        payload = await client.list_products(count=50)
        summary = await client.catalog_summary()

    assert payload["total"] == 1
    assert summary[0]["unit_cost_usd"] == 28.0
    assert summary[0]["name"].startswith("Middle East")


@pytest.mark.asyncio
@respx.mock
async def test_telna_auth_error():
    respx.get(f"{ORDERING}/products").mock(
        return_value=Response(401, json={"error": "nope"})
    )
    async with TelnaClient(
        api_token="bad",
        ordering_base_url=ORDERING,
        diagnostic_base_url=DIAGNOSTIC,
    ) as client:
        with pytest.raises(TelnaAuthError):
            await client.list_products()


@pytest.mark.asyncio
@respx.mock
async def test_create_work_order_returns_activation_code():
    respx.post(f"{ORDERING}/work-orders").mock(
        return_value=Response(
            200,
            json={
                "id": "wo_1",
                "customer_ref": "NL-TEST1",
                "product": SAMPLE_PRODUCT["id"],
                "status": "SHIPPED",
                "created_date": 1,
                "package": {},
                "sim_registry": {"iccid": "8910000000000000001"},
                "euicc_profile": {
                    "iccid": "8910000000000000001",
                    "activation_code": "LPA:1$smdp.telna.example$MATCHINGID",
                    "state": "RELEASED",
                    "cc_required": False,
                    "reuse_enabled": False,
                    "reuse_remaining_count": 0,
                    "profile_reuse_policy": {"reuse_type": "NEVER", "max_count": 0},
                },
            },
        )
    )
    async with TelnaClient(
        api_token="tok_test",
        ordering_base_url=ORDERING,
        diagnostic_base_url=DIAGNOSTIC,
    ) as client:
        order = await client.create_work_order(
            product_id=SAMPLE_PRODUCT["id"],
            customer_ref="NL-TEST1",
        )

    assert order["status"] == "SHIPPED"
    assert order["euicc_profile"]["activation_code"].startswith("LPA:")
