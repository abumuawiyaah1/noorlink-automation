"""
Virtual catalog → provider fulfillment resolution.

Looks up plan_fulfillment_map (DB), then falls back to built-in Saudi Access seeds
so local/dev can route SA before the migration is applied.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.api import supabase_repository as db
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Built-in Phase A seeds (same as migration). Used when the table is missing.
STATIC_SA_MAP: List[Dict[str, Any]] = [
    {
        "catalog_key": "sa-5gb-30",
        "country_code": "SA",
        "country_slug": "saudi-arabia",
        "data_gb": 5.0,
        "validity_days": 30,
        "provider": "esimaccess",
        "provider_sku": "CKH279",
        "provider_slug": "SA_5_30",
        "wholesale_cents": 722,
        "period_num": None,
        "is_active": True,
    },
    {
        "catalog_key": "sa-10gb-30",
        "country_code": "SA",
        "country_slug": "saudi-arabia",
        "data_gb": 10.0,
        "validity_days": 30,
        "provider": "esimaccess",
        "provider_sku": "CKH280",
        "provider_slug": "SA_10_30",
        "wholesale_cents": 1150,
        "period_num": None,
        "is_active": True,
    },
    {
        "catalog_key": "sa-20gb-30",
        "country_code": "SA",
        "country_slug": "saudi-arabia",
        "data_gb": 20.0,
        "validity_days": 30,
        "provider": "esimaccess",
        "provider_sku": "CKH800",
        "provider_slug": "SA_20_30",
        "wholesale_cents": 1950,
        "period_num": None,
        "is_active": True,
    },
    {
        "catalog_key": "sa-50gb-30",
        "country_code": "SA",
        "country_slug": "saudi-arabia",
        "data_gb": 50.0,
        "validity_days": 30,
        "provider": "esimaccess",
        "provider_sku": "CKH801",
        "provider_slug": "SA_50_30",
        "wholesale_cents": 5990,
        "period_num": None,
        "is_active": True,
    },
]


def _regional_fulfillment_seeds() -> List[Dict[str, Any]]:
    """Access SKUs declared on regional template plans."""
    try:
        from app.api.regional_inventory import (
            REGIONAL_PRODUCTS,
            REGIONAL_TEMPLATES,
            parse_data_total_gb,
            plan_data_label,
        )
    except Exception:
        return []

    seeds: List[Dict[str, Any]] = []
    for product_id, product in REGIONAL_PRODUCTS.items():
        template = REGIONAL_TEMPLATES.get(str(product.get("template_key")))
        if not template:
            continue
        for plan in (template.get("plans") or {}).values():
            if not isinstance(plan, dict) or plan.get("coming_soon"):
                continue
            fulfillment = plan.get("fulfillment")
            if not isinstance(fulfillment, dict):
                continue
            catalog_key = str(fulfillment.get("catalog_key") or "").strip()
            sku = str(fulfillment.get("provider_sku") or "").strip()
            if not catalog_key or not sku:
                continue
            data_label = plan_data_label(plan)
            seeds.append(
                {
                    "catalog_key": catalog_key,
                    "country_code": None,
                    "country_slug": product_id,
                    "data_gb": parse_data_total_gb(data_label),
                    "validity_days": int(plan.get("days") or 0) or None,
                    "provider": str(fulfillment.get("provider") or "esimaccess"),
                    "provider_sku": sku,
                    "provider_slug": fulfillment.get("provider_slug"),
                    "wholesale_cents": fulfillment.get("wholesale_cents"),
                    "period_num": None,
                    "is_active": True,
                }
            )
    return seeds


STATIC_FULFILLMENT_MAP: List[Dict[str, Any]] = STATIC_SA_MAP + _regional_fulfillment_seeds()


@dataclass(frozen=True)
class FulfillmentTarget:
    catalog_key: str
    provider: str
    provider_sku: str
    provider_slug: Optional[str] = None
    wholesale_cents: Optional[int] = None
    period_num: Optional[int] = None
    country_code: Optional[str] = None
    data_gb: Optional[float] = None
    validity_days: Optional[int] = None
    source: str = "map"


class FulfillmentMapError(Exception):
    """Cannot resolve or enforce a fulfillment target."""


def normalize_country_slug(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    aliases = {
        "saudi": "saudi-arabia",
        "saudi arabia": "saudi-arabia",
        "sa": "saudi-arabia",
        "umrah": "saudi-arabia",
        "hajj": "saudi-arabia",
        "middle east": "regional-middle-east",
        "middle-east": "regional-middle-east",
        "middle east regional": "regional-middle-east",
        "europe": "regional-europe",
        "europe regional": "regional-europe",
        "asia pacific": "regional-asia-pacific",
        "asia-pacific": "regional-asia-pacific",
        "asia": "regional-asia-pacific",
        "north america": "regional-north-america",
        "north-america": "regional-north-america",
        "africa": "regional-africa",
        "africa regional": "regional-africa",
        "caribbean": "regional-caribbean",
        "caribbean regional": "regional-caribbean",
        "west indies": "regional-caribbean",
        "south america": "regional-south-america",
        "south-america": "regional-south-america",
        "latin america": "regional-south-america",
        "latam": "regional-south-america",
        "global": "regional-global",
        "global regional": "regional-global",
        "worldwide": "regional-global",
        "australia": "australia",
        "mexico": "mexico",
        "uae": "uae",
        "united arab emirates": "uae",
        "united-arab-emirates": "uae",
    }
    if raw in aliases:
        return aliases[raw]
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def is_saudi_destination(country: Optional[str], country_code: Optional[str] = None) -> bool:
    if (country_code or "").strip().upper() == "SA":
        return True
    return normalize_country_slug(country) == "saudi-arabia"


# Country storefront pages that silently fulfill on Telna Middle East Bundle.
# Customers still see "UAE 10GB" / "Turkey 10GB" — not a regional promo.
# Saudi / Umrah stays on Access (never listed here).
ME_SILENT_TELNA_COUNTRY_SLUGS = frozenset(
    {
        "uae",
        "united-arab-emirates",
        "turkey",
        "egypt",
        "qatar",
        "kuwait",
        "bahrain",
        "oman",
        "jordan",
        "israel",
        "morocco",
        "tunisia",
        "cyprus",
    }
)

# Telna Middle East Bundle ladder (shared SKUs for silent country fulfillment).
ME_SILENT_TELNA_LADDER: List[Dict[str, Any]] = [
    {
        "data_gb": 1.0,
        "validity_days": 5,
        "provider_sku": "67f6c112d07af55d502bef7a",
        "provider_slug": "telna-me-1gb-5d",
        "wholesale_cents": 370,
        "key_suffix": "1gb-5",
    },
    {
        "data_gb": 3.0,
        "validity_days": 7,
        "provider_sku": "67f6c112d07af55d502bef79",
        "provider_slug": "telna-me-3gb-7d",
        "wholesale_cents": 1000,
        "key_suffix": "3gb-7",
    },
    {
        "data_gb": 5.0,
        "validity_days": 15,
        "provider_sku": "67f6c112d07af55d502bef7b",
        "provider_slug": "telna-me-5gb-15d",
        "wholesale_cents": 1620,
        "key_suffix": "5gb-15",
    },
    {
        "data_gb": 10.0,
        "validity_days": 30,
        "provider_sku": "67f6c112d07af55d502bef78",
        "provider_slug": "telna-me-10gb-30d",
        "wholesale_cents": 2800,
        "key_suffix": "10gb-30",
    },
]


def _me_silent_lookup_slugs(slug: str) -> List[str]:
    """Country slugs that should match silent ME Telna fulfillment map rows."""
    normalized = normalize_country_slug(slug)
    if normalized == "united-arab-emirates":
        normalized = "uae"
    if normalized in ME_SILENT_TELNA_COUNTRY_SLUGS or slug in ME_SILENT_TELNA_COUNTRY_SLUGS:
        return [normalized]
    return []


def _me_silent_static_seeds() -> List[Dict[str, Any]]:
    """Per-country Telna ME maps so UAE/Turkey/Egypt resolve without regional promo."""
    seeds: List[Dict[str, Any]] = []
    for country_slug in sorted(ME_SILENT_TELNA_COUNTRY_SLUGS):
        if country_slug == "united-arab-emirates":
            continue  # alias of uae
        for rung in ME_SILENT_TELNA_LADDER:
            seeds.append(
                {
                    "catalog_key": f"{country_slug}-{rung['key_suffix']}",
                    "country_code": None,
                    "country_slug": country_slug,
                    "data_gb": rung["data_gb"],
                    "validity_days": rung["validity_days"],
                    "provider": "telna",
                    "provider_sku": rung["provider_sku"],
                    "provider_slug": rung["provider_slug"],
                    "wholesale_cents": rung["wholesale_cents"],
                    "period_num": None,
                    "is_active": True,
                }
            )
    return seeds


STATIC_FULFILLMENT_MAP: List[Dict[str, Any]] = (
    STATIC_SA_MAP + _regional_fulfillment_seeds() + _me_silent_static_seeds()
)


def _row_to_target(row: Dict[str, Any], *, source: str) -> FulfillmentTarget:
    return FulfillmentTarget(
        catalog_key=str(row.get("catalog_key") or ""),
        provider=str(row.get("provider") or "").strip().lower(),
        provider_sku=str(row.get("provider_sku") or "").strip(),
        provider_slug=(str(row["provider_slug"]).strip() if row.get("provider_slug") else None),
        wholesale_cents=int(row["wholesale_cents"]) if row.get("wholesale_cents") is not None else None,
        period_num=int(row["period_num"]) if row.get("period_num") is not None else None,
        country_code=(str(row["country_code"]).upper() if row.get("country_code") else None),
        data_gb=float(row["data_gb"]) if row.get("data_gb") is not None else None,
        validity_days=int(row["validity_days"]) if row.get("validity_days") is not None else None,
        source=source,
    )


def _gb_close(a: Optional[float], b: Optional[float], tol: float = 0.05) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def _match_static(
    *,
    package_id: Optional[str],
    country: Optional[str],
    data_gb: Optional[float],
    validity_days: Optional[int],
) -> Optional[FulfillmentTarget]:
    slug = normalize_country_slug(country)
    if slug == "united-arab-emirates":
        slug = "uae"
    lookup_slugs = set(_me_silent_lookup_slugs(slug or ""))
    if slug:
        lookup_slugs.add(slug)
    for row in STATIC_FULFILLMENT_MAP:
        if not row.get("is_active"):
            continue
        row_slug = normalize_country_slug(row.get("country_slug"))
        if row_slug == "united-arab-emirates":
            row_slug = "uae"
        if lookup_slugs and row_slug and row_slug not in lookup_slugs:
            continue
        if data_gb is None or not _gb_close(data_gb, float(row["data_gb"])):
            continue
        if (
            validity_days is not None
            and int(row["validity_days"]) != int(validity_days)
        ):
            continue
        return _row_to_target(row, source="static")
    return None


def _fetch_db_maps() -> List[Dict[str, Any]]:
    try:
        client = db.get_supabase_client()
        result = (
            client.table("plan_fulfillment_map")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        return list(result.data or [])
    except Exception as exc:
        logger.info("plan_fulfillment_map unavailable (%s); using static seeds", exc)
        return []


def resolve_fulfillment_target(
    order_row: Dict[str, Any],
    *,
    package: Optional[Dict[str, Any]] = None,
    use_smart_cascade: bool = True,
) -> Optional[FulfillmentTarget]:
    """
    Resolve provider target for an order.
    Returns None when no map applies (caller uses global ESIM_PROVIDER).

    When use_smart_cascade is True (default), after the hand-wired map lookup we
    apply country → region → global matching from the provider catalog cache.
    Browse paths never call providers — cache only.
    """
    package_id = order_row.get("package_id") or (package or {}).get("id")
    country = order_row.get("country") or (package or {}).get("country")
    data_gb = order_row.get("data_total_gb")
    if data_gb is None and package:
        data_gb = package.get("data_total_gb")
    validity_days = None
    if package and package.get("validity_days") is not None:
        try:
            validity_days = int(package["validity_days"])
        except (TypeError, ValueError):
            validity_days = None
    if validity_days is None and order_row.get("validity_days") is not None:
        try:
            validity_days = int(order_row["validity_days"])
        except (TypeError, ValueError):
            validity_days = None

    metadata = order_row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    wants_topup = bool(
        metadata.get("wants_topup")
        or metadata.get("wantsTopUp")
        or order_row.get("wants_topup")
    )

    rows = _fetch_db_maps()
    mapped: Optional[FulfillmentTarget] = None
    if rows:
        if package_id:
            for row in rows:
                if str(row.get("package_id") or "") == str(package_id):
                    mapped = _row_to_target(row, source="db:package_id")
                    break

        if mapped is None:
            slug = normalize_country_slug(country)
            if slug == "united-arab-emirates":
                slug = "uae"
            lookup_slugs = set(_me_silent_lookup_slugs(slug or ""))
            if slug:
                lookup_slugs.add(slug)
            for row in rows:
                row_slug = normalize_country_slug(row.get("country_slug"))
                if row_slug == "united-arab-emirates":
                    row_slug = "uae"
                row_code = (row.get("country_code") or "").upper()
                country_ok = False
                if slug and row_slug and row_slug in lookup_slugs:
                    country_ok = True
                if is_saudi_destination(country) and row_code == "SA":
                    country_ok = True
                if not country_ok:
                    continue
                if data_gb is not None and row.get("data_gb") is not None:
                    if not _gb_close(float(data_gb), float(row["data_gb"])):
                        continue
                elif data_gb is None:
                    continue
                if (
                    validity_days is not None
                    and row.get("validity_days") is not None
                    and int(validity_days) != int(row["validity_days"])
                ):
                    continue
                mapped = _row_to_target(row, source="db:country_data")
                break

    if mapped is None:
        mapped = _match_static(
            package_id=str(package_id) if package_id else None,
            country=country,
            data_gb=float(data_gb) if data_gb is not None else None,
            validity_days=validity_days,
        )

    if not use_smart_cascade:
        return mapped

    try:
        from app.services.fulfillment_resolver import choose_fulfillment_target

        return choose_fulfillment_target(
            country=str(country or ""),
            data_gb=float(data_gb) if data_gb is not None else None,
            validity_days=validity_days,
            mapped=mapped,
            wants_topup=wants_topup,
        )
    except Exception as exc:
        logger.warning("Smart fulfillment cascade failed (%s); using map only", exc)
        return mapped


def enforce_saudi_access_policy(
    order_row: Dict[str, Any],
    target: Optional[FulfillmentTarget],
) -> None:
    """
    Restriction: Saudi / Umrah must fulfill via eSIM Access when enforcement is on.
    """
    settings = get_settings()
    if not settings.esim_access_enforce_saudi:
        return
    if not is_saudi_destination(order_row.get("country")):
        return

    if target is None:
        raise FulfillmentMapError(
            "Saudi Arabia orders require a plan_fulfillment_map entry "
            "(sa-5gb-30 / sa-10gb-30 / sa-20gb-30 / sa-50gb-30)."
        )
    if target.provider != "esimaccess":
        raise FulfillmentMapError(
            f"Saudi Arabia must use esimaccess, got provider={target.provider}"
        )
    if not settings.esim_access_access_code.strip():
        raise FulfillmentMapError(
            "Saudi Arabia fulfillment requires ESIM_ACCESS_ACCESS_CODE"
        )
