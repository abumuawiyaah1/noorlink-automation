"""Server-side catalog price resolution for checkout (never trust client price)."""

from __future__ import annotations

from typing import Any, Dict

from app.api import supabase_repository as db
from app.api.supabase_repository import ManagedPackagePriceMismatchError, SupabaseRepositoryError


class CheckoutPricingError(Exception):
    """Raised when checkout cannot resolve a sellable catalog price."""


def resolve_catalog_plan(*, package_id: str, country: str) -> Dict[str, Any]:
    pid = (package_id or "").strip()
    if not pid:
        raise CheckoutPricingError("packageId is required. Go back and select a plan.")

    try:
        catalog = db.get_plans_by_country(country)
    except SupabaseRepositoryError as exc:
        raise CheckoutPricingError("Plans catalog is temporarily unavailable.") from exc

    plans = catalog.get("plans") or []
    match = next((p for p in plans if str(p.get("id")) == pid), None)

    if not match:
        country_id = str(catalog.get("country_id") or "").strip()
        if country_id and country_id != country.strip():
            try:
                alt = db.get_plans_by_country(country_id)
                plans = alt.get("plans") or []
                match = next((p for p in plans if str(p.get("id")) == pid), None)
            except SupabaseRepositoryError:
                pass

    if not match and not db._is_synthetic_plan_id(pid):
        client = db.get_supabase_client()
        result = (
            client.table("esim_packages")
            .select("id, name, price_cents, data_total_gb, validity_days")
            .eq("id", pid)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            price_cents = row.get("price_cents")
            if price_cents is None:
                raise CheckoutPricingError("Unknown package.")
            return {
                "id": pid,
                "name": row.get("name") or "Travel eSIM",
                "price": round(int(price_cents) / 100.0, 2),
                "data_gb": row.get("data_total_gb"),
                "duration_days": row.get("validity_days"),
            }

    if not match:
        raise CheckoutPricingError(
            "Plan not found in our catalog. Go back and select a plan again."
        )

    if match.get("coming_soon"):
        raise CheckoutPricingError("This plan is not available for purchase yet.")

    return match


def authoritative_checkout_price(
    *,
    package_id: str,
    country: str,
    client_price: float | None = None,
) -> float:
    plan = resolve_catalog_plan(package_id=package_id, country=country)
    price = float(plan["price"])
    if client_price is not None and client_price > 0:
        client_cents = int(round(float(client_price) * 100))
        server_cents = int(round(price * 100))
        if client_cents != server_cents:
            raise ManagedPackagePriceMismatchError(
                f"Price mismatch for plan '{package_id}': "
                f"expected {server_cents} cents, got {client_cents} cents"
            )
    return price
