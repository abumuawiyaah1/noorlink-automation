"""Monthly business summary email to admin."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import select

from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import AdminUser
from app.services.admin_finance import build_finance_snapshot
from app.services.admin_notifications import notifications_for_role
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger(__name__)


def _recipient_emails() -> List[str]:
    settings = get_settings()
    emails: List[str] = []
    ops = (settings.ops_alert_email or "").strip().lower()
    if ops and "@" in ops:
        emails.append(ops)

    factory = get_session_factory()
    if factory is not None:
        with factory() as session:
            rows = session.scalars(
                select(AdminUser)
                .where(AdminUser.is_active.is_(True))
                .where(AdminUser.role == "admin")
            ).all()
            for user in rows:
                notify = (user.notify_email or "").strip().lower()
                if notify and "@" in notify and notify not in emails:
                    emails.append(notify)
    return emails


def build_monthly_summary_html(*, days: int = 30) -> str:
    finance = build_finance_snapshot(days=days)
    alerts = notifications_for_role("admin")
    revenue = finance.get("revenue_cents", 0) / 100
    margin = finance.get("margin_cents", 0) / 100
    lines = [
        "<h2>NoorLink monthly summary</h2>",
        f"<p>Period: last {days} days</p>",
        "<ul>",
        f"<li>Revenue: <strong>${revenue:,.2f}</strong></li>",
        f"<li>Est. margin: <strong>${margin:,.2f}</strong> ({finance.get('margin_pct', 0)}%)</li>",
        f"<li>Orders: {finance.get('order_count', 0)}</li>",
        f"<li>Refunded: {finance.get('refunded_count', 0)}</li>",
        f"<li>Pending fulfillment: {finance.get('pending_fulfillment', 0)}</li>",
        f"<li>Affiliate liability: ${finance.get('affiliate_liability_cents', 0) / 100:,.2f}</li>",
        "</ul>",
    ]
    if alerts:
        lines.append("<h3>Needs attention</h3><ul>")
        for item in alerts[:8]:
            lines.append(f"<li>{item.title}: {item.count}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>All clear — no open admin alerts.</p>")
    lines.append("<p>View dashboard: <a href=\"https://api.noorlink.co/admin\">NoorLink Admin</a></p>")
    return "\n".join(lines)


def send_monthly_summary_email(*, days: int = 30) -> Dict[str, Any]:
    recipients = _recipient_emails()
    if not recipients:
        return {"sent": 0, "error": "No admin report recipients configured."}

    html = build_monthly_summary_html(days=days)
    sent = 0
    errors: List[str] = []
    for email in recipients:
        try:
            send_email(
                to_email=email,
                subject="NoorLink monthly business summary",
                html_body=html,
            )
            sent += 1
        except EmailDeliveryError as exc:
            errors.append(f"{email}: {exc}")

    return {"sent": sent, "recipients": recipients, "errors": errors}
