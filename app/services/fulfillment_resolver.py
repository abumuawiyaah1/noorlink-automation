"""
Smart fulfillment: country → region → global from provider catalog cache.

Storefront still shows NoorLink's fixed 4-plan ladder. This resolver only picks
the upstream SKU at checkout/provision time (no browse-time provider calls).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.services.fulfillment_map import (
    FulfillmentTarget,
    is_saudi_destination,
    normalize_country_slug,
)
from app.services.provider_catalog import (
    CatalogProduct,
    fetch_catalog_products,
    rank_matches,
)

logger = logging.getLogger(__name__)


def _template_key_for_country(country_slug: str) -> Optional[str]:
    try:
        from app.api.regional_inventory import resolve_country_identity
    except Exception:
        return None
    _name, template_key = resolve_country_identity(country_slug)
    return template_key


def _regional_product_id(template_key: str) -> str:
    return f"regional-{template_key}"


def _product_to_target(product: CatalogProduct, *, source: str) -> FulfillmentTarget:
    return FulfillmentTarget(
        catalog_key=f"auto-{product.provider}-{product.provider_sku}",
        provider=product.provider,
        provider_sku=product.provider_sku,
        provider_slug=None,
        wholesale_cents=product.wholesale_cents,
        period_num=None,
        country_code=None,
        data_gb=product.data_gb,
        validity_days=product.validity_days,
        source=source,
    )


def _cheaper(a: FulfillmentTarget, b: FulfillmentTarget) -> FulfillmentTarget:
    aw = a.wholesale_cents if a.wholesale_cents is not None else 10**12
    bw = b.wholesale_cents if b.wholesale_cents is not None else 10**12
    return a if aw <= bw else b


def resolve_cascade(
    *,
    country: str,
    data_gb: float,
    validity_days: int,
    products: Optional[List[CatalogProduct]] = None,
) -> Optional[FulfillmentTarget]:
    """
    Prefer country SKU, then regional covering the country, then global.
    Within each step pick lowest wholesale among acceptable matches.
    """
    slug = normalize_country_slug(country)
    if not slug or data_gb is None or validity_days is None:
        return None

    catalog = products if products is not None else fetch_catalog_products()
    if not catalog:
        return None

    # 1) Single-country
    country_hits = rank_matches(
        catalog,
        country_slug=slug,
        data_gb=float(data_gb),
        validity_days=int(validity_days),
        scope="country",
    )
    if country_hits:
        return _product_to_target(country_hits[0], source="catalog:country")

    # 2) Regional covering country
    template_key = _template_key_for_country(slug)
    regional_slug = _regional_product_id(template_key) if template_key else slug
    regional_hits = rank_matches(
        catalog,
        country_slug=slug,
        data_gb=float(data_gb),
        validity_days=int(validity_days),
        scope="regional",
    )
    # Also try matching against regional-* slug coverage lists
    if not regional_hits and template_key:
        regional_hits = rank_matches(
            catalog,
            country_slug=regional_slug,
            data_gb=float(data_gb),
            validity_days=int(validity_days),
            scope="regional",
        )
    if regional_hits:
        return _product_to_target(regional_hits[0], source="catalog:regional")

    # 3) Global
    global_hits = rank_matches(
        catalog,
        country_slug="global",
        data_gb=float(data_gb),
        validity_days=int(validity_days),
        scope="global",
    )
    if global_hits:
        return _product_to_target(global_hits[0], source="catalog:global")

    return None


def citrus_topup_target(
    *,
    data_gb: Optional[float],
    validity_days: Optional[int],
    wholesale_cents: Optional[int] = None,
) -> FulfillmentTarget:
    return FulfillmentTarget(
        catalog_key="topup-citrus",
        provider="citrus",
        provider_sku="citrus-payg",
        provider_slug="citrus-payg",
        wholesale_cents=wholesale_cents,
        data_gb=data_gb,
        validity_days=validity_days,
        source="policy:topup",
    )


def is_regional_destination(country: Optional[str]) -> bool:
    slug = normalize_country_slug(country)
    return slug.startswith("regional-") or slug in {
        "europe",
        "caribbean",
        "africa",
        "global",
        "worldwide",
    }


def choose_fulfillment_target(
    *,
    country: str,
    data_gb: Optional[float],
    validity_days: Optional[int],
    mapped: Optional[FulfillmentTarget],
    wants_topup: bool = False,
    products: Optional[List[CatalogProduct]] = None,
) -> Optional[FulfillmentTarget]:
    """
    Final policy:
    - Saudi stays on Access map (caller still enforces)
    - Top-up preference → Citrus when configured
    - Explicit regional purchases keep strategic map when present
    - Single-country: cascade catalog; keep map if cheaper/equal and present
    """
    settings = get_settings()
    slug = normalize_country_slug(country)

    if wants_topup and (settings.citrus_api_key or "").strip():
        if not is_saudi_destination(country):
            return citrus_topup_target(
                data_gb=data_gb,
                validity_days=validity_days,
                wholesale_cents=mapped.wholesale_cents if mapped else None,
            )

    # Buyer already selected a regional/global product — prefer hand-wired map
    if mapped and is_regional_destination(country):
        return mapped

    if data_gb is None or validity_days is None:
        return mapped

    cascade = resolve_cascade(
        country=slug,
        data_gb=float(data_gb),
        validity_days=int(validity_days),
        products=products,
    )

    if mapped is None:
        return cascade
    if cascade is None:
        return mapped

    # Silent profit: prefer cheaper wholesale between map and cascade
    return _cheaper(mapped, cascade)


def explain_fulfillment(
    *,
    country: str,
    data_gb: float,
    validity_days: int,
    wants_topup: bool = False,
) -> Dict[str, Any]:
    """Debug helper for admin /api/fulfillment/resolve."""
    from app.services.breakage_strategy import (
        estimate_breakage_margin,
        fulfillment_mode_for_order,
        resolve_country_policy,
    )
    from app.services.fulfillment_map import resolve_fulfillment_target

    probe = {
        "country": country,
        "data_total_gb": data_gb,
        "validity_days": validity_days,
        "metadata": {"wants_topup": wants_topup},
    }
    package = {"validity_days": validity_days, "data_total_gb": data_gb}
    mapped = resolve_fulfillment_target(
        probe, package=package, use_smart_cascade=False
    )
    chosen = choose_fulfillment_target(
        country=country,
        data_gb=data_gb,
        validity_days=validity_days,
        mapped=mapped,
        wants_topup=wants_topup,
    )
    policy = resolve_country_policy(country)
    mode = fulfillment_mode_for_order(
        country=country,
        data_gb=data_gb,
        validity_days=validity_days,
        wants_topup=wants_topup,
    )
    retail_guess = 29.99 if data_gb >= 10 else 19.99 if data_gb >= 3 else 14.99
    return {
        "country": normalize_country_slug(country),
        "data_gb": data_gb,
        "validity_days": validity_days,
        "wants_topup": wants_topup,
        "mapped": mapped.__dict__ if mapped else None,
        "chosen": chosen.__dict__ if chosen else None,
        "ladder": "country → regional → global",
        "breakage_policy": {
            "mode": policy.policy,
            "reason": policy.policy_reason,
            "price_gb_usd": policy.price_gb_usd,
            "breakage_score": policy.breakage_score,
        },
        "fulfillment_mode": mode,
        "breakage_margin_estimates": {
            "at_50pct_usage": estimate_breakage_margin(
                country=country,
                data_gb=data_gb,
                retail_usd=retail_guess,
                usage_pct=0.5,
            ),
            "at_100pct_usage": estimate_breakage_margin(
                country=country,
                data_gb=data_gb,
                retail_usd=retail_guess,
                usage_pct=1.0,
            ),
        },
    }
