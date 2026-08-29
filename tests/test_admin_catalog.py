"""Tests for catalog admin approval helpers."""

from app.services.admin_catalog import (
    apply_fulfillment_approval_rules,
    apply_package_approval_rules,
    fulfillment_map_requires_approval,
    is_known_provider,
    package_sale_status,
    parse_custom_plan_wizard_form,
    price_change_requires_approval,
    suggest_plan_slug,
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
