"""Admin catalog helpers — plans, prices, provider fulfillment maps."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import EsimPackage, PlanFulfillmentMap

KNOWN_FULFILLMENT_PROVIDERS: Set[str] = {
    "citrus",
    "esimaccess",
    "telna",
    "simbase",
    "mock",
}

PRICE_CHANGE_APPROVAL_THRESHOLD_PCT = 10


class AdminCatalogError(Exception):
    """Catalog admin operation failed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_provider(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def is_known_provider(provider: Optional[str]) -> bool:
    return normalize_provider(provider) in KNOWN_FULFILLMENT_PROVIDERS


def price_change_requires_approval(old_cents: int, new_cents: int) -> bool:
    if old_cents <= 0:
        return False
    delta_pct = abs(new_cents - old_cents) / old_cents * 100
    return delta_pct > PRICE_CHANGE_APPROVAL_THRESHOLD_PCT


def package_sale_status(
    *,
    is_active: bool,
    admin_approved: bool,
    pending_price_cents: Optional[int] = None,
) -> str:
    if pending_price_cents is not None:
        return "Price pending approval"
    if not admin_approved:
        return "Pending approval"
    if not is_active:
        return "Off sale"
    return "On sale"


def validate_package_payload(data: Dict[str, Any], *, is_create: bool) -> Dict[str, Any]:
    cleaned = dict(data)

    slug = str(cleaned.get("slug") or "").strip().lower()
    if not slug:
        raise AdminCatalogError("Slug is required.")
    cleaned["slug"] = slug

    name = str(cleaned.get("name") or "").strip()
    if not name:
        raise AdminCatalogError("Plan name is required.")
    cleaned["name"] = name

    country = str(cleaned.get("country") or "").strip()
    if not country:
        raise AdminCatalogError("Country is required.")
    cleaned["country"] = country

    price_cents = int(cleaned.get("price_cents") or 0)
    if price_cents <= 0:
        raise AdminCatalogError("Price must be greater than zero.")
    cleaned["price_cents"] = price_cents

    cleaned["currency"] = (str(cleaned.get("currency") or "USD").strip().upper() or "USD")[:3]
    cleaned["data_label"] = str(cleaned.get("data_label") or "10GB").strip() or "10GB"
    cleaned["validity_days"] = max(1, int(cleaned.get("validity_days") or 15))
    cleaned["sort_order"] = int(cleaned.get("sort_order") or 0)
    cleaned["region"] = str(cleaned.get("region") or "Americas").strip() or "Americas"

    data_gb = cleaned.get("data_total_gb")
    if data_gb in ("", None):
        cleaned["data_total_gb"] = None
    else:
        cleaned["data_total_gb"] = Decimal(str(data_gb))

    if is_create:
        cleaned.setdefault("is_active", False)
        cleaned.setdefault("is_managed", True)
        cleaned.setdefault("is_featured", False)

    return cleaned


def apply_package_approval_rules(
    validated: Dict[str, Any],
    *,
    is_create: bool,
    editor_is_admin: bool,
    editor_username: str,
    existing: Optional[Any] = None,
) -> Dict[str, Any]:
    """Approval for new plans and significant price changes."""
    new_price = int(validated["price_cents"])
    pending_price: Optional[int] = None

    if not is_create and existing is not None:
        old_price = int(getattr(existing, "price_cents", 0) or 0)
        existing_pending = getattr(existing, "pending_price_cents", None)
        if (
            not editor_is_admin
            and old_price > 0
            and new_price != old_price
            and price_change_requires_approval(old_price, new_price)
        ):
            pending_price = new_price
            validated["price_cents"] = old_price
        elif editor_is_admin:
            validated["pending_price_cents"] = None
        elif existing_pending is not None and new_price == old_price:
            pending_price = existing_pending
    elif editor_is_admin:
        validated["pending_price_cents"] = None

    if pending_price is not None:
        validated["pending_price_cents"] = pending_price

    if is_create:
        if editor_is_admin:
            validated["admin_approved"] = True
            validated["admin_approved_by"] = editor_username
            validated["admin_approved_at"] = _utc_now()
            validated["is_active"] = bool(validated.get("is_active", True))
        else:
            validated["admin_approved"] = False
            validated["admin_approved_by"] = None
            validated["admin_approved_at"] = None
            validated["is_active"] = False
        return validated

    if editor_is_admin:
        validated["admin_approved"] = True
        validated["admin_approved_by"] = editor_username
        validated["admin_approved_at"] = _utc_now()
        return validated

    if getattr(existing, "admin_approved", False) and pending_price is None:
        validated["admin_approved"] = True
        validated["admin_approved_by"] = getattr(existing, "admin_approved_by", None)
        validated["admin_approved_at"] = getattr(existing, "admin_approved_at", None)
    else:
        if pending_price is None and not getattr(existing, "admin_approved", False):
            validated["admin_approved"] = False
            validated["admin_approved_by"] = None
            validated["admin_approved_at"] = None

    return validated


def validate_fulfillment_map_payload(data: Dict[str, Any], *, is_create: bool) -> Dict[str, Any]:
    cleaned = dict(data)

    catalog_key = str(cleaned.get("catalog_key") or "").strip()
    if not catalog_key:
        raise AdminCatalogError("Catalog key is required.")
    cleaned["catalog_key"] = catalog_key

    provider = normalize_provider(str(cleaned.get("provider") or ""))
    if not provider:
        raise AdminCatalogError("Provider is required.")
    cleaned["provider"] = provider

    provider_sku = str(cleaned.get("provider_sku") or "").strip()
    if not provider_sku:
        raise AdminCatalogError("Provider SKU is required.")
    cleaned["provider_sku"] = provider_sku

    if is_create:
        cleaned.setdefault("is_active", True)

    return cleaned


def fulfillment_map_requires_approval(
    *,
    provider: str,
    is_create: bool,
    provider_changed: bool,
) -> bool:
    if not is_known_provider(provider):
        return True
    if is_create or provider_changed:
        return True
    return False


def apply_fulfillment_approval_rules(
    validated: Dict[str, Any],
    *,
    is_create: bool,
    editor_is_admin: bool,
    editor_username: str,
    existing: Optional[Any] = None,
) -> Dict[str, Any]:
    provider = validated["provider"]
    provider_changed = (
        not is_create
        and existing is not None
        and normalize_provider(getattr(existing, "provider", "")) != provider
    )
    needs_approval = fulfillment_map_requires_approval(
        provider=provider,
        is_create=is_create,
        provider_changed=provider_changed,
    )

    if not needs_approval:
        validated["admin_approved"] = True
        validated["admin_approved_by"] = None
        validated["admin_approved_at"] = None
        return validated

    if editor_is_admin:
        validated["admin_approved"] = True
        validated["admin_approved_by"] = editor_username
        validated["admin_approved_at"] = _utc_now()
        return validated

    validated["admin_approved"] = False
    validated["admin_approved_by"] = None
    validated["admin_approved_at"] = None
    if is_create or provider_changed:
        validated["is_active"] = False
    return validated


def approve_catalog_package(package: Any, *, admin_username: str) -> None:
    package.admin_approved = True
    package.admin_approved_by = admin_username
    package.admin_approved_at = _utc_now()
    if getattr(package, "pending_price_cents", None) is not None:
        package.price_cents = int(package.pending_price_cents)
        package.pending_price_cents = None


def approve_fulfillment_map(row: Any, *, admin_username: str) -> None:
    row.admin_approved = True
    row.admin_approved_by = admin_username
    row.admin_approved_at = _utc_now()
    row.is_active = True


def list_fulfillment_provider_options() -> List[str]:
    return sorted(KNOWN_FULFILLMENT_PROVIDERS)


def slugify_plan_part(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return cleaned.strip("-")


def suggest_plan_slug(*, country: str, data_label: str, validity_days: int) -> str:
    country_part = slugify_plan_part(country) or "plan"
    data_part = slugify_plan_part(data_label) or "data"
    return f"{country_part}-{data_part}-{validity_days}d"


def suggest_catalog_key(*, slug: str, provider: str) -> str:
    provider_part = slugify_plan_part(provider) or "route"
    return f"{slug}-{provider_part}"


def parse_custom_plan_wizard_form(form: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize wizard form fields from POST body."""
    country = str(form.get("country") or "").strip()
    data_label = str(form.get("data_label") or "10GB").strip() or "10GB"
    validity_days = max(1, int(str(form.get("validity_days") or "15")))
    slug = str(form.get("slug") or "").strip().lower() or suggest_plan_slug(
        country=country,
        data_label=data_label,
        validity_days=validity_days,
    )
    name = str(form.get("name") or "").strip() or f"{country} {data_label}".strip()
    provider = normalize_provider(str(form.get("provider") or ""))
    catalog_key = str(form.get("catalog_key") or "").strip() or suggest_catalog_key(
        slug=slug,
        provider=provider,
    )

    data_gb_raw = str(form.get("data_total_gb") or "").strip()
    wholesale_raw = str(form.get("wholesale_cents") or "").strip()

    return {
        "slug": slug,
        "name": name,
        "country": country,
        "country_code": str(form.get("country_code") or "").strip().upper() or None,
        "region": str(form.get("region") or "Americas").strip() or "Americas",
        "flag_emoji": str(form.get("flag_emoji") or "").strip() or None,
        "description": str(form.get("description") or "").strip() or None,
        "data_label": data_label,
        "data_total_gb": Decimal(data_gb_raw) if data_gb_raw else None,
        "validity_days": validity_days,
        "price_cents": int(str(form.get("price_cents") or "0")),
        "currency": str(form.get("currency") or "USD").strip().upper() or "USD",
        "sort_order": int(str(form.get("sort_order") or "0")),
        "is_featured": str(form.get("is_featured") or "").lower() in {"1", "true", "on", "yes"},
        "publish_now": str(form.get("publish_now") or "").lower() in {"1", "true", "on", "yes"},
        "provider": provider,
        "provider_sku": str(form.get("provider_sku") or "").strip(),
        "provider_slug": str(form.get("provider_slug") or "").strip() or None,
        "catalog_key": catalog_key,
        "wholesale_cents": int(wholesale_raw) if wholesale_raw else None,
        "route_notes": str(form.get("route_notes") or "").strip() or None,
    }


def create_custom_plan_from_wizard(
    *,
    form: Dict[str, Any],
    editor_is_admin: bool,
    editor_username: str,
) -> Dict[str, Any]:
    """Create esim_packages row + plan_fulfillment_map in one transaction."""
    parsed = parse_custom_plan_wizard_form(form)

    package_payload = validate_package_payload(
        {
            "slug": parsed["slug"],
            "name": parsed["name"],
            "country": parsed["country"],
            "country_code": parsed["country_code"],
            "region": parsed["region"],
            "flag_emoji": parsed["flag_emoji"],
            "description": parsed["description"],
            "data_label": parsed["data_label"],
            "data_total_gb": parsed["data_total_gb"],
            "validity_days": parsed["validity_days"],
            "price_cents": parsed["price_cents"],
            "currency": parsed["currency"],
            "sort_order": parsed["sort_order"],
            "is_featured": parsed["is_featured"],
            "is_managed": True,
            "is_active": False,
        },
        is_create=True,
    )
    apply_package_approval_rules(
        package_payload,
        is_create=True,
        editor_is_admin=editor_is_admin,
        editor_username=editor_username,
    )
    if editor_is_admin and parsed["publish_now"]:
        package_payload["is_active"] = True

    map_payload = validate_fulfillment_map_payload(
        {
            "catalog_key": parsed["catalog_key"],
            "country_code": parsed["country_code"],
            "country_slug": slugify_plan_part(parsed["country"]),
            "data_gb": parsed["data_total_gb"],
            "validity_days": parsed["validity_days"],
            "provider": parsed["provider"],
            "provider_sku": parsed["provider_sku"],
            "provider_slug": parsed["provider_slug"],
            "wholesale_cents": parsed["wholesale_cents"],
            "is_active": True,
            "notes": parsed["route_notes"],
        },
        is_create=True,
    )
    apply_fulfillment_approval_rules(
        map_payload,
        is_create=True,
        editor_is_admin=editor_is_admin,
        editor_username=editor_username,
    )
    if editor_is_admin and parsed["publish_now"] and package_payload.get("admin_approved"):
        map_payload["is_active"] = True
    elif not map_payload.get("admin_approved"):
        map_payload["is_active"] = False

    factory = get_session_factory()
    if factory is None:
        raise AdminCatalogError("DATABASE_URL is required to create custom plans.")

    package_id = uuid4()
    map_id = uuid4()

    with factory() as session:
        existing = session.execute(
            select(EsimPackage.id).where(EsimPackage.slug == package_payload["slug"])
        ).scalar_one_or_none()
        if existing is not None:
            raise AdminCatalogError(f"Plan slug already exists: {package_payload['slug']}")

        existing_key = session.execute(
            select(PlanFulfillmentMap.id).where(
                PlanFulfillmentMap.catalog_key == map_payload["catalog_key"]
            )
        ).scalar_one_or_none()
        if existing_key is not None:
            raise AdminCatalogError(
                f"Catalog key already exists: {map_payload['catalog_key']}"
            )

        package = EsimPackage(
            id=package_id,
            slug=package_payload["slug"],
            name=package_payload["name"],
            country=package_payload["country"],
            country_code=package_payload.get("country_code"),
            region=package_payload["region"],
            flag_emoji=package_payload.get("flag_emoji"),
            description=package_payload.get("description"),
            data_label=package_payload["data_label"],
            data_total_gb=package_payload.get("data_total_gb"),
            validity_days=package_payload["validity_days"],
            price_cents=package_payload["price_cents"],
            currency=package_payload["currency"],
            provider_sku=parsed["provider_sku"],
            is_active=bool(package_payload.get("is_active")),
            is_featured=bool(package_payload.get("is_featured")),
            is_managed=bool(package_payload.get("is_managed", True)),
            sort_order=package_payload["sort_order"],
            admin_approved=bool(package_payload.get("admin_approved")),
            admin_approved_by=package_payload.get("admin_approved_by"),
            admin_approved_at=package_payload.get("admin_approved_at"),
            pending_price_cents=package_payload.get("pending_price_cents"),
        )
        route = PlanFulfillmentMap(
            id=map_id,
            catalog_key=map_payload["catalog_key"],
            package_id=package_id,
            country_code=map_payload.get("country_code"),
            country_slug=map_payload.get("country_slug"),
            data_gb=map_payload.get("data_gb"),
            validity_days=map_payload.get("validity_days"),
            provider=map_payload["provider"],
            provider_sku=map_payload["provider_sku"],
            provider_slug=map_payload.get("provider_slug"),
            wholesale_cents=map_payload.get("wholesale_cents"),
            is_active=bool(map_payload.get("is_active")),
            admin_approved=bool(map_payload.get("admin_approved")),
            admin_approved_by=map_payload.get("admin_approved_by"),
            admin_approved_at=map_payload.get("admin_approved_at"),
            notes=map_payload.get("notes"),
        )
        session.add(package)
        session.add(route)
        session.commit()

    sale_status = package_sale_status(
        is_active=bool(package_payload.get("is_active")),
        admin_approved=bool(package_payload.get("admin_approved")),
    )
    return {
        "slug": package_payload["slug"],
        "name": package_payload["name"],
        "catalog_key": map_payload["catalog_key"],
        "provider": map_payload["provider"],
        "package_id": str(package_id),
        "sale_status": sale_status,
        "admin_approved": bool(package_payload.get("admin_approved")),
        "route_approved": bool(map_payload.get("admin_approved")),
    }
