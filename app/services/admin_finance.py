"""Finance snapshot and CSV exports for admin."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from app.db.engine import get_session_factory
from app.db.models import AffiliateCommission, Order


def _period_start(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _wholesale_cents(metadata: dict) -> int:
    plan = metadata.get("fulfillment_plan") if isinstance(metadata.get("fulfillment_plan"), dict) else {}
    raw = plan.get("wholesale_cents") or metadata.get("wholesale_cents")
    try:
        return int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


def build_finance_snapshot(*, days: int = 30) -> Dict[str, Any]:
    factory = get_session_factory()
    if factory is None:
        return {"error": "DATABASE_URL not configured"}

    since = _period_start(days)
    with factory() as session:
        paid_statuses = ("paid", "delivered", "active", "suspended", "expired")
        orders = session.scalars(
            select(Order).where(Order.created_at >= since).where(Order.status.in_(paid_statuses))
        ).all()

        revenue_cents = 0
        complimentary_cents = 0
        wholesale_cents = 0
        by_country: Dict[str, int] = {}
        by_status: Dict[str, int] = {}

        for order in orders:
            amount = int(order.amount_cents or 0)
            meta = order.metadata_ or {}
            is_complimentary = isinstance(meta.get("complimentary"), dict) and meta["complimentary"].get(
                "granted_by"
            )
            if is_complimentary or amount == 0:
                complimentary_cents += amount
            else:
                revenue_cents += amount
                wholesale_cents += _wholesale_cents(meta)

            country = order.country or "Unknown"
            by_country[country] = by_country.get(country, 0) + amount
            by_status[order.status] = by_status.get(order.status, 0) + 1

        refunded = session.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.status == "refunded")
            .where(Order.updated_at >= since)
        ) or 0

        pending_fulfillment = session.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.status == "paid")
            .where(Order.qr_code_url.is_(None))
        ) or 0

        affiliate_liability = session.scalar(
            select(func.coalesce(func.sum(AffiliateCommission.commission_cents), 0))
            .where(AffiliateCommission.status == "approved")
        ) or 0

    margin_cents = max(0, revenue_cents - wholesale_cents)
    return {
        "period_days": days,
        "order_count": len(orders),
        "revenue_cents": revenue_cents,
        "wholesale_cents": wholesale_cents,
        "margin_cents": margin_cents,
        "margin_pct": round(margin_cents / revenue_cents * 100, 1) if revenue_cents else 0,
        "complimentary_orders": complimentary_cents,
        "refunded_count": int(refunded),
        "pending_fulfillment": int(pending_fulfillment),
        "affiliate_liability_cents": int(affiliate_liability or 0),
        "by_country": dict(sorted(by_country.items(), key=lambda x: -x[1])[:15]),
        "by_status": by_status,
    }


def build_finance_snapshot_support(*, days: int = 30) -> Dict[str, Any]:
    """Read-only finance view for support — no margin or affiliate liability."""
    full = build_finance_snapshot(days=days)
    if full.get("error"):
        return full
    return {
        "period_days": full["period_days"],
        "order_count": full["order_count"],
        "revenue_cents": full["revenue_cents"],
        "refunded_count": full["refunded_count"],
        "pending_fulfillment": full["pending_fulfillment"],
        "by_status": full.get("by_status") or {},
        "read_only": True,
    }


def export_orders_csv(*, days: int = 90) -> str:
    factory = get_session_factory()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "order_number",
            "email",
            "country",
            "package_name",
            "amount_cents",
            "currency",
            "status",
            "paid_at",
            "fulfilled_at",
            "refunded_at",
        ]
    )
    if factory is None:
        return buffer.getvalue()

    since = _period_start(days)
    with factory() as session:
        rows = session.scalars(select(Order).where(Order.created_at >= since).order_by(Order.created_at.desc())).all()
        for order in rows:
            writer.writerow(
                [
                    order.order_number,
                    order.email,
                    order.country,
                    order.package_name,
                    order.amount_cents,
                    order.currency,
                    order.status,
                    order.paid_at.isoformat() if order.paid_at else "",
                    order.fulfilled_at.isoformat() if order.fulfilled_at else "",
                    order.refunded_at.isoformat() if order.refunded_at else "",
                ]
            )
    return buffer.getvalue()


def export_commissions_csv() -> str:
    factory = get_session_factory()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["order_number", "commission_cents", "commission_percent", "status", "fulfilled_at"]
    )
    if factory is None:
        return buffer.getvalue()

    with factory() as session:
        rows = session.scalars(
            select(AffiliateCommission).order_by(AffiliateCommission.created_at.desc()).limit(5000)
        ).all()
        for row in rows:
            writer.writerow(
                [
                    row.order_number,
                    row.commission_cents,
                    row.commission_percent,
                    row.status,
                    row.fulfilled_at.isoformat() if row.fulfilled_at else "",
                ]
            )
    return buffer.getvalue()
