"""Business metrics for admin insights."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import func, select

from app.db.engine import get_session_factory
from app.db.models import Order, SupportTicket
from app.services.admin_promo_insights import build_insider_performance, build_promo_performance
from app.services.admin_support_sla import sla_summary
from app.services.analytics_store import get_trending
from app.services.ops_event_log import email_analytics_summary, list_ops_events
from app.services.provider_balances import fetch_provider_balances_sync


def build_business_metrics(*, days: int = 30) -> Dict[str, Any]:
    factory = get_session_factory()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    plans_by_country: Counter[str] = Counter()
    plans_by_name: Counter[str] = Counter()
    support_by_category: Counter[str] = Counter()
    order_count = 0

    if factory is not None:
        with factory() as session:
            orders = session.scalars(
                select(Order)
                .where(Order.created_at >= since)
                .where(Order.status.in_(("paid", "delivered", "active", "suspended", "expired")))
            ).all()
            order_count = len(orders)
            for order in orders:
                plans_by_country[order.country or "Unknown"] += 1
                plans_by_name[order.package_name or "Unknown"] += 1

            tickets = session.scalars(
                select(SupportTicket).where(SupportTicket.created_at >= since)
            ).all()
            for ticket in tickets:
                support_by_category[ticket.category or "other"] += 1

    recent_failures = [
        e
        for e in list_ops_events(limit=50, event_type="fulfillment_failed")
    ]

    return {
        "period_days": days,
        "orders_sold": order_count,
        "top_countries": plans_by_country.most_common(10),
        "top_plans": plans_by_name.most_common(10),
        "support_by_category": support_by_category.most_common(10),
        "trending_searches": get_trending(limit=5),
        "email_analytics": email_analytics_summary(),
        "promo_performance": build_promo_performance(days=days),
        "insider_performance": build_insider_performance(),
        "provider_balances": fetch_provider_balances_sync(),
        "sla": sla_summary(),
        "recent_fulfillment_failures": recent_failures[:10],
    }
