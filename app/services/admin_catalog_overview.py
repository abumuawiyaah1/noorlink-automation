"""Compare checkout catalog (esim_packages) vs browse catalog (mobile_data_plans)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from sqlalchemy import select

from app.api import supabase_repository as db
from app.db.engine import get_session_factory
from app.db.models import EsimPackage


def _normalize_country(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")


def _plan_key(country: str, data_gb: float, days: int) -> Tuple[str, float, int]:
    return (_normalize_country(country), round(float(data_gb), 2), int(days))


def build_catalog_overview(*, country_filter: str = "") -> Dict[str, Any]:
    """Return side-by-side catalog rows and mismatch flags."""
    factory = get_session_factory()
    checkout_plans: List[Dict[str, Any]] = []
    if factory is not None:
        with factory() as session:
            query = select(EsimPackage).order_by(EsimPackage.country, EsimPackage.sort_order)
            if country_filter.strip():
                needle = country_filter.strip().lower()
                query = query.where(EsimPackage.country.ilike(f"%{needle}%"))
            for pkg in session.scalars(query.limit(200)).all():
                if not pkg.is_active:
                    continue
                checkout_plans.append(
                    {
                        "country": pkg.country,
                        "name": pkg.name,
                        "data_gb": float(pkg.data_total_gb) if pkg.data_total_gb else None,
                        "validity_days": pkg.validity_days,
                        "price_cents": pkg.price_cents,
                        "on_sale": pkg.is_active and pkg.admin_approved,
                        "slug": pkg.slug,
                        "source": "checkout",
                    }
                )

    browse_plans: List[Dict[str, Any]] = []
    try:
        client = db.get_supabase_client()
        query = client.table("mobile_data_plans").select("*").limit(500)
        if country_filter.strip():
            needle = country_filter.strip().lower()
            result = query.execute()
            rows = [
                row
                for row in (result.data or [])
                if needle in str(row.get("country_id") or "").lower()
                or needle in str(row.get("country_name") or "").lower()
            ]
        else:
            result = query.execute()
            rows = result.data or []

        for row in rows:
            if row.get("is_active", row.get("active", True)) is False:
                continue
            country = str(row.get("country_name") or row.get("country_id") or "")
            browse_plans.append(
                {
                    "country": country,
                    "name": row.get("name") or row.get("plan_name") or "",
                    "data_gb": float(row.get("data_gb") or 0),
                    "validity_days": int(row.get("duration_days") or row.get("validity_days") or 0),
                    "price_cents": int(row.get("price_cents") or 0),
                    "on_sale": True,
                    "slug": row.get("id") or row.get("slug"),
                    "source": "browse",
                }
            )
    except Exception:
        browse_plans = []

    checkout_keys = {
        _plan_key(p["country"], p["data_gb"] or 0, p["validity_days"] or 0): p
        for p in checkout_plans
        if p.get("data_gb") is not None
    }
    browse_keys = {
        _plan_key(p["country"], p["data_gb"] or 0, p["validity_days"] or 0): p
        for p in browse_plans
        if p.get("data_gb")
    }

    mismatches: List[Dict[str, Any]] = []
    all_keys = set(checkout_keys) | set(browse_keys)
    for key in sorted(all_keys):
        country, data_gb, days = key
        in_checkout = key in checkout_keys
        in_browse = key in browse_keys
        if in_checkout and in_browse:
            continue
        mismatches.append(
            {
                "country": country,
                "data_gb": data_gb,
                "validity_days": days,
                "checkout": in_checkout,
                "browse": in_browse,
                "message": (
                    "On browse page only — customers see it but checkout may use a different plan"
                    if in_browse and not in_checkout
                    else "Checkout only — not shown on browse plans page"
                ),
            }
        )

    return {
        "checkout_count": len(checkout_plans),
        "browse_count": len(browse_plans),
        "mismatch_count": len(mismatches),
        "checkout_plans": checkout_plans[:50],
        "browse_plans": browse_plans[:50],
        "mismatches": mismatches[:100],
        "country_filter": country_filter,
    }
