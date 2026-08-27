"""Tests for provider catalog matching and country → region → global resolver."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("RESEND_API_KEY", "re_test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")
os.environ.setdefault("ESIM_PROVIDER", "mock")
os.environ.setdefault("CITRUS_API_KEY", "rsk_test_key")

from app.core.config import get_settings
from app.services.fulfillment_map import resolve_fulfillment_target
from app.services.fulfillment_resolver import (
    choose_fulfillment_target,
    resolve_cascade,
)
from app.services.provider_catalog import (
    CatalogProduct,
    builtin_catalog,
    parse_product_name,
    rank_matches,
)


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_parse_telna_country_and_bundle_names():
    chile = parse_product_name("Chile-3 GB 7 Days")
    assert chile["scope"] == "country"
    assert chile["data_gb"] == 3.0
    assert chile["validity_days"] == 7
    assert "chile" in chile["country_slugs"]

    latam = parse_product_name("Latin America Bundle-1 GB 5 Days")
    assert latam["scope"] == "regional"
    assert latam["data_gb"] == 1.0
    assert any("brazil" in s or s.startswith("regional-") for s in latam["country_slugs"])

    global_p = parse_product_name("Global Bundle-1 GB 5 Days")
    assert global_p["scope"] == "global"


def test_rank_matches_prefers_exact_then_cheaper():
    products = [
        CatalogProduct(
            provider="telna",
            provider_sku="a",
            name="Chile-5 GB 7 Days",
            scope="country",
            country_slugs=("chile",),
            data_gb=5.0,
            validity_days=7,
            wholesale_cents=1200,
        ),
        CatalogProduct(
            provider="telna",
            provider_sku="b",
            name="Chile-3 GB 7 Days",
            scope="country",
            country_slugs=("chile",),
            data_gb=3.0,
            validity_days=7,
            wholesale_cents=900,
        ),
        CatalogProduct(
            provider="telna",
            provider_sku="c",
            name="Chile-3 GB 15 Days",
            scope="country",
            country_slugs=("chile",),
            data_gb=3.0,
            validity_days=15,
            wholesale_cents=800,
        ),
    ]
    hits = rank_matches(products, country_slug="chile", data_gb=3.0, validity_days=7)
    assert hits[0].provider_sku == "b"


def test_cascade_country_then_regional_then_global():
    catalog = [
        CatalogProduct(
            provider="telna",
            provider_sku="latam-3",
            name="Latin America Bundle-3 GB 7 Days",
            scope="regional",
            country_slugs=("chile", "brazil", "regional-south-america"),
            data_gb=3.0,
            validity_days=7,
            wholesale_cents=850,
        ),
        CatalogProduct(
            provider="telna",
            provider_sku="global-3",
            name="Global Bundle-3 GB 7 Days",
            scope="global",
            country_slugs=("global",),
            data_gb=3.0,
            validity_days=7,
            wholesale_cents=2150,
        ),
    ]
    # No country SKU → regional
    hit = resolve_cascade(
        country="chile", data_gb=3.0, validity_days=7, products=catalog
    )
    assert hit is not None
    assert hit.provider_sku == "latam-3"
    assert hit.source == "catalog:regional"

    # Country SKU wins over regional
    catalog_with_country = [
        CatalogProduct(
            provider="telna",
            provider_sku="chile-3",
            name="Chile-3 GB 7 Days",
            scope="country",
            country_slugs=("chile",),
            data_gb=3.0,
            validity_days=7,
            wholesale_cents=700,
        ),
        *catalog,
    ]
    hit2 = resolve_cascade(
        country="chile",
        data_gb=3.0,
        validity_days=7,
        products=catalog_with_country,
    )
    assert hit2 is not None
    assert hit2.provider_sku == "chile-3"
    assert hit2.source == "catalog:country"

    # Global fallback
    global_only = [catalog[1]]
    hit3 = resolve_cascade(
        country="mongolia", data_gb=3.0, validity_days=7, products=global_only
    )
    assert hit3 is not None
    assert hit3.provider_sku == "global-3"
    assert hit3.source == "catalog:global"


def test_choose_prefers_cheaper_cascade_over_map(monkeypatch):
    from app.services.fulfillment_map import FulfillmentTarget

    mapped = FulfillmentTarget(
        catalog_key="mapped",
        provider="esimaccess",
        provider_sku="EXPENSIVE",
        wholesale_cents=2000,
        data_gb=3.0,
        validity_days=7,
        source="static",
    )
    products = [
        CatalogProduct(
            provider="telna",
            provider_sku="cheap-chile",
            name="Chile-3 GB 7 Days",
            scope="country",
            country_slugs=("chile",),
            data_gb=3.0,
            validity_days=7,
            wholesale_cents=700,
        )
    ]
    chosen = choose_fulfillment_target(
        country="chile",
        data_gb=3.0,
        validity_days=7,
        mapped=mapped,
        wants_topup=False,
        products=products,
    )
    assert chosen is not None
    assert chosen.provider_sku == "cheap-chile"


def test_choose_keeps_silent_me_map_over_cheaper_country_sku():
    from app.services.fulfillment_map import FulfillmentTarget

    mapped = FulfillmentTarget(
        catalog_key="turkey-10gb-30",
        provider="telna",
        provider_sku="67f6c112d07af55d502bef78",
        wholesale_cents=2800,
        data_gb=10.0,
        validity_days=30,
        source="db:country_data",
    )
    products = [
        CatalogProduct(
            provider="telna",
            provider_sku="cheap-turkey",
            name="Turkey-10 GB 30 Days",
            scope="country",
            country_slugs=("turkey",),
            data_gb=10.0,
            validity_days=30,
            wholesale_cents=900,
        )
    ]
    chosen = choose_fulfillment_target(
        country="turkey",
        data_gb=10.0,
        validity_days=30,
        mapped=mapped,
        wants_topup=False,
        products=products,
    )
    assert chosen is not None
    assert chosen.provider_sku == mapped.provider_sku
    assert chosen.catalog_key == "turkey-10gb-30"


def test_topup_prefers_citrus_when_configured():
    chosen = choose_fulfillment_target(
        country="chile",
        data_gb=3.0,
        validity_days=7,
        mapped=None,
        wants_topup=True,
        products=builtin_catalog(),
    )
    assert chosen is not None
    assert chosen.provider == "citrus"
    assert chosen.source == "policy:topup"


def test_resolve_fulfillment_target_uses_builtin_for_unwired(monkeypatch):
    monkeypatch.setattr(
        "app.services.fulfillment_map._fetch_db_maps",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.services.provider_catalog.fetch_catalog_products",
        lambda **kwargs: builtin_catalog(),
    )
    # Brazil single-country with LatAm ladder step in builtin seed
    target = resolve_fulfillment_target(
        {
            "country": "Brazil",
            "data_total_gb": 3.0,
            "validity_days": 7,
            "metadata": {},
        },
        package={"data_total_gb": 3.0, "validity_days": 7},
    )
    assert target is not None
    assert target.provider == "telna"
    assert target.source.startswith("catalog:")
    assert target.provider_sku.startswith("67f6c112")


def test_builtin_seed_non_empty():
    assert len(builtin_catalog()) >= 10
