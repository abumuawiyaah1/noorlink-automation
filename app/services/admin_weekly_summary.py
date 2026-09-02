"""Weekly scorecard email for admins — Mondays at 6:00 New York."""

from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.admin_notifications import notifications_for_role
from app.services.admin_report_core import (
    affiliate_liability_cents,
    analyze_orders,
    compare_periods,
    format_delta,
    format_money,
    hero_search_interest,
    is_report_send_hour,
    last_week_window,
    mark_report_sent,
    newsletter_signups_between,
    ny_now,
    paid_orders_between,
    prior_week_window,
    refunded_count_between,
    report_already_sent,
    render_list_section,
)
from app.services.admin_report_recipients import admin_report_recipient_emails
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger(__name__)

AUDIT_ACTION = "weekly_admin_report_sent"


def should_send_weekly_report(now_utc: Optional[datetime] = None) -> bool:
    local = ny_now(now_utc)
    return local.weekday() == 0 and is_report_send_hour(now_utc)


def build_weekly_summary_html(*, now_utc: Optional[datetime] = None) -> str:
    window = last_week_window(now_utc)
    prior = prior_week_window(now_utc)
    orders = paid_orders_between(window.start_utc, window.end_utc)
    stats = analyze_orders(orders)
    prior_stats = analyze_orders(paid_orders_between(prior.start_utc, prior.end_utc))
    deltas = compare_periods(stats, prior_stats)
    refunds = refunded_count_between(window.start_utc, window.end_utc)
    signups = newsletter_signups_between(window.start_utc, window.end_utc)
    alerts = notifications_for_role("admin")
    searches = hero_search_interest()

    lines = [
        "<h2>NoorLink weekly scorecard</h2>",
        f"<p><strong>{html.escape(window.label)}</strong> (New York)</p>",
        "<h3>Week at a glance</h3>",
        "<ul>",
        f"<li>Revenue: <strong>{format_money(int(stats['revenue_cents']))}</strong> ({format_delta('revenue', deltas['revenue_delta_pct'])})</li>",
        f"<li>Paid orders: <strong>{stats.get('paid_units', 0)}</strong> ({format_delta('orders', deltas['orders_delta_pct'])})</li>",
        f"<li>Est. margin: <strong>{format_money(int(stats['margin_cents']))}</strong> ({stats.get('margin_pct', 0)}%) ({format_delta('margin', deltas['margin_delta_pct'])})</li>",
        f"<li>Average order: <strong>{format_money(int(stats.get('aov_cents') or 0))}</strong></li>",
        f"<li>Refunds: <strong>{refunds}</strong></li>",
        f"<li>Repeat buyers: <strong>{stats.get('repeat_buyers', 0)}</strong></li>",
        f"<li>Insider signups: <strong>{signups}</strong></li>",
        f"<li>Affiliate liability: <strong>{format_money(affiliate_liability_cents())}</strong></li>",
        "</ul>",
    ]

    package_items = [
        f"{html.escape(str(row['name']))} · {row['units']} sold · margin {format_money(int(row['margin_cents']))} ({row.get('margin_pct', 0)}%)"
        for row in (stats.get("top_packages") or [])[:5]
    ]
    lines.append(render_list_section("Top packages", package_items, empty="No paid packages this week."))

    destination_items = [
        f"{html.escape(country)} · {format_money(int(cents))}"
        for country, cents in (stats.get("top_destinations") or [])[:5]
    ]
    lines.append(render_list_section("Top destinations (eSIM bought for)", destination_items, empty="No destination sales this week."))

    customer_items = [
        f"{html.escape(country)} · {count} order(s)"
        for country, count in (stats.get("top_customer_countries") or [])[:5]
    ]
    lines.append(
        render_list_section(
            "Customer billing countries",
            customer_items,
            empty="No billing country captured yet — fills in as new Stripe checkouts complete.",
        )
    )

    source_items = [
        f"{html.escape(label)} · {count} order(s)"
        for label, count in (stats.get("top_sources") or [])[:8]
    ]
    lines.append(render_list_section("Channel mix", source_items, empty="No attributed orders this week."))

    affiliate_items = [
        f"{html.escape(code)} · {format_money(int(cents))}"
        for code, cents in (stats.get("top_affiliates") or [])[:5]
    ]
    lines.append(render_list_section("Partner leaderboard", affiliate_items, empty="No affiliate-attributed revenue this week."))

    leader_items = [
        f"{html.escape(str(row['name']))} · {row.get('margin_pct', 0)}% margin"
        for row in (stats.get("margin_leaders") or [])[:3]
    ]
    lines.append(render_list_section("Margin leaders", leader_items, empty="Not enough data yet."))

    trap_items = [
        f"{html.escape(str(row['name']))} · {row.get('margin_pct', 0)}% margin on {format_money(int(row['revenue_cents']))} revenue"
        for row in (stats.get("margin_traps") or [])[:3]
    ]
    lines.append(render_list_section("Margin watchlist", trap_items, empty="No thin-margin packages flagged."))

    if searches:
        lines.append(render_list_section("Hero search interest", [html.escape(item) for item in searches], empty=""))

    lines.append("<h3>Needs attention</h3>")
    if alerts:
        lines.append("<ul>")
        for item in alerts[:8]:
            lines.append(f"<li>{html.escape(item.title)}: {item.count}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>All clear — no open admin alerts.</p>")

    focus = _weekly_focus(stats, prior_stats, deltas, searches)
    lines.append("<h3>This week's focus</h3>")
    lines.append(f"<p>{focus}</p>")
    lines.append('<p>View dashboard: <a href="https://api.noorlink.co/admin">NoorLink Admin</a></p>')
    return "\n".join(lines)


def _weekly_focus(
    stats: Dict[str, Any],
    prior_stats: Dict[str, Any],
    deltas: Dict[str, Any],
    searches: List[str],
) -> str:
    revenue = int(stats.get("revenue_cents") or 0)
    if revenue <= 0:
        search_hint = f" Hero searches leaned toward {html.escape(searches[0])}." if searches else ""
        return (
            "No paid orders this week — tighten homepage CTAs, send Insider, and ask top partners for one post."
            + search_hint
        )

    rev_delta = deltas.get("revenue_delta_pct")
    packages = stats.get("top_packages") or []
    destinations = stats.get("top_destinations") or []
    traps = stats.get("margin_traps") or []

    parts: List[str] = []
    if rev_delta is not None:
        if rev_delta < -10:
            parts.append(f"Revenue slipped {abs(rev_delta):.1f}% week over week.")
        elif rev_delta > 10:
            parts.append(f"Revenue grew {rev_delta:.1f}% week over week — keep the same offers live.")

    if destinations:
        country, cents = destinations[0]
        parts.append(
            f"Double down on {html.escape(country)} ({round(cents / revenue * 100)}% of revenue)."
        )
    if packages:
        parts.append(f"Feature {html.escape(str(packages[0]['name']))} in ads and checkout.")
    if traps and int(traps[0].get("margin_pct") or 0) < 35:
        parts.append(
            f"Review pricing on {html.escape(str(traps[0]['name']))} — margin is only {traps[0].get('margin_pct', 0)}%."
        )
    if searches:
        parts.append(f"Site searches spiked for {html.escape(searches[0])} — make that path one click from home.")

    if not parts:
        parts.append("Steady week — keep fulfillment fast and support under 24 hours.")
    return " ".join(parts)


def send_weekly_summary_email(*, force: bool = False, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    local = ny_now(now_utc)
    if not force and not should_send_weekly_report(now_utc):
        return {"sent": 0, "skipped": "Weekly report only sends Monday at 6:00 New York."}

    record_id = f"{local.isocalendar().year}-W{local.isocalendar().week:02d}"
    if not force and report_already_sent(AUDIT_ACTION, record_id):
        return {"sent": 0, "skipped": f"Already sent for {record_id}."}

    recipients = admin_report_recipient_emails()
    if not recipients:
        return {"sent": 0, "error": "No admin report recipients configured."}

    window = last_week_window(now_utc)
    stats = analyze_orders(paid_orders_between(window.start_utc, window.end_utc))
    html_body = build_weekly_summary_html(now_utc=now_utc)
    subject = (
        f"NoorLink weekly — {format_money(int(stats['revenue_cents']))} · "
        f"{stats.get('paid_units', 0)} orders"
    )

    sent = 0
    errors: List[str] = []
    for email in recipients:
        try:
            send_email(to_email=email, subject=subject, html_body=html_body)
            sent += 1
        except EmailDeliveryError as exc:
            errors.append(f"{email}: {exc}")

    if sent and not force:
        try:
            mark_report_sent(AUDIT_ACTION, record_id, recipient_count=sent)
        except Exception:
            logger.exception("Failed to record weekly admin report send for %s", record_id)

    return {"sent": sent, "recipients": recipients, "subject": subject, "period": record_id, "errors": errors}
