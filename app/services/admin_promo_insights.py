"""Promo and Insider campaign performance for admin insights."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import Order, PromoCode
from app.services.ops_event_log import email_analytics_summary


def build_promo_performance(*, days: int = 30) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    redemptions: Counter[str] = Counter()
    revenue_by_promo: Counter[str] = Counter()

    factory = get_session_factory()
    active_promos: List[Dict[str, Any]] = []
    if factory is not None:
        with factory() as session:
            orders = session.scalars(
                select(Order)
                .where(Order.created_at >= since)
                .where(Order.status.in_(("paid", "delivered", "active", "suspended", "expired")))
            ).all()
            for order in orders:
                meta = order.metadata_ or {}
                promo = meta.get("promo") if isinstance(meta.get("promo"), dict) else None
                if promo and promo.get("code"):
                    code = str(promo["code"]).upper()
                    redemptions[code] += 1
                    revenue_by_promo[code] += int(order.amount_cents or 0)

            promos = session.scalars(select(PromoCode).where(PromoCode.is_active.is_(True))).all()
            for promo in promos:
                active_promos.append(
                    {
                        "code": promo.code,
                        "percent_off": promo.percent_off,
                        "redemption_count": promo.redemption_count or 0,
                        "max_redemptions": promo.max_redemptions,
                        "admin_approved": promo.admin_approved,
                    }
                )

    return {
        "top_redeemed": redemptions.most_common(10),
        "revenue_by_promo_cents": dict(revenue_by_promo.most_common(10)),
        "active_promos": active_promos[:20],
        "attribution_chart": _build_promo_attribution_chart(redemptions, revenue_by_promo),
        "insider_attribution": _build_insider_attribution(since),
    }


def _build_promo_attribution_chart(
    redemptions: Counter[str],
    revenue_by_promo: Counter[str],
) -> List[Dict[str, Any]]:
    if not redemptions:
        return []
    max_orders = max(redemptions.values()) or 1
    rows: List[Dict[str, Any]] = []
    for code, count in redemptions.most_common(8):
        rows.append(
            {
                "code": code,
                "orders": count,
                "revenue_cents": int(revenue_by_promo.get(code, 0)),
                "bar_pct": round(100 * count / max_orders),
            }
        )
    return rows


def _build_insider_attribution(since: datetime) -> List[Dict[str, Any]]:
    """Match Insider issue promo codes to paid orders in the period."""
    issue_promos: Dict[str, str] = {}
    try:
        from app.api import supabase_repository as db

        client = db.get_supabase_client()
        result = (
            client.table("insider_issues")
            .select("slug, promo_code")
            .not_.is_("promo_code", "null")
            .execute()
        )
        for row in result.data or []:
            promo = str(row.get("promo_code") or "").strip().upper()
            if promo:
                issue_promos[promo] = str(row.get("slug") or promo)
    except Exception:
        return []

    if not issue_promos:
        return []

    orders_by_promo: Counter[str] = Counter()
    revenue_by_promo: Counter[str] = Counter()
    factory = get_session_factory()
    if factory is None:
        return []

    with factory() as session:
        orders = session.scalars(
            select(Order)
            .where(Order.created_at >= since)
            .where(Order.status.in_(("paid", "delivered", "active", "suspended", "expired")))
        ).all()
        for order in orders:
            meta = order.metadata_ or {}
            promo = meta.get("promo") if isinstance(meta.get("promo"), dict) else None
            if not promo or not promo.get("code"):
                continue
            code = str(promo["code"]).upper()
            if code not in issue_promos:
                continue
            orders_by_promo[code] += 1
            revenue_by_promo[code] += int(order.amount_cents or 0)

    if not orders_by_promo:
        return []

    max_orders = max(orders_by_promo.values()) or 1
    rows: List[Dict[str, Any]] = []
    for promo_code, count in orders_by_promo.most_common(8):
        rows.append(
            {
                "issue_slug": issue_promos.get(promo_code, promo_code),
                "promo_code": promo_code,
                "orders": count,
                "revenue_cents": int(revenue_by_promo.get(promo_code, 0)),
                "bar_pct": round(100 * count / max_orders),
            }
        )
    return rows


def build_insider_performance() -> Dict[str, Any]:
    analytics = email_analytics_summary()
    insider_sends = analytics.get("insider_sends") or {}
    issues: List[Dict[str, Any]] = []
    try:
        from app.api import supabase_repository as db

        client = db.get_supabase_client()
        result = (
            client.table("insider_issues")
            .select("slug, subject, status, send_at, promo_code")
            .order("send_at", desc=True)
            .limit(12)
            .execute()
        )
        for row in result.data or []:
            slug = str(row.get("slug") or "")
            issues.append(
                {
                    "slug": slug,
                    "subject": row.get("subject"),
                    "status": row.get("status"),
                    "send_at": row.get("send_at"),
                    "promo_code": row.get("promo_code"),
                    "emails_logged": insider_sends.get(slug, 0),
                }
            )
    except Exception:
        pass

    return {
        "total_insider_emails_logged": sum(insider_sends.values()),
        "by_issue": insider_sends,
        "recent_issues": issues,
    }
