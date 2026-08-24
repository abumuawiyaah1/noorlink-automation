"""Tests for multi-country regional product catalog."""

from __future__ import annotations

from app.api.regional_inventory import (
    REGIONAL_PRODUCTS,
    build_regional_package_payload,
    build_regional_product_rows,
    resolve_regional_product_by_display_name,
    resolve_regional_product_slug,
)


def test_all_regional_products_have_plans():
    for product_id in REGIONAL_PRODUCTS:
        rows = build_regional_product_rows(product_id)
        assert len(rows) == 5, product_id
        assert rows[0]["country_id"] == product_id
        assert str(rows[0]["id"]).startswith("regional-")


def test_resolve_regional_slugs():
    assert resolve_regional_product_slug("europe") == "regional-europe"
    assert resolve_regional_product_slug("global") == "regional-global"
    assert resolve_regional_product_slug("worldwide") == "regional-global"
    assert resolve_regional_product_slug("africa") == "regional-africa"
    assert resolve_regional_product_slug("south-america") == "regional-south-america"
    assert resolve_regional_product_slug("france") is None


def test_resolve_regional_display_names():
    assert (
        resolve_regional_product_by_display_name("Europe Regional")
        == "regional-europe"
    )
    assert (
        resolve_regional_product_by_display_name("Global Regional")
        == "regional-global"
    )


def test_build_regional_package_payload():
    payload = build_regional_package_payload(
        regional_product_id="regional-europe",
        price_cents=3499,
    )
    assert payload is not None
    assert payload["country"] == "Europe Regional"
    assert payload["metadata"]["product_type"] == "regional"
    assert payload["metadata"]["region_slug"] == "europe"
    assert len(payload["metadata"]["coverage_countries"]) >= 10


def test_phase_three_products_exist():
    assert "regional-global" in REGIONAL_PRODUCTS
    assert "regional-africa" in REGIONAL_PRODUCTS
    assert "regional-south-america" in REGIONAL_PRODUCTS
