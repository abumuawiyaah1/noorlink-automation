"""
NoorLink breakage-fulfillment strategy.

Sell fixed bundles at retail; fulfill on WeConnect per-MB where eligible;
enforce allowance + expiry internally. Profit when customers do not use full allowance.

Policy modes (country_routing.json):
  - weconnect_breakage: virtual bundle on WeConnect PAYG rails
  - telna_fixed: Telna (or regional) fixed bundles — per-MB too expensive
  - access_fixed: eSIM Access — Saudi/Umrah policy
  - catalog_cascade: smart cascade from provider_catalog / plan maps
  - exclude: do not sell / block checkout
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from app.services.fulfillment_map import normalize_country_slug

logger = logging.getLogger(__name__)

PolicyMode = Literal[
    "weconnect_breakage",
    "telna_fixed",
    "access_fixed",
    "catalog_cascade",
    "exclude",
]

DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "breakage" / "country_routing.json"
)

# NoorLink standard sellable bundles (storefront ladder)
STANDARD_BUNDLES: List[Dict[str, Any]] = [
    {"key": "starter", "data_gb": 3, "validity_days": 7, "retail_usd": 19.99},
    {"key": "traveler", "data_gb": 10, "validity_days": 15, "retail_usd": 29.99},
    {"key": "heavy", "data_gb": 20, "validity_days": 30, "retail_usd": 44.99},
]

CARIBBEAN_BUNDLES: List[Dict[str, Any]] = [
    {"key": "basic", "data_gb": 1, "validity_days": 5, "retail_usd": 14.99},
    {"key": "standard", "data_gb": 3, "validity_days": 7, "retail_usd": 27.99},
    {"key": "plus", "data_gb": 5, "validity_days": 15, "retail_usd": 34.99},
    {"key": "premium", "data_gb": 10, "validity_days": 30, "retail_usd": 54.99},
]

WECONNECT_ESIM_USD = 1.60


@dataclass(frozen=True)
class CountryPolicy:
    country: str
    country_slug: str
    policy: PolicyMode
    policy_reason: str
    price_mb_usd: float
    price_gb_usd: float
    margin_10gb_100pct: float
    margin_10gb_50pct: float
    breakage_score: int
    region_hint: str


@dataclass(frozen=True)
class BreakageAllowance:
    """Virtual bundle enforced on top of WeConnect PAYG."""

    order_id: str
    allowance_mb: int
    valid_until_iso: str
    retail_usd: float
    country_slug: str
    plan_key: str


def _load_routing_file() -> Dict[str, Any]:
    if not DATA_PATH.is_file():
        logger.warning("Breakage routing file missing: %s", DATA_PATH)
        return {"countries": {}, "summary": {}}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def routing_payload() -> Dict[str, Any]:
    return _load_routing_file()


def reload_routing_cache() -> None:
    routing_payload.cache_clear()


def list_country_policies() -> List[CountryPolicy]:
    payload = routing_payload()
    out: List[CountryPolicy] = []
    for row in (payload.get("countries") or {}).values():
        out.append(
            CountryPolicy(
                country=row["country"],
                country_slug=row["country_slug"],
                policy=row["policy"],
                policy_reason=row["policy_reason"],
                price_mb_usd=float(row["price_mb_usd"]),
                price_gb_usd=float(row["price_gb_usd"]),
                margin_10gb_100pct=float(row["margin_10gb_100pct"]),
                margin_10gb_50pct=float(row["margin_10gb_50pct"]),
                breakage_score=int(row["breakage_score"]),
                region_hint=str(row.get("region_hint") or ""),
            )
        )
    return sorted(out, key=lambda p: p.country)


def _lookup_row(country: str) -> Optional[Dict[str, Any]]:
    slug = normalize_country_slug(country)
    countries = routing_payload().get("countries") or {}

    if slug in countries:
        return countries[slug]

    # Fuzzy: match display name
    needle = country.strip().lower()
    for row in countries.values():
        if row.get("country", "").lower() == needle:
            return row
    return None


def resolve_country_policy(country: str) -> CountryPolicy:
    row = _lookup_row(country)
    if row is None:
        return CountryPolicy(
            country=country,
            country_slug=normalize_country_slug(country),
            policy="catalog_cascade",
            policy_reason="No WeConnect row; default to catalog cascade.",
            price_mb_usd=0.0,
            price_gb_usd=0.0,
            margin_10gb_100pct=0.0,
            margin_10gb_50pct=0.0,
            breakage_score=0,
            region_hint="unknown",
        )
    return CountryPolicy(
        country=row["country"],
        country_slug=row["country_slug"],
        policy=row["policy"],
        policy_reason=row["policy_reason"],
        price_mb_usd=float(row["price_mb_usd"]),
        price_gb_usd=float(row["price_gb_usd"]),
        margin_10gb_100pct=float(row["margin_10gb_100pct"]),
        margin_10gb_50pct=float(row["margin_10gb_50pct"]),
        breakage_score=int(row["breakage_score"]),
        region_hint=str(row.get("region_hint") or ""),
    )


def is_breakage_eligible(country: str) -> bool:
    return resolve_country_policy(country).policy == "weconnect_breakage"


def is_checkout_blocked(country: str) -> bool:
    return resolve_country_policy(country).policy == "exclude"


def bundles_for_country(country: str) -> List[Dict[str, Any]]:
    policy = resolve_country_policy(country)
    if policy.region_hint == "caribbean" or policy.policy == "telna_fixed" and policy.region_hint == "caribbean":
        return CARIBBEAN_BUNDLES
    if normalize_country_slug(country).startswith("regional-caribbean"):
        return CARIBBEAN_BUNDLES
    if normalize_country_slug(country).startswith("regional-south-america"):
        return CARIBBEAN_BUNDLES
    return STANDARD_BUNDLES


def estimate_wholesale_usd(
    *,
    price_mb_usd: float,
    data_gb: float,
    usage_pct: float = 1.0,
    include_esim: bool = True,
) -> float:
    mb = data_gb * 1024 * usage_pct
    total = price_mb_usd * mb
    if include_esim:
        total += WECONNECT_ESIM_USD
    return round(total, 2)


def estimate_breakage_margin(
    *,
    country: str,
    data_gb: float,
    retail_usd: float,
    usage_pct: float,
) -> Dict[str, Any]:
    policy = resolve_country_policy(country)
    wholesale = estimate_wholesale_usd(
        price_mb_usd=policy.price_mb_usd,
        data_gb=data_gb,
        usage_pct=usage_pct,
    )
    margin = round(retail_usd - wholesale, 2)
    return {
        "country": policy.country_slug,
        "policy": policy.policy,
        "data_gb": data_gb,
        "usage_pct": usage_pct,
        "retail_usd": retail_usd,
        "wholesale_usd": wholesale,
        "margin_usd": margin,
        "margin_pct": round(margin / retail_usd, 4) if retail_usd else 0.0,
    }


def pilot_countries(limit: int = 25) -> List[CountryPolicy]:
    payload = routing_payload()
    rows = payload.get("summary", {}).get("pilot_countries_top_25") or []
    out: List[CountryPolicy] = []
    for row in rows[:limit]:
        out.append(
            CountryPolicy(
                country=row["country"],
                country_slug=row["country_slug"],
                policy=row["policy"],
                policy_reason=row["policy_reason"],
                price_mb_usd=float(row["price_mb_usd"]),
                price_gb_usd=float(row["price_gb_usd"]),
                margin_10gb_100pct=float(row["margin_10gb_100pct"]),
                margin_10gb_50pct=float(row["margin_10gb_50pct"]),
                breakage_score=int(row["breakage_score"]),
                region_hint=str(row.get("region_hint") or ""),
            )
        )
    return out


def strategy_summary() -> Dict[str, Any]:
    return dict(routing_payload().get("summary") or {})


def build_allowance(
    *,
    order_id: str,
    country: str,
    data_gb: float,
    validity_days: int,
    retail_usd: float,
    plan_key: str,
    valid_until_iso: str,
) -> BreakageAllowance:
    return BreakageAllowance(
        order_id=order_id,
        allowance_mb=int(round(float(data_gb) * 1024)),
        valid_until_iso=valid_until_iso,
        retail_usd=float(retail_usd),
        country_slug=normalize_country_slug(country),
        plan_key=plan_key,
    )


def fulfillment_mode_for_order(
    *,
    country: str,
    data_gb: Optional[float],
    validity_days: Optional[int],
    wants_topup: bool = False,
) -> Dict[str, Any]:
    """
    High-level routing decision for checkout / provision.
    Does not replace provider SKU lookup — informs which rail to prefer.
    """
    policy = resolve_country_policy(country)
    slug = normalize_country_slug(country)

    if wants_topup:
        return {
            "mode": "payg_topup",
            "provider_preference": ["weconnect", "citrus"],
            "policy": policy.policy,
            "country": slug,
            "note": "Top-up / Flex PAYG — balance-based, not virtual bundle.",
        }

    if policy.policy == "exclude":
        return {
            "mode": "blocked",
            "provider_preference": [],
            "policy": policy.policy,
            "country": slug,
            "note": policy.policy_reason,
        }

    if policy.policy == "access_fixed":
        return {
            "mode": "fixed_bundle",
            "provider_preference": ["esimaccess"],
            "policy": policy.policy,
            "country": slug,
            "note": policy.policy_reason,
        }

    if policy.policy == "telna_fixed":
        return {
            "mode": "fixed_bundle",
            "provider_preference": ["telna", "esimaccess"],
            "policy": policy.policy,
            "country": slug,
            "note": policy.policy_reason,
        }

    if policy.policy == "weconnect_breakage" and data_gb and validity_days:
        return {
            "mode": "virtual_bundle",
            "provider_preference": ["weconnect"],
            "policy": policy.policy,
            "country": slug,
            "allowance_mb": int(round(float(data_gb) * 1024)),
            "validity_days": int(validity_days),
            "note": (
                "Sell fixed bundle; provision WeConnect PAYG; enforce cap + expiry. "
                "Profit on unused allowance (breakage)."
            ),
        }

    return {
        "mode": "catalog_cascade",
        "provider_preference": ["telna", "esimaccess", "citrus"],
        "policy": policy.policy,
        "country": slug,
        "note": policy.policy_reason,
    }
