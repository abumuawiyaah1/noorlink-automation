"""
Provider catalog warehouse — sync + match helpers.

Sellable catalog stays on NoorLink (4-plan ladders). This module only stores
upstream SKUs so checkout can resolve country → region → global without
calling providers during browse.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.api import supabase_repository as db

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(
    r"^(?P<label>.+?)\s*[-–]\s*(?P<data>\d+(?:\.\d+)?)\s*GB\s+(?P<days>\d+)\s*Days?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CatalogProduct:
    provider: str
    provider_sku: str
    name: str
    scope: str  # country | regional | global
    country_slugs: Tuple[str, ...]
    data_gb: Optional[float]
    validity_days: Optional[int]
    wholesale_cents: Optional[int]


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")


def parse_product_name(name: str) -> Dict[str, Any]:
    """Parse Telna-style names like 'Chile-3 GB 7 Days' or 'Latin America Bundle-1 GB 5 Days'."""
    raw = (name or "").strip()
    match = _NAME_RE.match(raw)
    if not match:
        return {
            "label": raw,
            "data_gb": None,
            "validity_days": None,
            "scope": "country",
            "country_slugs": tuple(),
        }

    label = match.group("label").strip()
    data_gb = float(match.group("data"))
    validity_days = int(match.group("days"))
    label_l = label.lower()

    if "global" in label_l:
        scope = "global"
        slugs: Tuple[str, ...] = ("global",)
    elif "bundle" in label_l or "latin america" in label_l or "caribbean" in label_l:
        scope = "regional"
        slugs = _regional_slugs_for_label(label)
    elif "africa" in label_l and "bundle" in label_l:
        scope = "regional"
        slugs = _regional_slugs_for_label(label)
    elif "europe" in label_l or "north america" in label_l or "asia" in label_l:
        scope = "regional"
        slugs = _regional_slugs_for_label(label)
    else:
        scope = "country"
        # Strip trailing " Bundle - Lite" noise
        country_label = re.sub(
            r"\s+bundle.*$", "", label, flags=re.IGNORECASE
        ).strip()
        slugs = (_slugify(country_label),) if country_label else tuple()

    return {
        "label": label,
        "data_gb": data_gb,
        "validity_days": validity_days,
        "scope": scope,
        "country_slugs": slugs,
    }


def _regional_slugs_for_label(label: str) -> Tuple[str, ...]:
    """Map bundle label → destination slugs from REGIONAL_PRODUCTS when possible."""
    try:
        from app.api.regional_inventory import REGIONAL_PRODUCTS, COUNTRY_TEMPLATE_HINTS
    except Exception:
        REGIONAL_PRODUCTS = {}
        COUNTRY_TEMPLATE_HINTS = {}

    label_l = label.lower()
    template_key = None
    if "latin america" in label_l or "south america" in label_l:
        template_key = "south-america"
    elif "caribbean" in label_l:
        template_key = "caribbean"
    elif "africa" in label_l:
        template_key = "africa"
    elif "europe" in label_l:
        template_key = "europe"
    elif "north america" in label_l:
        template_key = "north-america"
    elif "middle east" in label_l:
        template_key = "middle-east"
    elif "asia" in label_l:
        template_key = "asia-pacific"

    slugs: List[str] = []
    if template_key:
        for product in REGIONAL_PRODUCTS.values():
            if product.get("template_key") == template_key:
                for name in product.get("countries") or []:
                    slugs.append(_slugify(str(name)))
                break
        for country_slug, (_display, tmpl) in COUNTRY_TEMPLATE_HINTS.items():
            if tmpl == template_key and country_slug not in slugs:
                slugs.append(country_slug)
        slugs.append(f"regional-{template_key}")

    return tuple(dict.fromkeys(slugs))


# Portal-sourced seeds (Telna). Used when DB empty / API disallowed.
BUILTIN_TELNA_SEED: List[Dict[str, Any]] = [
    # Caribbean
    {"provider_sku": "690b2b5f7aff111b7539f7c4", "name": "Caribbean Bundle-1 GB 5 Days", "wholesale_cents": 650},
    {"provider_sku": "690b2b5e7aff111b7539f7bd", "name": "Caribbean Bundle-3 GB 7 Days", "wholesale_cents": 1600},
    {"provider_sku": "690b2b5e7aff111b7539f7be", "name": "Caribbean Bundle-5 GB 15 Days", "wholesale_cents": 2300},
    {"provider_sku": "690b2b5f7aff111b7539f7c3", "name": "Caribbean Bundle-10 GB 30 Days", "wholesale_cents": 4000},
    # Latin America (17-country)
    {"provider_sku": "67f6c112d07af55d502bef74", "name": "Latin America Bundle-1 GB 5 Days", "wholesale_cents": 330},
    {"provider_sku": "67f6c112d07af55d502bef76", "name": "Latin America Bundle-3 GB 7 Days", "wholesale_cents": 850},
    {"provider_sku": "67f6c112d07af55d502bef77", "name": "Latin America Bundle-5 GB 15 Days", "wholesale_cents": 1400},
    {"provider_sku": "67f6c112d07af55d502bef75", "name": "Latin America Bundle-10 GB 30 Days", "wholesale_cents": 2500},
    # Global
    {"provider_sku": "690b2b5f7aff111b7539f7d7", "name": "Global Bundle-1 GB 5 Days", "wholesale_cents": 775},
    {"provider_sku": "690b2b5f7aff111b7539f7d2", "name": "Global Bundle-3 GB 7 Days", "wholesale_cents": 2150},
    # Africa regional
    {"provider_sku": "690b2b5f7aff111b7539f7d6", "name": "Africa Bundle-5 GB 15 Days", "wholesale_cents": 3025},
    {"provider_sku": "690b2b5f7aff111b7539f7d8", "name": "Africa Bundle-10 GB 30 Days", "wholesale_cents": 5525},
    # North America regional
    {"provider_sku": "66b5db0b899f794eccc80043", "name": "North America Bundle-3 GB 7 Days", "wholesale_cents": 660},
    {"provider_sku": "66b5db0b899f794eccc80016", "name": "North America Bundle-10 GB 30 Days", "wholesale_cents": 1800},
]


def seed_row_to_product(row: Dict[str, Any], *, provider: str = "telna") -> CatalogProduct:
    parsed = parse_product_name(str(row.get("name") or ""))
    wholesale = row.get("wholesale_cents")
    if wholesale is None and row.get("unit_cost_usd") is not None:
        wholesale = int(round(float(row["unit_cost_usd"]) * 100))
    return CatalogProduct(
        provider=provider,
        provider_sku=str(row["provider_sku"]),
        name=str(row.get("name") or ""),
        scope=str(parsed["scope"]),
        country_slugs=tuple(parsed["country_slugs"]),
        data_gb=parsed["data_gb"],
        validity_days=parsed["validity_days"],
        wholesale_cents=int(wholesale) if wholesale is not None else None,
    )


def builtin_catalog() -> List[CatalogProduct]:
    return [seed_row_to_product(row) for row in BUILTIN_TELNA_SEED]


def product_to_row(product: CatalogProduct) -> Dict[str, Any]:
    return {
        "provider": product.provider,
        "provider_sku": product.provider_sku,
        "name": product.name,
        "scope": product.scope,
        "country_slugs": list(product.country_slugs),
        "data_gb": product.data_gb,
        "validity_days": product.validity_days,
        "wholesale_cents": product.wholesale_cents,
        "is_active": True,
    }


def upsert_catalog_products(products: Sequence[CatalogProduct]) -> int:
    if not products:
        return 0
    client = db.get_supabase_client()
    payload = [product_to_row(p) for p in products]
    try:
        client.table("provider_catalog_products").upsert(
            payload,
            on_conflict="provider,provider_sku",
        ).execute()
        return len(payload)
    except Exception as exc:
        logger.exception("provider_catalog_products upsert failed: %s", exc)
        raise db.SupabaseRepositoryError(str(exc)) from exc


def fetch_catalog_products(*, provider: Optional[str] = None) -> List[CatalogProduct]:
    """Load active catalog from DB; fall back to builtin Telna seed."""
    try:
        client = db.get_supabase_client()
        query = (
            client.table("provider_catalog_products")
            .select(
                "provider, provider_sku, name, scope, country_slugs, "
                "data_gb, validity_days, wholesale_cents, is_active"
            )
            .eq("is_active", True)
        )
        if provider:
            query = query.eq("provider", provider)
        result = query.execute()
        rows = list(result.data or [])
        if rows:
            out: List[CatalogProduct] = []
            for row in rows:
                slugs = row.get("country_slugs") or []
                if not isinstance(slugs, list):
                    slugs = []
                out.append(
                    CatalogProduct(
                        provider=str(row.get("provider") or ""),
                        provider_sku=str(row.get("provider_sku") or ""),
                        name=str(row.get("name") or ""),
                        scope=str(row.get("scope") or "country"),
                        country_slugs=tuple(str(s) for s in slugs),
                        data_gb=float(row["data_gb"]) if row.get("data_gb") is not None else None,
                        validity_days=int(row["validity_days"])
                        if row.get("validity_days") is not None
                        else None,
                        wholesale_cents=int(row["wholesale_cents"])
                        if row.get("wholesale_cents") is not None
                        else None,
                    )
                )
            return out
    except Exception as exc:
        logger.info("provider_catalog_products unavailable (%s); using builtin seed", exc)

    products = builtin_catalog()
    if provider:
        products = [p for p in products if p.provider == provider]
    return products


def normalize_telna_api_product(raw: Dict[str, Any]) -> Optional[CatalogProduct]:
    from app.services.telna import normalize_product

    norm = normalize_product(raw)
    sku = str(norm.get("id") or "").strip()
    name = str(norm.get("name") or "").strip()
    if not sku or not name:
        return None

    parsed = parse_product_name(name)
    data_gb = parsed["data_gb"]
    if data_gb is None and norm.get("data_mb") is not None:
        data_gb = round(float(norm["data_mb"]) / 1024.0, 4)

    validity_days = parsed["validity_days"]
    if validity_days is None and norm.get("duration_days") is not None:
        validity_days = int(round(float(norm["duration_days"])))

    countries = norm.get("supported_countries") or []
    slugs = tuple(_slugify(str(c)) for c in countries if str(c).strip())
    scope = parsed["scope"]
    if not slugs and parsed["country_slugs"]:
        slugs = parsed["country_slugs"]
    if scope == "country" and not slugs and parsed["country_slugs"]:
        slugs = parsed["country_slugs"]
    if len(slugs) > 1 and scope == "country":
        scope = "regional"

    wholesale = None
    if norm.get("unit_cost_usd") is not None:
        wholesale = int(round(float(norm["unit_cost_usd"]) * 100))

    return CatalogProduct(
        provider="telna",
        provider_sku=sku,
        name=name,
        scope=scope,
        country_slugs=slugs,
        data_gb=data_gb,
        validity_days=validity_days,
        wholesale_cents=wholesale,
    )


async def sync_telna_catalog(*, use_builtin_on_failure: bool = True) -> Dict[str, Any]:
    """
    Refresh Telna rows in provider_catalog_products.
    Browse path never calls this — cron/admin only.
    """
    from app.services.telna import TelnaAuthError, TelnaClient, TelnaError

    synced = 0
    source = "api"
    try:
        async with TelnaClient() as client:
            raw_products = await client.list_products(count=500)
        products: List[CatalogProduct] = []
        for raw in raw_products:
            if not isinstance(raw, dict):
                continue
            item = normalize_telna_api_product(raw)
            if item:
                products.append(item)
        if products:
            synced = upsert_catalog_products(products)
            return {
                "success": True,
                "source": source,
                "synced": synced,
                "provider": "telna",
            }
    except (TelnaAuthError, TelnaError) as exc:
        logger.warning("Telna catalog sync via API failed: %s", exc)
        if not use_builtin_on_failure:
            return {
                "success": False,
                "source": "api",
                "synced": 0,
                "error": str(exc),
                "provider": "telna",
            }
    except Exception as exc:
        logger.warning("Telna catalog sync unexpected failure: %s", exc)
        if not use_builtin_on_failure:
            return {
                "success": False,
                "source": "api",
                "synced": 0,
                "error": str(exc),
                "provider": "telna",
            }

    source = "builtin"
    try:
        synced = upsert_catalog_products(builtin_catalog())
    except Exception as exc:
        # DB may be unavailable in tests — still report builtin ready in memory
        logger.info("Builtin catalog upsert skipped: %s", exc)
        synced = len(BUILTIN_TELNA_SEED)
        return {
            "success": True,
            "source": source,
            "synced": synced,
            "persisted": False,
            "provider": "telna",
            "message": "Using in-memory builtin seed (DB upsert unavailable).",
        }

    return {
        "success": True,
        "source": source,
        "synced": synced,
        "persisted": True,
        "provider": "telna",
        "message": "API unavailable or empty; seeded builtin Telna portal SKUs.",
    }


def _coverage_ok(product: CatalogProduct, country_slug: str) -> bool:
    if product.scope == "global":
        return True
    slug = _slugify(country_slug)
    if slug in product.country_slugs:
        return True
    # Regional product id style
    if any(s.startswith("regional-") and slug.startswith("regional-") for s in product.country_slugs):
        return slug in product.country_slugs
    return False


def rank_matches(
    products: Iterable[CatalogProduct],
    *,
    country_slug: str,
    data_gb: float,
    validity_days: int,
    scope: Optional[str] = None,
) -> List[CatalogProduct]:
    """
    Prefer exact GB/days, then same GB + longer days, then more GB + enough days.
    Sort by wholesale ascending (missing wholesale last).
    """
    slug = _slugify(country_slug)
    candidates: List[Tuple[int, int, CatalogProduct]] = []
    for product in products:
        if scope and product.scope != scope:
            continue
        if not _coverage_ok(product, slug):
            continue
        if product.data_gb is None or product.validity_days is None:
            continue
        if float(product.data_gb) + 1e-9 < float(data_gb):
            continue
        if int(product.validity_days) < int(validity_days):
            continue

        exact_data = abs(float(product.data_gb) - float(data_gb)) <= 0.05
        exact_days = int(product.validity_days) == int(validity_days)
        if exact_data and exact_days:
            tier = 0
        elif exact_data:
            tier = 1
        else:
            tier = 2
        wholesale = product.wholesale_cents if product.wholesale_cents is not None else 10**12
        candidates.append((tier, wholesale, product))

    candidates.sort(key=lambda item: (item[0], item[1], item[2].provider_sku))
    return [item[2] for item in candidates]
