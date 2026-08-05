"""
Persistent data access via Supabase (PostgreSQL).
Requires SUPABASE_URL + SUPABASE_SERVICE_KEY in the environment.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from functools import lru_cache
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from supabase import Client, create_client

from app.core.config import get_settings
from app.services.pricing_engine import (
    has_global_pricing_rule,
    normalize_plan_category,
    resolve_display_badge,
    resolve_plan_price,
    select_pricing_rule_hierarchy,
)
from .regional_inventory import build_dynamic_package_payload
from .schemas import Order, OrderStatus

logger = logging.getLogger(__name__)


class SupabaseRepositoryError(Exception):
    """Raised when a database operation fails."""


class ManagedPackagePriceMismatchError(SupabaseRepositoryError):
    """Client price does not match the catalog row for a managed package."""


@dataclass(frozen=True)
class CreatedOrder:
    order: Order
    order_id: str
    package: Optional[Dict[str, Any]]


@lru_cache
def get_supabase_client() -> Client:
    cfg = get_settings()
    if not cfg.supabase_url or not cfg.supabase_admin_key:
        raise SupabaseRepositoryError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"
        )
    return create_client(cfg.supabase_url, cfg.supabase_admin_key)


def _generate_order_number() -> str:
    return f"NL-{uuid4().hex[:8].upper()}"


def _parse_travel_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def _row_to_order(row: Dict[str, Any]) -> Order:
    amount_cents = row.get("amount_cents") or 0
    created = row.get("created_at")
    if isinstance(created, str):
        created_at = created
    elif isinstance(created, datetime):
        created_at = created.astimezone(timezone.utc).isoformat()
    else:
        created_at = datetime.now(timezone.utc).isoformat()

    status = row.get("status") or "pending"
    if status not in (
        "pending",
        "paid",
        "delivered",
        "active",
        "expired",
        "refunded",
        "failed",
    ):
        status = "pending"

    return Order(
        id=str(row.get("id") or row.get("order_number")),
        order_number=row["order_number"],
        email=row["email"],
        country=row["country"],
        flag=row.get("flag_emoji"),
        package_name=row["package_name"],
        price=round(float(amount_cents) / 100.0, 2),
        currency=row.get("currency") or "USD",
        status=status,  # type: ignore[arg-type]
        created_at=created_at,
        qr_code_url=row.get("qr_code_url"),
        activation_code=row.get("activation_code"),
        data_used_gb=float(row["data_used_gb"]) if row.get("data_used_gb") is not None else None,
        data_total_gb=float(row["data_total_gb"]) if row.get("data_total_gb") is not None else None,
    )


def _upsert_user_by_email(client: Client, email: str) -> Optional[str]:
    normalized = email.strip().lower()
    try:
        existing = (
            client.table("users")
            .select("id")
            .eq("email", normalized)
            .limit(1)
            .execute()
        )
        if existing.data:
            return str(existing.data[0]["id"])

        inserted = (
            client.table("users")
            .insert({"email": normalized})
            .execute()
        )
        if inserted.data:
            return str(inserted.data[0]["id"])
    except Exception:
        logger.warning("users upsert skipped for %s", normalized, exc_info=True)
    return None


def _has_managed_catalog_for_country(client: Client, country: str) -> bool:
    """Avoid auto-provisioning when a managed SKU already owns this country."""
    try:
        result = (
            client.table("esim_packages")
            .select("id")
            .ilike("country", country)
            .eq("is_managed", True)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception:
        logger.exception("Managed catalog probe failed for %s", country)
        return False


def _provision_dynamic_package(
    client: Client,
    *,
    country: str,
    price_cents: int,
    flag: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Insert a regional template package for an unknown country so future lookups hit DB.
    """
    if _has_managed_catalog_for_country(client, country):
        logger.debug(
            "Skipping dynamic provision; managed catalog exists for %s", country
        )
        return None

    payload = build_dynamic_package_payload(
        country_input=country,
        price_cents=price_cents,
        flag_emoji=flag,
    )
    if not payload:
        return None

    slug = payload["slug"]
    existing = (
        client.table("esim_packages")
        .select("*")
        .eq("slug", slug)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    try:
        result = client.table("esim_packages").insert(payload).execute()
    except Exception as exc:
        logger.warning("Dynamic package insert conflict for %s: %s", slug, exc)
        retry = (
            client.table("esim_packages")
            .select("*")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if retry.data:
            return retry.data[0]
        logger.exception("Dynamic package provisioning failed for %s", country)
        return None

    if result.data:
        logger.info("Provisioned dynamic package %s for %s", slug, country)
        return result.data[0]
    return None


def _resolve_package(
    client: Client,
    *,
    package_id: Optional[str],
    country: str,
    price_cents: int,
    flag: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        return _resolve_package_unsafe(
            client,
            package_id=package_id,
            country=country,
            price_cents=price_cents,
            flag=flag,
        )
    except Exception:
        logger.warning(
            "Package resolve failed for country=%s package_id=%s",
            country,
            package_id,
            exc_info=True,
        )
        return None


def _resolve_package_unsafe(
    client: Client,
    *,
    package_id: Optional[str],
    country: str,
    price_cents: int,
    flag: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if package_id:
        result = (
            client.table("esim_packages")
            .select("*")
            .eq("id", package_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            if row.get("is_managed") and row.get("price_cents") != price_cents:
                return None
            return row
        return None

    result = (
        client.table("esim_packages")
        .select("*")
        .eq("country", country)
        .eq("price_cents", price_cents)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]

    result = (
        client.table("esim_packages")
        .select("*")
        .ilike("country", country)
        .eq("price_cents", price_cents)
        .eq("is_active", True)
        .order("sort_order")
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]

    result = (
        client.table("esim_packages")
        .select("*")
        .ilike("country", country)
        .eq("is_active", True)
        .order("sort_order")
        .limit(1)
        .execute()
    )
    if result.data:
        row = result.data[0]
        if row.get("is_managed") and row.get("price_cents") != price_cents:
            pass
        else:
            return row

    return _provision_dynamic_package(
        client,
        country=country,
        price_cents=price_cents,
        flag=flag,
    )


def _validate_managed_package_price(
    package: Optional[Dict[str, Any]],
    price_cents: int,
) -> None:
    if not package or not package.get("is_managed"):
        return
    catalog_cents = package.get("price_cents")
    if catalog_cents is None:
        return
    if price_cents != int(catalog_cents):
        raise ManagedPackagePriceMismatchError(
            f"Price mismatch for managed package "
            f"'{package.get('slug') or package.get('id')}': "
            f"expected {catalog_cents} cents, got {price_cents} cents"
        )


def save_newsletter_subscriber(email: str, dream_destination: Optional[str] = None) -> None:
    client = get_supabase_client()
    payload: Dict[str, Any] = {"email": email.strip().lower()}
    if dream_destination:
        payload["dream_destination"] = dream_destination

    try:
        client.table("newsletter_subscribers").upsert(
            payload,
            on_conflict="email",
        ).execute()
    except Exception as exc:
        logger.exception("newsletter_subscribers upsert failed")
        raise SupabaseRepositoryError(str(exc)) from exc


def create_support_ticket(
    *,
    name: str,
    email: str,
    subject: Optional[str],
    message: str,
) -> str:
    client = get_supabase_client()
    ticket_number = f"TCK-{uuid4().hex[:8].upper()}"
    payload = {
        "ticket_number": ticket_number,
        "name": name.strip(),
        "email": email.strip().lower(),
        "subject": subject,
        "message": message.strip(),
        "status": "open",
    }
    try:
        client.table("support_tickets").insert(payload).execute()
    except Exception as exc:
        logger.exception("support_tickets insert failed")
        raise SupabaseRepositoryError(str(exc)) from exc
    return ticket_number


def create_order(
    *,
    email: str,
    country: str,
    price: float,
    flag: Optional[str],
    travel_date: Optional[str],
    package_id: Optional[str] = None,
) -> CreatedOrder:
    client = get_supabase_client()
    price_cents = int(round(price * 100))
    user_id = _upsert_user_by_email(client, email)
    package = _resolve_package(
        client,
        package_id=package_id,
        country=country,
        price_cents=price_cents,
        flag=flag,
    )
    _validate_managed_package_price(package, price_cents)

    if package_id and not package:
        try:
            managed_probe = (
                client.table("esim_packages")
                .select("id, is_managed, price_cents, slug")
                .eq("id", package_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if managed_probe.data and managed_probe.data[0].get("is_managed"):
                _validate_managed_package_price(managed_probe.data[0], price_cents)
        except Exception:
            logger.warning("Managed package probe failed for %s", package_id, exc_info=True)

    package_name = (
        package["name"] if package else f"{country} Travel eSIM"
    )
    pkg_id = str(package["id"]) if package else None
    data_total_gb = package.get("data_total_gb") if package else None

    order_number = _generate_order_number()
    payload: Dict[str, Any] = {
        "order_number": order_number,
        "user_id": user_id,
        "package_id": pkg_id,
        "email": email.strip().lower(),
        "country": country,
        "flag_emoji": flag,
        "package_name": package_name,
        "amount_cents": price_cents,
        "currency": (package or {}).get("currency") or "USD",
        "status": "pending",
        "travel_date": _parse_travel_date(travel_date),
        "data_total_gb": data_total_gb,
        "data_used_gb": 0,
    }

    try:
        result = client.table("orders").insert(payload).execute()
    except Exception as exc:
        logger.exception("orders insert failed")
        message = str(exc)
        if "Could not find the table" in message or "PGRST205" in message:
            raise SupabaseRepositoryError(
                "Checkout tables are missing. Run supabase/bootstrap_checkout_minimal.sql "
                "in the Supabase SQL Editor, then retry."
            ) from exc
        raise SupabaseRepositoryError(message) from exc

    if not result.data:
        raise SupabaseRepositoryError("Order insert returned no data")
    row = result.data[0]
    return CreatedOrder(
        order=_row_to_order(row),
        order_id=str(row["id"]),
        package=package,
    )


def _fetch_order_row(
    client: Client,
    *,
    order_number: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    query = client.table("orders").select("*")
    if order_number:
        query = query.eq("order_number", order_number)
    elif stripe_checkout_session_id:
        query = query.eq("stripe_checkout_session_id", stripe_checkout_session_id)
    else:
        return None
    result = query.limit(1).execute()
    if not result.data:
        return None
    return result.data[0]


def get_order_row_by_stripe_session(session_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    try:
        return _fetch_order_row(client, stripe_checkout_session_id=session_id)
    except Exception as exc:
        logger.exception("Order fetch by Stripe session failed")
        raise SupabaseRepositoryError(str(exc)) from exc


def get_order_row_by_order_number(order_number: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    try:
        return _fetch_order_row(client, order_number=order_number)
    except Exception as exc:
        logger.exception("Order fetch by order_number failed")
        raise SupabaseRepositoryError(str(exc)) from exc


def merge_order_metadata(order_number: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    client = get_supabase_client()
    row = _fetch_order_row(client, order_number=order_number)
    if not row:
        raise SupabaseRepositoryError(f"Order not found: {order_number}")

    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    merged = {**metadata, **patch}

    try:
        client.table("orders").update({"metadata": merged}).eq(
            "order_number", order_number
        ).execute()
    except Exception as exc:
        logger.exception("orders metadata merge failed for %s", order_number)
        raise SupabaseRepositoryError(str(exc)) from exc
    return merged


def mark_order_paid(
    *,
    order_number: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
    stripe_payment_intent_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Transition order pending → paid. Idempotent if already paid or delivered.
    Returns the updated order row, or None if not found.
    """
    client = get_supabase_client()
    row = _fetch_order_row(
        client,
        order_number=order_number,
        stripe_checkout_session_id=stripe_checkout_session_id,
    )
    if not row:
        return None

    current_status = row.get("status")
    if current_status in ("paid", "delivered", "active"):
        logger.info(
            "Order %s already %s; skipping paid transition",
            row["order_number"],
            current_status,
        )
        return row

    if current_status != "pending":
        logger.warning(
            "Order %s in unexpected status %s for mark_order_paid",
            row["order_number"],
            current_status,
        )
        return row

    now = datetime.now(timezone.utc).isoformat()
    updates: Dict[str, Any] = {
        "status": "paid",
        "paid_at": now,
    }
    if stripe_payment_intent_id:
        updates["stripe_payment_intent_id"] = stripe_payment_intent_id

    try:
        result = (
            client.table("orders")
            .update(updates)
            .eq("order_number", row["order_number"])
            .eq("status", "pending")
            .execute()
        )
    except Exception as exc:
        logger.exception("mark_order_paid failed for %s", row["order_number"])
        raise SupabaseRepositoryError(str(exc)) from exc

    if result.data:
        return result.data[0]

    refreshed = _fetch_order_row(client, order_number=row["order_number"])
    return refreshed


def mark_order_delivered(
    order_number: str,
    *,
    qr_code_url: str,
    activation_code: str,
    metadata_patch: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    client = get_supabase_client()
    row = _fetch_order_row(client, order_number=order_number)
    if not row:
        raise SupabaseRepositoryError(f"Order not found: {order_number}")

    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    if metadata_patch:
        metadata = {**metadata, **metadata_patch}

    now = datetime.now(timezone.utc).isoformat()
    updates: Dict[str, Any] = {
        "status": "delivered",
        "fulfilled_at": now,
        "qr_code_url": qr_code_url,
        "activation_code": activation_code,
        "metadata": metadata,
    }

    try:
        result = (
            client.table("orders")
            .update(updates)
            .eq("order_number", order_number)
            .execute()
        )
    except Exception as exc:
        logger.exception("mark_order_delivered failed for %s", order_number)
        raise SupabaseRepositoryError(str(exc)) from exc

    if not result.data:
        raise SupabaseRepositoryError("Delivered update returned no data")
    return result.data[0]


def update_order_stripe_session(
    order_number: str,
    stripe_checkout_session_id: str,
) -> None:
    client = get_supabase_client()
    try:
        client.table("orders").update(
            {"stripe_checkout_session_id": stripe_checkout_session_id}
        ).eq("order_number", order_number).execute()
    except Exception as exc:
        logger.exception(
            "orders stripe_checkout_session_id update failed for %s",
            order_number,
        )
        raise SupabaseRepositoryError(str(exc)) from exc


def lookup_order(order_id: str, email: str) -> Optional[Order]:
    client = get_supabase_client()
    normalized_email = email.strip().lower()
    order_number = order_id.strip()

    try:
        result = (
            client.table("orders")
            .select("*")
            .eq("order_number", order_number)
            .eq("email", normalized_email)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.exception("orders lookup failed")
        raise SupabaseRepositoryError(str(exc)) from exc

    if not result.data:
        return None
    return _row_to_order(result.data[0])


# Supabase UI label: "Mobile Data Plans" → PostgreSQL table name:
MOBILE_DATA_PLANS_TABLE = "mobile_data_plans"
PRICING_RULES_TABLE = "pricing_rules"


def fetch_active_pricing_rules() -> list[Dict[str, Any]]:
    """Return all active pricing_rules for hierarchy resolution."""
    client = get_supabase_client()
    try:
        result = (
            client.table(PRICING_RULES_TABLE)
            .select(
                "rule_name, scope, target_id, multiplier, fixed_buffer, "
                "min_margin_amount, price_suffix_rule, is_active"
            )
            .eq("is_active", True)
            .execute()
        )
    except Exception as exc:
        logger.exception("pricing_rules fetch failed")
        raise SupabaseRepositoryError(str(exc)) from exc

    return list(result.data or [])


def _normalize_country_id(country_id: str) -> str:
    """Map URL-friendly country keys to catalog ids."""
    raw = country_id.strip().lower().replace("_", "-")
    aliases = {
        "united-states": "usa",
        "us": "usa",
        "united-kingdom": "uk",
        "gb": "uk",
        "saudi": "saudi-arabia",
        "umrah": "saudi-arabia",
        "hajj": "saudi-arabia",
        "eu": "europe",
        "schengen": "europe",
    }
    return aliases.get(raw, raw)


def _parse_plan_price(row: Dict[str, Any]) -> float:
    if row.get("price_cents") is not None:
        return round(float(row["price_cents"]) / 100.0, 2)
    if row.get("price") is not None:
        return round(float(row["price"]), 2)
    if row.get("amount") is not None:
        return round(float(row["amount"]), 2)
    return 0.0


def _is_rechargeable_plan(row: Dict[str, Any]) -> bool:
    for key in ("rechargeable", "is_rechargeable", "is_pay_as_you_go", "pay_as_you_go"):
        if row.get(key) is True:
            return True

    plan_type = str(row.get("plan_type") or row.get("type") or "").lower()
    if plan_type in {"payg", "pay-as-you-go", "rechargeable", "flex"}:
        return True

    name = str(row.get("name") or "").lower()
    return "pay-as-you-go" in name or "pay as you go" in name


def _map_mobile_data_plan_row(
    row: Dict[str, Any],
    country_id: str,
    *,
    pricing_rules: list[Dict[str, Any]],
) -> Dict[str, Any]:
    data_gb = row.get("data_gb")
    if data_gb is None and row.get("data_total_gb") is not None:
        data_gb = row.get("data_total_gb")

    duration_days = row.get("duration_days")
    if duration_days is None:
        duration_days = row.get("validity_days")

    rechargeable = _is_rechargeable_plan(row)
    plan_category = normalize_plan_category(row, is_rechargeable=rechargeable)
    is_featured = bool(row.get("is_featured"))

    try:
        rule = select_pricing_rule_hierarchy(
            pricing_rules,
            country_id=country_id,
            region_id=row.get("region_id"),
        )
        price, pricing_strategy, margin_status, formatted_price_parts = (
            resolve_plan_price(row, rule)
        )
    except ValueError as exc:
        raise SupabaseRepositoryError(str(exc)) from exc

    return {
        "id": str(row["id"]),
        "country_id": str(row.get("country_id") or country_id),
        "name": row.get("name") or "Plan",
        "data_gb": float(data_gb) if data_gb is not None else None,
        "duration_days": duration_days,
        "price": price,
        "formatted_price_parts": formatted_price_parts,
        "currency": row.get("currency") or "USD",
        "is_rechargeable": rechargeable,
        "is_pay_as_you_go": rechargeable,
        "pricing_strategy": pricing_strategy,
        "margin_status": margin_status,
        "plan_category": plan_category,
        "display_badge": resolve_display_badge(
            plan_category=plan_category,
            is_featured=is_featured,
        ),
    }


def _group_plans_by_category(
    plans: list[Dict[str, Any]],
) -> Dict[str, list[Dict[str, Any]]]:
    groups: Dict[str, list[Dict[str, Any]]] = {
        "fixed": [],
        "unlimited": [],
        "flexible": [],
    }
    for plan in plans:
        category = plan.get("plan_category") or "fixed"
        groups.setdefault(category, []).append(plan)
    return groups


def _fetch_country_metadata(
    client: Client, country_id: str
) -> Dict[str, Optional[str]]:
    """Best-effort country label/flag from optional countries table."""
    for table in ("countries", "country"):
        try:
            result = (
                client.table(table)
                .select("id, slug, name, flag_emoji, flag")
                .or_(f"slug.eq.{country_id},id.eq.{country_id}")
                .limit(1)
                .execute()
            )
            if result.data:
                row = result.data[0]
                return {
                    "country_name": row.get("name"),
                    "flag": row.get("flag_emoji") or row.get("flag"),
                }
        except Exception:
            continue
    return {"country_name": None, "flag": None}


def get_plans_by_country(country_id: str) -> Dict[str, Any]:
    """
    Return browsable plans for a country from public.mobile_data_plans
    (Supabase display name: "Mobile Data Plans").
    """
    client = get_supabase_client()
    normalized = _normalize_country_id(country_id)
    lookup_ids = list(dict.fromkeys([country_id.strip(), normalized]))

    rows: list[Dict[str, Any]] = []
    try:
        for lookup_id in lookup_ids:
            result = (
                client.table(MOBILE_DATA_PLANS_TABLE)
                .select("*")
                .eq("country_id", lookup_id)
                .execute()
            )
            rows = result.data or []
            if rows:
                break
    except Exception as exc:
        logger.exception(
            "%s fetch failed for country_id=%s",
            MOBILE_DATA_PLANS_TABLE,
            country_id,
        )
        raise SupabaseRepositoryError(str(exc)) from exc

    active_rows = [
        row
        for row in rows
        if row.get("is_active", row.get("active", True)) is not False
    ]
    source_rows = active_rows or rows
    source_rows.sort(
        key=lambda row: (
            row.get("sort_order") if row.get("sort_order") is not None else 999,
            str(row.get("name") or ""),
        )
    )

    meta = _fetch_country_metadata(client, normalized)
    if source_rows:
        first = source_rows[0]
        meta["country_name"] = meta.get("country_name") or first.get("country_name")
        meta["flag"] = meta.get("flag") or first.get("flag_emoji") or first.get("flag")

    try:
        pricing_rules = fetch_active_pricing_rules()
    except SupabaseRepositoryError:
        raise
    except Exception as exc:
        logger.exception("pricing_rules load failed")
        raise SupabaseRepositoryError(str(exc)) from exc

    if not pricing_rules:
        raise SupabaseRepositoryError(
            "No active pricing rules configured. Add rows to pricing_rules."
        )

    if not has_global_pricing_rule(pricing_rules):
        raise SupabaseRepositoryError(
            "No active GLOBAL pricing rule configured. Margins cannot be computed."
        )

    plans = [
        _map_mobile_data_plan_row(row, normalized, pricing_rules=pricing_rules)
        for row in source_rows
    ]
    plan_groups = _group_plans_by_category(plans)

    return {
        "country_id": normalized,
        "country_name": meta.get("country_name") or normalized.replace("-", " ").title(),
        "flag": meta.get("flag"),
        "plans": plans,
        "plan_groups": plan_groups,
    }


def ping_database() -> bool:
    """Lightweight connectivity check for health endpoint.

    Prefer mobile_data_plans (live catalog used by /api/v1/plans). Fall back to
    esim_packages for older deployments that only have the checkout SKU table.
    """
    client = get_supabase_client()
    for table in (MOBILE_DATA_PLANS_TABLE, "esim_packages"):
        try:
            client.table(table).select("id").limit(1).execute()
            return True
        except Exception:
            logger.warning("Supabase ping failed for table=%s", table, exc_info=True)
    return False
