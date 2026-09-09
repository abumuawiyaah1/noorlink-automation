"""Monthly strategy review email for admins — 1st of month at 6:00 New York."""

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
    last_month_window,
    mark_report_sent,
    newsletter_signups_between,
    ny_now,
    paid_orders_between,
    prior_month_window,
    refunded_count_between,
    report_already_sent,
    render_list_section,
)
from app.services.admin_report_recipients import admin_report_recipient_emails
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger(__name__)

AUDIT_ACTION = "monthly_admin_report_sent"


def should_send_monthly_report(now_utc: Optional[datetime] = None) -> bool:
    local = ny_now(now_utc)
    if local.day == 1:
        return is_report_send_hour(now_utc)
    # Late GitHub cron: still send once if the 1st was missed.
    return local.day == 2


def build_monthly_summary_html(*, now_utc: Optional[datetime] = None) -> str:
    window = last_month_window(now_utc)
    prior = prior_month_window(now_utc)
    stats = analyze_orders(paid_orders_between(window.start_utc, window.end_utc))
    prior_stats = analyze_orders(paid_orders_between(prior.start_utc, prior.end_utc))
    deltas = compare_periods(stats, prior_stats)
    refunds = refunded_count_between(window.start_utc, window.end_utc)
    signups = newsletter_signups_between(window.start_utc, window.end_utc)
    alerts = notifications_for_role("admin")
    searches = hero_search_interest()

    lines = [
        "<h2>NoorLink monthly review</h2>",
        f"<p><strong>{html.escape(window.label)}</strong> (New York)</p>",
        "<h3>Month at a glance</h3>",
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
        f"{html.escape(str(row['name']))} · {row['units']} sold · {format_money(int(row['revenue_cents']))} revenue · margin {row.get('margin_pct', 0)}%"
        for row in (stats.get("top_packages") or [])[:5]
    ]
    lines.append(render_list_section("Top packages", package_items, empty="No paid packages this month."))

    destination_items = [
        f"{html.escape(country)} · {format_money(int(cents))}"
        for country, cents in (stats.get("top_destinations") or [])[:5]
    ]
    lines.append(render_list_section("Top destinations (eSIM bought for)", destination_items, empty="No destination sales this month."))

    customer_items = [
        f"{html.escape(country)} · {count} order(s)"
        for country, count in (stats.get("top_customer_countries") or [])[:5]
    ]
    lines.append(
        render_list_section(
            "Where customers paid from",
            customer_items,
            empty="Billing country will populate from Stripe as new orders complete.",
        )
    )

    source_items = [
        f"{html.escape(label)} · {count} order(s)"
        for label, count in (stats.get("top_sources") or [])[:8]
    ]
    lines.append(render_list_section("Acquisition channels", source_items, empty="No attributed orders this month."))

    affiliate_items = [
        f"{html.escape(code)} · {format_money(int(cents))}"
        for code, cents in (stats.get("top_affiliates") or [])[:5]
    ]
    lines.append(render_list_section("Top partners", affiliate_items, empty="No affiliate-attributed revenue this month."))

    leader_items = [
        f"{html.escape(str(row['name']))} · {format_money(int(row['margin_cents']))} margin ({row.get('margin_pct', 0)}%)"
        for row in (stats.get("margin_leaders") or [])[:3]
    ]
    lines.append(render_list_section("Margin winners", leader_items, empty="Not enough data yet."))

    trap_items = [
        f"{html.escape(str(row['name']))} · {row.get('margin_pct', 0)}% margin · {format_money(int(row['revenue_cents']))} revenue"
        for row in (stats.get("margin_traps") or [])[:3]
    ]
    lines.append(render_list_section("Pricing review candidates", trap_items, empty="No thin-margin packages flagged."))

    if searches:
        lines.append(render_list_section("On-site search demand", [html.escape(item) for item in searches], empty=""))

    lines.append("<h3>Needs attention</h3>")
    if alerts:
        lines.append("<ul>")
        for item in alerts[:8]:
            lines.append(f"<li>{html.escape(item.title)}: {item.count}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>All clear — no open admin alerts.</p>")

    lines.append("<h3>Strategic focus for next month</h3>")
    lines.append(f"<p>{_monthly_focus(stats, prior_stats, deltas, searches)}</p>")
    lines.append('<p>View dashboard: <a href="https://api.noorlink.co/admin">NoorLink Admin</a></p>')
    return "\n".join(lines)


def _monthly_focus(
    stats: Dict[str, Any],
    prior_stats: Dict[str, Any],
    deltas: Dict[str, Any],
    searches: List[str],
) -> str:
    revenue = int(stats.get("revenue_cents") or 0)
    if revenue <= 0:
        return (
            "Treat next month as a launch sprint: one flagship destination landing page, "
            "one partner push, and one Insider offer with a tracked promo code."
        )

    packages = stats.get("top_packages") or []
    destinations = stats.get("top_destinations") or []
    affiliates = stats.get("top_affiliates") or []
    traps = stats.get("margin_traps") or []

    actions: List[str] = []
    rev_delta = deltas.get("revenue_delta_pct")
    if rev_delta is not None and rev_delta < 0:
        actions.append(f"Revenue is down {abs(rev_delta):.1f}% month over month — audit checkout drop-off and support response time.")

    if destinations:
        country, cents = destinations[0]
        actions.append(
            f"Build next month's creative around {html.escape(country)} ({round(cents / revenue * 100)}% of revenue)."
        )
    if packages:
        actions.append(f"Keep {html.escape(str(packages[0]['name']))} as the default recommended plan.")
    if affiliates:
        code, cents = affiliates[0]
        actions.append(
            f"Thank partner {html.escape(code)} ({format_money(int(cents))}) and ask what converted."
        )
    if traps and int(traps[0].get("margin_pct") or 0) < 40:
        actions.append(
            f"Reprice or remap fulfillment for {html.escape(str(traps[0]['name']))} before scaling ads."
        )
    if searches:
        actions.append(f"Add a homepage module for {html.escape(searches[0])} — shoppers are already searching for it.")

    if int(stats.get("repeat_buyers") or 0) > 0:
        actions.append("You have repeat buyers — add a post-trip email asking for referrals with ?ref= links.")

    if not actions:
        actions.append("Solid month — protect margin, keep support fast, and test one new destination bundle.")

    return " ".join(actions)


def send_monthly_summary_email(*, force: bool = False, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    local = ny_now(now_utc)
    if not force and not should_send_monthly_report(now_utc):
        return {"sent": 0, "skipped": "Monthly report sends on the 1st after 6:00 New York (2nd catch-up)."}

    record_id = f"{local.year}-{local.month:02d}"
    if not force and report_already_sent(AUDIT_ACTION, record_id):
        return {"sent": 0, "skipped": f"Already sent for {record_id}."}

    recipients = admin_report_recipient_emails()
    if not recipients:
        return {"sent": 0, "error": "No admin report recipients configured."}

    stats = analyze_orders(
        paid_orders_between(last_month_window(now_utc).start_utc, last_month_window(now_utc).end_utc)
    )
    html_body = build_monthly_summary_html(now_utc=now_utc)
    subject = (
        f"NoorLink monthly — {format_money(int(stats['revenue_cents']))} · "
        f"{stats.get('paid_units', 0)} orders · {stats.get('margin_pct', 0)}% margin"
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
            logger.exception("Failed to record monthly admin report send for %s", record_id)

    return {"sent": sent, "recipients": recipients, "subject": subject, "period": record_id, "errors": errors}
