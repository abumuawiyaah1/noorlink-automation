"""Admin-only complimentary (free) eSIM grants for staff and partners."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select

from app.api import supabase_repository as db
from app.api.supabase_repository import SupabaseRepositoryError, _generate_order_number, _upsert_user_by_email
from app.db.engine import get_session_factory
from app.db.models import EsimPackage
from app.services.fulfillment import FulfillmentError, fulfill_paid_order
from app.services.fulfillment_map import (
    FulfillmentMapError,
    enforce_saudi_access_policy,
    resolve_fulfillment_target,
)

logger = logging.getLogger(__name__)

COMPLIMENTARY_REASONS = {
    "staff": "Staff member",
    "partner": "Partner / collaborator",
    "goodwill": "Customer goodwill",
    "qa_test": "QA / internal test",
}


class AdminComplimentaryError(Exception):
    """Complimentary eSIM grant failed."""


def list_grantable_packages(*, limit: int = 500) -> List[Dict[str, Any]]:
    """Active catalog packages available for admin grants."""
    factory = get_session_factory()
    if factory is None:
        raise AdminComplimentaryError("DATABASE_URL is required for complimentary eSIM grants.")

    with factory() as session:
        rows = session.execute(
            select(EsimPackage)
            .where(EsimPackage.is_active.is_(True))
            .order_by(EsimPackage.country, EsimPackage.sort_order, EsimPackage.name)
            .limit(limit)
        ).scalars().all()

    return [
        {
            "id": str(row.id),
            "name": row.name,
            "country": row.country,
            "flag_emoji": row.flag_emoji,
            "data_label": row.data_label,
            "validity_days": row.validity_days,
            "price_cents": row.price_cents,
            "currency": row.currency,
        }
        for row in rows
    ]


def _load_package(package_id: str) -> EsimPackage:
    factory = get_session_factory()
    if factory is None:
        raise AdminComplimentaryError("DATABASE_URL is not configured.")
    try:
        pkg_uuid = UUID(package_id.strip())
    except ValueError as exc:
        raise AdminComplimentaryError("Invalid package id.") from exc

    with factory() as session:
        package = session.get(EsimPackage, pkg_uuid)
    if package is None:
        raise AdminComplimentaryError("Package not found.")
    if not package.is_active:
        raise AdminComplimentaryError("Package is not active.")
    return package


def _build_complimentary_order_payload(
    *,
    package: EsimPackage,
    recipient_email: str,
    recipient_name: Optional[str],
    reason: str,
    note: Optional[str],
    granted_by: str,
) -> Dict[str, Any]:
    email = recipient_email.strip().lower()
    if not email or "@" not in email:
        raise AdminComplimentaryError("A valid recipient email is required.")

    reason_key = (reason or "").strip().lower()
    if reason_key not in COMPLIMENTARY_REASONS:
        raise AdminComplimentaryError("Choose a valid grant reason.")

    client = db.get_supabase_client()
    user_id = _upsert_user_by_email(client, email)

    data_total_gb = float(package.data_total_gb) if package.data_total_gb is not None else None
    validity_days = int(package.validity_days) if package.validity_days is not None else None

    probe_order = {
        "package_id": str(package.id),
        "country": package.country,
        "data_total_gb": data_total_gb,
        "validity_days": validity_days,
        "metadata": {},
    }
    package_dict = {
        "id": str(package.id),
        "name": package.name,
        "country": package.country,
        "data_total_gb": data_total_gb,
        "validity_days": validity_days,
        "price_cents": package.price_cents,
        "currency": package.currency,
        "slug": package.slug,
    }

    fulfillment_target = resolve_fulfillment_target(probe_order, package=package_dict)
    try:
        enforce_saudi_access_policy(probe_order, fulfillment_target)
    except FulfillmentMapError as exc:
        raise AdminComplimentaryError(str(exc)) from exc

    metadata: Dict[str, Any] = {
        "complimentary": {
            "granted_by": granted_by,
            "reason": reason_key,
            "reason_label": COMPLIMENTARY_REASONS[reason_key],
            "recipient_name": (recipient_name or "").strip() or None,
            "note": (note or "").strip() or None,
            "granted_at": datetime.now(timezone.utc).isoformat(),
            "catalog_price_cents": int(package.price_cents),
        },
    }
    if validity_days is not None:
        metadata["validity_days"] = validity_days

    if fulfillment_target:
        metadata["fulfillment_plan"] = {
            "catalog_key": fulfillment_target.catalog_key,
            "provider": fulfillment_target.provider,
            "provider_sku": fulfillment_target.provider_sku,
            "provider_slug": fulfillment_target.provider_slug,
            "wholesale_cents": fulfillment_target.wholesale_cents,
            "source": fulfillment_target.source,
            "data_gb": fulfillment_target.data_gb,
            "validity_days": fulfillment_target.validity_days,
        }

    order_number = _generate_order_number()
    payload: Dict[str, Any] = {
        "order_number": order_number,
        "user_id": user_id,
        "package_id": str(package.id),
        "email": email,
        "country": package.country,
        "flag_emoji": package.flag_emoji,
        "package_name": package.name,
        "amount_cents": 0,
        "currency": package.currency or "USD",
        "status": "pending",
        "data_total_gb": data_total_gb,
        "data_used_gb": 0,
        "metadata": metadata,
    }
    return payload


def grant_complimentary_esim(
    *,
    package_id: str,
    recipient_email: str,
    recipient_name: Optional[str] = None,
    reason: str = "staff",
    note: Optional[str] = None,
    granted_by: str,
) -> Dict[str, Any]:
    """
    Create a $0 order, mark paid, provision eSIM, and email the recipient.
    Admin-only — enforced at the dashboard layer.
    """
    package = _load_package(package_id)
    payload = _build_complimentary_order_payload(
        package=package,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        reason=reason,
        note=note,
        granted_by=granted_by,
    )
    order_number = payload["order_number"]

    client = db.get_supabase_client()
    try:
        result = client.table("orders").insert(payload).execute()
    except Exception as exc:
        logger.exception("Complimentary order insert failed")
        raise AdminComplimentaryError(str(exc)) from exc

    if not result.data:
        raise AdminComplimentaryError("Order insert returned no data.")

    try:
        paid_row = db.mark_order_paid(order_number=order_number)
        if not paid_row:
            raise AdminComplimentaryError("Could not mark complimentary order as paid.")
        delivered = fulfill_paid_order(paid_row)
    except FulfillmentError as exc:
        raise AdminComplimentaryError(str(exc)) from exc
    except SupabaseRepositoryError as exc:
        raise AdminComplimentaryError(str(exc)) from exc

    return {
        "order_number": order_number,
        "email": payload["email"],
        "country": payload["country"],
        "package_name": payload["package_name"],
        "status": delivered.get("status"),
        "qr_code_url": delivered.get("qr_code_url"),
    }
