"""Shared analytics and scheduling helpers for admin business reports."""

from __future__ import annotations

import html
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.api import supabase_repository as db
from app.db.engine import get_session_factory
from app.db.models import AdminAuditLog, AffiliateCommission, Order
from app.services.admin_finance import _wholesale_cents
from app.services.analytics_store import get_trending

logger = logging.getLogger(__name__)

NY_TZ = ZoneInfo("America/New_York")
PAID_STATUSES = ("paid", "delivered", "active", "suspended", "expired")
REFUNDED_STATUS = "refunded"
SEND_HOUR_NY = 6


@dataclass(frozen=True)
class PeriodWindow:
    label: str
    start_utc: datetime
    end_utc: datetime


def ny_now(now_utc: Optional[datetime] = None) -> datetime:
    moment = now_utc or datetime.now(timezone.utc)
    return moment.astimezone(NY_TZ)


def is_report_send_hour(now_utc: Optional[datetime] = None) -> bool:
    return ny_now(now_utc).hour == SEND_HOUR_NY


def period_window_days(*, days: int, end_ny: Optional[datetime] = None) -> PeriodWindow:
    end_local = (end_ny or ny_now()).replace(hour=0, minute=0, second=0, microsecond=0)
    start_local = end_local - timedelta(days=days)
    return PeriodWindow(
        label=f"last {days} days",
        start_utc=start_local.astimezone(timezone.utc),
        end_utc=end_local.astimezone(timezone.utc),
    )


def yesterday_window(now_utc: Optional[datetime] = None) -> PeriodWindow:
    local = ny_now(now_utc)
    today_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    return PeriodWindow(
        label=f"{yesterday_start:%A, %b} {yesterday_start.day}",
        start_utc=yesterday_start.astimezone(timezone.utc),
        end_utc=today_start.astimezone(timezone.utc),
    )


def last_week_window(now_utc: Optional[datetime] = None) -> PeriodWindow:
    local = ny_now(now_utc)
    end = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=7)
    return PeriodWindow(
        label=f"{start:%b} {start.day} – {end - timedelta(days=1):%b} {(end - timedelta(days=1)).day}",
        start_utc=start.astimezone(timezone.utc),
        end_utc=end.astimezone(timezone.utc),
    )


def prior_week_window(now_utc: Optional[datetime] = None) -> PeriodWindow:
    current = last_week_window(now_utc)
    span = current.end_utc - current.start_utc
    return PeriodWindow(
        label="prior 7 days",
        start_utc=current.start_utc - span,
        end_utc=current.start_utc,
    )


def last_month_window(now_utc: Optional[datetime] = None) -> PeriodWindow:
    return period_window_days(days=30, end_ny=ny_now(now_utc))


def prior_month_window(now_utc: Optional[datetime] = None) -> PeriodWindow:
    current = last_month_window(now_utc)
    span = current.end_utc - current.start_utc
    return PeriodWindow(
        label="prior 30 days",
        start_utc=current.start_utc - span,
        end_utc=current.start_utc,
    )


def report_already_sent(action: str, record_id: str) -> bool:
    factory = get_session_factory()
    if factory is None:
        return False
    with factory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(AdminAuditLog.action == action)
            .where(AdminAuditLog.record_id == record_id)
        ) or 0
        return int(count) > 0


def mark_report_sent(action: str, record_id: str, *, recipient_count: int) -> None:
    factory = get_session_factory()
    if factory is None:
        return
    with factory() as session:
        session.add(
            AdminAuditLog(
                admin_user_id=None,
                admin_username="system",
                action=action,
                table_name="admin_reports",
                record_id=record_id,
                new_values={"recipient_count": recipient_count},
                ip_address=None,
            )
        )
        session.commit()


def paid_orders_between(start_utc: datetime, end_utc: datetime) -> List[Order]:
    factory = get_session_factory()
    if factory is None:
        return []
    with factory() as session:
        return list(
            session.scalars(
                select(Order)
                .where(Order.created_at >= start_utc)
                .where(Order.created_at < end_utc)
                .where(Order.status.in_(PAID_STATUSES))
                .order_by(Order.created_at.desc())
            ).all()
        )


def refunded_count_between(start_utc: datetime, end_utc: datetime) -> int:
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.status == REFUNDED_STATUS)
                .where(Order.updated_at >= start_utc)
                .where(Order.updated_at < end_utc)
            )
            or 0
        )


def affiliate_liability_cents() -> int:
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        return int(
            session.scalar(
                select(func.coalesce(func.sum(AffiliateCommission.commission_cents), 0)).where(
                    AffiliateCommission.status == "approved"
                )
            )
            or 0
        )


def newsletter_signups_between(start_utc: datetime, end_utc: datetime) -> int:
    try:
        client = db.get_supabase_client()
        result = (
            client.table("newsletter_subscribers")
            .select("email", count="exact")
            .gte("subscribed_at", start_utc.isoformat())
            .lt("subscribed_at", end_utc.isoformat())
            .is_("unsubscribed_at", "null")
            .execute()
        )
        return int(result.count or 0)
    except Exception as exc:
        logger.warning("Newsletter signup count failed: %s", exc)
        return 0


def _is_complimentary(order: Order) -> bool:
    meta = order.metadata_ or {}
    complimentary = meta.get("complimentary")
    return isinstance(complimentary, dict) and bool(complimentary.get("granted_by"))


def _customer_country(order: Order) -> Optional[str]:
    meta = order.metadata_ or {}
    customer = meta.get("customer")
    if isinstance(customer, dict):
        country = str(customer.get("billing_country") or "").strip().upper()
        if len(country) == 2:
            return country
    attribution = meta.get("attribution")
    if isinstance(attribution, dict):
        country = str(attribution.get("billing_country") or "").strip().upper()
        if len(country) == 2:
            return country
    return None


def _utm_bucket(order: Order) -> Optional[str]:
    meta = order.metadata_ or {}
    attribution = meta.get("attribution")
    if not isinstance(attribution, dict):
        return None
    source = str(attribution.get("utm_source") or "").strip().lower()
    medium = str(attribution.get("utm_medium") or "").strip().lower()
    if source and medium:
        return f"UTM: {source}/{medium}"
    if source:
        return f"UTM: {source}"
    return None


def traffic_label(order: Order) -> str:
    utm = _utm_bucket(order)
    if utm:
        return utm
    meta = order.metadata_ or {}
    affiliate = meta.get("affiliate")
    if isinstance(affiliate, dict):
        code = str(affiliate.get("code") or "partner").strip().upper()
        return f"Affiliate: {code}"
    promo = meta.get("promo")
    if isinstance(promo, dict):
        code = str(promo.get("code") or "promo").strip().upper()
        return f"Promo: {code}"
    return "Direct"


def analyze_orders(orders: List[Order]) -> Dict[str, Any]:
    revenue_cents = 0
    wholesale_cents = 0
    paid_units = 0
    by_package: Dict[str, Dict[str, Any]] = {}
    by_destination: Dict[str, int] = defaultdict(int)
    by_customer_country: Dict[str, int] = defaultdict(int)
    by_source: Dict[str, int] = defaultdict(int)
    by_affiliate: Dict[str, int] = defaultdict(int)
    emails_in_period: Dict[str, int] = defaultdict(int)

    for order in orders:
        email = (order.email or "").strip().lower()
        if email:
            emails_in_period[email] += 1

        amount = int(order.amount_cents or 0)
        meta = order.metadata_ or {}
        if _is_complimentary(order) or amount == 0:
            continue

        paid_units += 1
        wholesale = _wholesale_cents(meta)
        revenue_cents += amount
        wholesale_cents += wholesale
        margin = max(0, amount - wholesale)

        pkg_key = (order.package_name or "Unknown").strip()
        pkg = by_package.setdefault(
            pkg_key,
            {
                "name": pkg_key,
                "units": 0,
                "revenue_cents": 0,
                "margin_cents": 0,
                "wholesale_cents": 0,
            },
        )
        pkg["units"] += 1
        pkg["revenue_cents"] += amount
        pkg["margin_cents"] += margin
        pkg["wholesale_cents"] += wholesale

        destination = (order.country or "Unknown").strip()
        by_destination[destination] += amount

        customer_country = _customer_country(order)
        if customer_country:
            by_customer_country[customer_country] += 1

        by_source[traffic_label(order)] += 1

        affiliate = meta.get("affiliate")
        if isinstance(affiliate, dict):
            code = str(affiliate.get("code") or "").strip().upper()
            if code:
                by_affiliate[code] += amount

    margin_cents = max(0, revenue_cents - wholesale_cents)
    margin_pct = round(margin_cents / revenue_cents * 100, 1) if revenue_cents else 0.0
    aov_cents = round(revenue_cents / paid_units) if paid_units else 0

    package_rows = list(by_package.values())
    for row in package_rows:
        rev = int(row["revenue_cents"])
        row["margin_pct"] = round(int(row["margin_cents"]) / rev * 100, 1) if rev else 0.0

    repeat_buyers = sum(1 for count in emails_in_period.values() if count > 1)

    top_packages = sorted(
        package_rows,
        key=lambda row: (-row["revenue_cents"], -row["units"], row["name"]),
    )
    margin_leaders = sorted(
        [row for row in package_rows if row["units"] > 0],
        key=lambda row: (-row["margin_pct"], -row["margin_cents"], row["name"]),
    )[:3]
    margin_traps = sorted(
        [row for row in package_rows if row["units"] > 0 and row["revenue_cents"] > 0],
        key=lambda row: (row["margin_pct"], -row["revenue_cents"]),
    )[:3]

    return {
        "order_count": len(orders),
        "paid_units": paid_units,
        "revenue_cents": revenue_cents,
        "margin_cents": margin_cents,
        "margin_pct": margin_pct,
        "aov_cents": aov_cents,
        "repeat_buyers": repeat_buyers,
        "top_packages": top_packages[:5],
        "top_destinations": sorted(by_destination.items(), key=lambda item: -item[1])[:5],
        "top_customer_countries": sorted(by_customer_country.items(), key=lambda item: -item[1])[:5],
        "top_sources": sorted(by_source.items(), key=lambda item: (-item[1], item[0]))[:8],
        "top_affiliates": sorted(by_affiliate.items(), key=lambda item: -item[1])[:5],
        "margin_leaders": margin_leaders,
        "margin_traps": margin_traps,
    }


def compare_periods(current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    def delta_pct(cur: int, prev: int) -> Optional[float]:
        if prev <= 0:
            return None if cur <= 0 else 100.0
        return round((cur - prev) / prev * 100, 1)

    return {
        "revenue_delta_pct": delta_pct(
            int(current.get("revenue_cents") or 0),
            int(previous.get("revenue_cents") or 0),
        ),
        "orders_delta_pct": delta_pct(
            int(current.get("paid_units") or 0),
            int(previous.get("paid_units") or 0),
        ),
        "margin_delta_pct": delta_pct(
            int(current.get("margin_cents") or 0),
            int(previous.get("margin_cents") or 0),
        ),
    }


def format_money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def format_delta(label: str, delta_pct: Optional[float]) -> str:
    if delta_pct is None:
        return f"{label}: n/a vs prior period"
    arrow = "↑" if delta_pct > 0 else "↓" if delta_pct < 0 else "→"
    return f"{label}: {arrow} {abs(delta_pct):.1f}% vs prior period"


def hero_search_interest() -> List[str]:
    try:
        trending = get_trending(limit=5)
        return [item["destination"] for item in trending if item.get("destination")]
    except Exception:
        return []


def render_list_section(title: str, items: List[str], *, empty: str) -> str:
    lines = [f"<h3>{html.escape(title)}</h3>"]
    if items:
        lines.append("<ul>")
        lines.extend(f"<li>{item}</li>" for item in items)
        lines.append("</ul>")
    else:
        lines.append(f"<p>{html.escape(empty)}</p>")
    return "\n".join(lines)
