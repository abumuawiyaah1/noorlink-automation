"""Daily morning business brief for admins (America/New_York)."""

from __future__ import annotations

import html
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.services.admin_notifications import notifications_for_role
from app.services.admin_report_core import (
    analyze_orders,
    format_money,
    is_report_send_hour,
    mark_report_sent,
    ny_now,
    paid_orders_between,
    report_already_sent,
    yesterday_window,
)
from app.services.admin_report_recipients import admin_report_recipient_emails
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger(__name__)

AUDIT_ACTION = "daily_admin_report_sent"


def _build_insight(stats: Dict[str, Any]) -> str:
    revenue = int(stats.get("revenue_cents") or 0)
    if revenue <= 0:
        return (
            "No paid orders yesterday — push one Insider touchpoint and check that "
            "top destinations are easy to find from the homepage."
        )

    destinations = stats.get("top_destinations") or []
    packages = stats.get("top_packages") or []
    if destinations:
        top_country, top_country_cents = destinations[0]
        share = round(top_country_cents / revenue * 100)
        if packages:
            top_pkg = packages[0]
            return (
                f"{html.escape(top_country)} drove {share}% of yesterday's revenue. "
                f"Lead with {html.escape(str(top_pkg.get('name') or 'your top plan'))} "
                f"in hero, Insider, and partner posts."
            )
        return (
            f"{html.escape(top_country)} drove {share}% of yesterday's revenue — "
            "keep that destination prominent above the fold."
        )

    if packages:
        top_pkg = packages[0]
        share = round(int(top_pkg.get("revenue_cents") or 0) / revenue * 100)
        return (
            f"{html.escape(str(top_pkg.get('name') or 'Top plan'))} was "
            f"{share}% of yesterday's revenue — feature it in checkout and email."
        )

    return "Revenue came in yesterday — review top packages and double down on what converted."


def build_daily_summary_html(*, now_utc: Optional[Any] = None) -> str:
    window = yesterday_window(now_utc)
    stats = analyze_orders(paid_orders_between(window.start_utc, window.end_utc))
    alerts = notifications_for_role("admin")

    lines = [
        "<h2>NoorLink daily brief</h2>",
        f"<p><strong>{html.escape(window.label)}</strong> (New York)</p>",
        "<h3>Yesterday</h3>",
        "<ul>",
        f"<li>Revenue: <strong>{format_money(int(stats['revenue_cents']))}</strong></li>",
        f"<li>Orders: <strong>{stats.get('paid_units', 0)}</strong></li>",
        f"<li>Est. margin: <strong>{format_money(int(stats['margin_cents']))}</strong> ({stats.get('margin_pct', 0)}%)</li>",
        "</ul>",
    ]

    packages = stats.get("top_packages") or []
    lines.append("<h3>Top packages</h3>")
    if packages:
        lines.append("<ul>")
        for row in packages[:3]:
            lines.append(
                "<li>"
                f"{html.escape(str(row['name']))} · "
                f"{row['units']} sold · "
                f"margin {format_money(int(row['margin_cents']))}"
                "</li>"
            )
        lines.append("</ul>")
    else:
        lines.append("<p>No paid packages yesterday.</p>")

    destinations = stats.get("top_destinations") or []
    lines.append("<h3>Top destinations</h3>")
    if destinations:
        lines.append("<ul>")
        for country, cents in destinations[:3]:
            lines.append(f"<li>{html.escape(country)} · {format_money(int(cents))} revenue</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>No destination sales yesterday.</p>")

    sources = stats.get("top_sources") or []
    lines.append("<h3>Traffic source</h3>")
    if sources:
        lines.append("<ul>")
        for label, count in sources:
            lines.append(f"<li>{html.escape(label)} · {count} order(s)</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>No attributed orders yesterday.</p>")

    lines.append("<h3>Needs attention</h3>")
    if alerts:
        lines.append("<ul>")
        for item in alerts[:8]:
            lines.append(f"<li>{html.escape(item.title)}: {item.count}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>All clear — no open admin alerts.</p>")

    lines.append("<h3>Today's focus</h3>")
    lines.append(f"<p>{_build_insight(stats)}</p>")
    lines.append('<p>View dashboard: <a href="https://api.noorlink.co/admin">NoorLink Admin</a></p>')
    return "\n".join(lines)


def _subject_line(stats: Dict[str, Any], alerts: List[Any]) -> str:
    revenue = stats.get("revenue_cents", 0) / 100
    orders = stats.get("paid_units", 0)
    urgent = next((item for item in alerts if item.severity == "urgent"), None)
    if urgent:
        hook = f"{urgent.count} {urgent.title.lower()}"
    elif alerts:
        hook = f"{len(alerts)} alert(s)"
    else:
        hook = "all clear"
    return f"NoorLink daily — ${revenue:,.2f} · {orders} orders · {hook}"


def send_daily_summary_email(*, force: bool = False, now_utc: Optional[Any] = None) -> Dict[str, Any]:
    moment = now_utc
    ny_date: date = ny_now(moment).date()

    if not force and not is_report_send_hour(moment):
        return {"sent": 0, "skipped": "Outside 6:00 New York send window."}

    record_id = ny_date.isoformat()
    if not force and report_already_sent(AUDIT_ACTION, record_id):
        return {"sent": 0, "skipped": f"Already sent for {record_id}."}

    recipients = admin_report_recipient_emails()
    if not recipients:
        return {"sent": 0, "error": "No admin report recipients configured."}

    window = yesterday_window(moment)
    stats = analyze_orders(paid_orders_between(window.start_utc, window.end_utc))
    alerts = notifications_for_role("admin")
    html_body = build_daily_summary_html(now_utc=moment)
    subject = _subject_line(stats, alerts)

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
            logger.exception("Failed to record daily admin report send for %s", record_id)

    return {
        "sent": sent,
        "recipients": recipients,
        "subject": subject,
        "ny_date": record_id,
        "errors": errors,
    }
