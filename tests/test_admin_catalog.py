"""Tests for catalog admin approval helpers."""

import pytest

from app.services.admin_catalog import (
    ACTIVE_NEW_SALES_PROVIDERS,
    AdminCatalogError,
    apply_fulfillment_approval_rules,
    apply_package_approval_rules,
    fulfillment_map_requires_approval,
    is_known_provider,
    list_fulfillment_provider_options,
    package_sale_status,
    parse_custom_plan_wizard_form,
    price_change_requires_approval,
    suggest_plan_slug,
    validate_fulfillment_map_payload,
)


def test_price_change_threshold():
    assert price_change_requires_approval(1000, 1150) is True
    assert price_change_requires_approval(1000, 1050) is False


def test_new_provider_requires_approval():
    assert fulfillment_map_requires_approval(
        provider="newvendor",
        is_create=True,
        provider_changed=False,
    )


def test_known_provider_new_route_requires_approval():
    assert is_known_provider("esimaccess")
    assert fulfillment_map_requires_approval(
        provider="esimaccess",
        is_create=True,
        provider_changed=False,
    )


def test_package_sale_status_pending():
    assert package_sale_status(is_active=False, admin_approved=False) == "Pending approval"
    assert package_sale_status(is_active=True, admin_approved=True) == "On sale"


def test_apply_package_price_pending_for_catalog():
    validated = {"price_cents": 1500}

    class Existing:
        price_cents = 1000
        pending_price_cents = None
        admin_approved = True

    apply_package_approval_rules(
        validated,
        is_create=False,
        editor_is_admin=False,
        editor_username="catalog",
        existing=Existing(),
    )
    assert validated["price_cents"] == 1000
    assert validated["pending_price_cents"] == 1500


def test_suggest_plan_slug():
    slug = suggest_plan_slug(country="Turkey", data_label="10GB", validity_days=15)
    assert slug == "turkey-10gb-15d"


def test_parse_wizard_form_auto_fields():
    parsed = parse_custom_plan_wizard_form(
        {
            "country": "Turkey",
            "data_label": "10GB",
            "validity_days": "15",
            "price_cents": "1999",
            "provider": "citrus",
            "provider_sku": "SKU-123",
        }
    )
    assert parsed["slug"] == "turkey-10gb-15d"
    assert parsed["name"] == "Turkey 10GB"
    assert parsed["catalog_key"] == "turkey-10gb-15d-citrus"
    assert parsed["provider"] == "citrus"


def test_wizard_providers_exclude_retired_rails():
    options = list_fulfillment_provider_options()
    assert "telna" not in options
    assert "weconnect" not in options
    assert set(options) == ACTIVE_NEW_SALES_PROVIDERS
    assert "citrus" in options
    assert "esimaccess" in options
    assert "zesimo" in options


def test_reject_telna_on_new_fulfillment_map():
    with pytest.raises(AdminCatalogError, match="Telna/WeConnect retired"):
        validate_fulfillment_map_payload(
            {
                "catalog_key": "turkey-10gb-30-telna",
                "provider": "telna",
                "provider_sku": "OLD-SKU",
                "is_active": True,
            },
            is_create=True,
        )


def test_reject_weconnect_on_new_fulfillment_map():
    with pytest.raises(AdminCatalogError, match="Telna/WeConnect retired"):
        validate_fulfillment_map_payload(
            {
                "catalog_key": "flex-payg-weconnect",
                "provider": "weconnect",
                "provider_sku": "WC-1",
            },
            is_create=True,
        )


def test_ghana_requires_esimaccess():
    with pytest.raises(AdminCatalogError, match="Ghana routes must use esimaccess"):
        validate_fulfillment_map_payload(
            {
                "catalog_key": "ghana-10gb-30",
                "country_slug": "ghana",
                "country_code": "GH",
                "provider": "citrus",
                "provider_sku": "CIT-GH",
            },
            is_create=True,
        )

    ok = validate_fulfillment_map_payload(
        {
            "catalog_key": "ghana-10gb-30",
            "country_slug": "ghana",
            "country_code": "GH",
            "provider": "esimaccess",
            "provider_sku": "MB040",
        },
        is_create=True,
    )
    assert ok["provider"] == "esimaccess"


def test_inactive_historical_telna_row_notes_edit_allowed():
    """Existing inactive Telna rows stay readable/editable without re-activating."""

    class Existing:
        provider = "telna"

    cleaned = validate_fulfillment_map_payload(
        {
            "catalog_key": "legacy-telna-row",
            "provider": "telna",
            "provider_sku": "OLD",
            "is_active": False,
            "notes": "legacy only",
        },
        is_create=False,
        existing=Existing(),
    )
    assert cleaned["provider"] == "telna"
    assert cleaned["is_active"] is False


def test_reactivating_historical_telna_row_blocked():
    class Existing:
        provider = "telna"

    with pytest.raises(AdminCatalogError, match="Telna/WeConnect retired"):
        validate_fulfillment_map_payload(
            {
                "catalog_key": "legacy-telna-row",
                "provider": "telna",
                "provider_sku": "OLD",
                "is_active": True,
            },
            is_create=False,
            existing=Existing(),
        )
