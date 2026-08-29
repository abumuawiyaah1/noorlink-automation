"""Admin operations: manual fulfill, suspended orders, cron tasks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import func, select

from app.api import supabase_repository as db
from app.db.engine import get_session_factory
from app.db.models import Order
from app.services.email_service import EmailDeliveryError
from app.services.fulfillment import FulfillmentError, fulfill_paid_order, process_paid_order
from app.services.insider_release import expire_finished_promos, release_due_insider_issues

logger = logging.getLogger(__name__)


class AdminOperationsError(Exception):
    """Admin operations action failed."""


def get_operations_summary() -> Dict[str, Any]:
    """Counts and flags for the operations dashboard."""
    factory = get_session_factory()
    suspended_count = 0
    pending_fulfillment = 0
    if factory is not None:
        with factory() as session:
            suspended_count = session.scalar(
                select(func.count()).select_from(Order).where(Order.status == "suspended")
            ) or 0
            pending_fulfillment = session.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.status == "paid")
                .where(Order.qr_code_url.is_(None))
            ) or 0

    active_subscribers = 0
    due_insider = 0
    try:
        client = db.get_supabase_client()
        subs = (
            client.table("newsletter_subscribers")
            .select("email", count="exact")
            .is_("unsubscribed_at", "null")
            .execute()
        )
        active_subscribers = int(subs.count or 0)
        now = datetime.now(timezone.utc).isoformat()
        due = (
            client.table("insider_issues")
            .select("slug", count="exact")
            .eq("status", "scheduled")
            .lte("send_at", now)
            .execute()
        )
        due_insider = int(due.count or 0)
    except Exception as exc:
        logger.warning("Operations summary partial failure: %s", exc)

    catalog_synced_at = None
    catalog_count = 0
    try:
        client = db.get_supabase_client()
        cat = (
            client.table("provider_catalog_products")
            .select("synced_at")
            .eq("is_active", True)
            .order("synced_at", desc=True)
            .limit(1)
            .execute()
        )
        if cat.data:
            catalog_synced_at = cat.data[0].get("synced_at")
        count_result = (
            client.table("provider_catalog_products")
            .select("provider_sku", count="exact")
            .eq("is_active", True)
            .execute()
        )
        catalog_count = int(count_result.count or 0)
    except Exception:
        pass

    return {
        "suspended_count": suspended_count,
        "pending_fulfillment": pending_fulfillment,
        "active_subscribers": active_subscribers,
        "due_insider_issues": due_insider,
        "catalog_product_count": catalog_count,
        "catalog_last_synced_at": catalog_synced_at,
    }


def manual_fulfill_order(*, order_number: str, paid_only: bool = False) -> Dict[str, Any]:
    normalized = order_number.strip().upper()
    if not normalized:
        raise AdminOperationsError("Order number is required.")

    try:
        row = db.get_order_row_by_order_number(normalized)
    except db.SupabaseRepositoryError as exc:
        raise AdminOperationsError(str(exc)) from exc

    if not row:
        raise AdminOperationsError(f"Order not found: {normalized}")

    status = str(row.get("status") or "")
    if paid_only:
        if status not in ("paid", "delivered", "active"):
            raise AdminOperationsError(
                f"Order is {status!r}. Uncheck 'paid only' to mark paid first."
            )
        try:
            result = fulfill_paid_order(row)
        except FulfillmentError as exc:
            raise AdminOperationsError(str(exc)) from exc
    else:
        if status in ("delivered", "active") and row.get("qr_code_url"):
            raise AdminOperationsError(
                f"Order {normalized} is already fulfilled (status={status})."
            )
        try:
            result = process_paid_order(order_number=normalized)
        except FulfillmentError as exc:
            raise AdminOperationsError(str(exc)) from exc

    if not result:
        raise AdminOperationsError("Fulfillment returned no result.")

    return {
        "order_number": normalized,
        "status": result.get("status"),
        "has_qr": bool(result.get("qr_code_url")),
    }


def list_suspended_orders(*, limit: int = 50) -> List[Dict[str, Any]]:
    factory = get_session_factory()
    if factory is None:
        return []

    with factory() as session:
        rows = session.scalars(
            select(Order)
            .where(Order.status == "suspended")
            .order_by(Order.updated_at.desc())
            .limit(limit)
        ).all()

    results: List[Dict[str, Any]] = []
    for order in rows:
        metadata = order.metadata_ or {}
        simbase = metadata.get("simbase") if isinstance(metadata.get("simbase"), dict) else {}
        results.append(
            {
                "order_number": order.order_number,
                "email": order.email,
                "country": order.country,
                "package_name": order.package_name,
                "iccid": order.iccid,
                "data_used_gb": float(order.data_used_gb) if order.data_used_gb else None,
                "data_total_gb": float(order.data_total_gb) if order.data_total_gb else None,
                "suspended_at": simbase.get("suspended_at"),
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            }
        )
    return results


def reactivate_suspended_order(*, order_number: str) -> Dict[str, Any]:
    normalized = order_number.strip().upper()
    factory = get_session_factory()
    if factory is None:
        raise AdminOperationsError("DATABASE_URL is required.")

    with factory() as session:
        order = session.scalar(select(Order).where(Order.order_number == normalized))
        if order is None:
            raise AdminOperationsError(f"Order not found: {normalized}")
        if order.status != "suspended":
            raise AdminOperationsError(f"Order is {order.status!r}, not suspended.")

        metadata = dict(order.metadata_ or {})
        simbase = dict(metadata.get("simbase") or {})
        simbase["usage_guard"] = "reactivated"
        simbase["reactivated_at"] = datetime.now(timezone.utc).isoformat()
        metadata["simbase"] = simbase
        order.metadata_ = metadata
        order.status = "active"
        session.commit()

    return {"order_number": normalized, "status": "active"}


def run_admin_cron_tasks() -> Dict[str, Any]:
    """Run the same tasks as POST /api/cron/run (for admin UI)."""
    result: Dict[str, Any] = {"success": True, "tasks": {}}

    try:
        result["tasks"]["expired_promos"] = expire_finished_promos()
    except db.SupabaseRepositoryError as exc:
        result["tasks"]["expired_promos"] = {"error": str(exc)}
        result["success"] = False

    try:
        result["tasks"]["insider"] = release_due_insider_issues()
    except (db.SupabaseRepositoryError, EmailDeliveryError) as exc:
        result["tasks"]["insider"] = {"error": str(exc)}
        result["success"] = False

    try:
        from app.services.provider_catalog import sync_telna_catalog
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            catalog = loop.run_until_complete(sync_telna_catalog(use_builtin_on_failure=True))
        finally:
            loop.close()
        result["tasks"]["catalog_sync"] = catalog
    except Exception as exc:
        result["tasks"]["catalog_sync"] = {"success": False, "error": str(exc)[:240]}

    try:
        from app.services.expiry_reminders import process_esim_expiry_reminders

        result["tasks"]["expiry_reminders"] = process_esim_expiry_reminders()
    except Exception as exc:
        result["tasks"]["expiry_reminders"] = {"success": False, "error": str(exc)[:240]}

    try:
        from app.services.usage_sync_cron import process_esim_usage_sync

        result["tasks"]["usage_sync"] = process_esim_usage_sync()
    except Exception as exc:
        result["tasks"]["usage_sync"] = {"success": False, "error": str(exc)[:240]}

    try:
        from app.services.ops_log_retention import purge_old_ops_logs

        result["tasks"]["log_retention"] = purge_old_ops_logs(retention_days=90)
    except Exception as exc:
        result["tasks"]["log_retention"] = {"error": str(exc)[:240]}

    try:
        from app.services.support_auto_refund import process_unanswered_auto_refunds

        result["tasks"]["auto_refunds"] = process_unanswered_auto_refunds()
    except Exception as exc:
        result["tasks"]["auto_refunds"] = {"success": False, "error": str(exc)[:240]}

    try:
        from app.services.affiliate_payout_requests import process_unanswered_affiliate_payouts

        result["tasks"]["affiliate_payouts"] = process_unanswered_affiliate_payouts()
    except Exception as exc:
        result["tasks"]["affiliate_payouts"] = {"success": False, "error": str(exc)[:240]}

    return result
