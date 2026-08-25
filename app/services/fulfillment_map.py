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
        "north america": "regional-north-america",
        "north-america": "regional-north-america",
        "africa": "regional-africa",
        "africa regional": "regional-africa",
        "caribbean": "regional-caribbean",
        "caribbean regional": "regional-caribbean",
        "west indies": "regional-caribbean",
        "south america": "regional-south-america",
        "south-america": "regional-south-america",
        "global": "regional-global",
        "global regional": "regional-global",
        "worldwide": "regional-global",
    }
    if raw in aliases:
        return aliases[raw]
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def is_saudi_destination(country: Optional[str], country_code: Optional[str] = None) -> bool:
    if (country_code or "").strip().upper() == "SA":
        return True
    return normalize_country_slug(country) == "saudi-arabia"


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
    for row in STATIC_FULFILLMENT_MAP:
        if not row.get("is_active"):
            continue
        if slug and row.get("country_slug") and slug != row["country_slug"]:
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
) -> Optional[FulfillmentTarget]:
    """
    Resolve provider target for an order.
    Returns None when no map applies (caller uses global ESIM_PROVIDER).
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

    rows = _fetch_db_maps()
    if rows:
        if package_id:
            for row in rows:
                if str(row.get("package_id") or "") == str(package_id):
                    return _row_to_target(row, source="db:package_id")

        slug = normalize_country_slug(country)
        for row in rows:
            row_slug = normalize_country_slug(row.get("country_slug"))
            row_code = (row.get("country_code") or "").upper()
            country_ok = False
            if slug and row_slug and slug == row_slug:
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
            return _row_to_target(row, source="db:country_data")

    return _match_static(
        package_id=str(package_id) if package_id else None,
        country=country,
        data_gb=float(data_gb) if data_gb is not None else None,
        validity_days=validity_days,
    )


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
