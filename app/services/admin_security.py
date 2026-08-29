"""Security overview for admin Operations panel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select

from app.core.config import get_settings
from app.db.engine import get_engine, get_session_factory
from app.db.models import AdminAuditLog, AdminUser
from app.services.security_threats import security_threats_summary


def _configured(value: str) -> bool:
    return bool((value or "").strip())


def build_security_overview(*, client_ip: str | None = None) -> Dict[str, Any]:
    settings = get_settings()
    from_email = (settings.resend_from_email or "").strip()
    domain_ok = "@noorlink.co" in from_email.lower()

    checklist: List[Dict[str, Any]] = [
        {
            "label": "Admin dashboard enabled",
            "ok": settings.admin_enabled,
            "hint": "Set ADMIN_ENABLED=true in production.",
        },
        {
            "label": "Database URL (SQLAdmin)",
            "ok": _configured(settings.database_url),
            "hint": "Set DATABASE_URL to Supabase pooler URI.",
        },
        {
            "label": "Session secret key changed",
            "ok": settings.secret_key != "change-this-in-production",
            "hint": "Set SECRET_KEY to a long random value.",
        },
        {
            "label": "Cron secret configured",
            "ok": _configured(settings.cron_secret),
            "hint": "Set CRON_SECRET for scheduled jobs.",
        },
        {
            "label": "Stripe webhook secret",
            "ok": _configured(settings.stripe_webhook_secret),
            "hint": "Required for automatic fulfillment after payment.",
        },
        {
            "label": "Resend API key",
            "ok": _configured(settings.resend_api_key),
            "hint": "Required for customer and Insider email.",
        },
        {
            "label": "Email from @noorlink.co",
            "ok": domain_ok,
            "hint": "RESEND_FROM_EMAIL should use noorlink.co domain.",
        },
        {
            "label": "Resend delivery webhooks",
            "ok": _configured(settings.resend_events_webhook_secret)
            or _configured(settings.resend_inbound_webhook_secret),
            "hint": "Set RESEND_EVENTS_WEBHOOK_SECRET and point Resend to /api/v1/webhooks/resend/events.",
        },
        {
            "label": "Admin IP allowlist",
            "ok": not settings.admin_allowed_ip_list or len(settings.admin_allowed_ip_list) >= 1,
            "hint": "Set ADMIN_ALLOWED_IPS and/or Cloudflare Access on /admin for production.",
        },
        {
            "label": "Ops alert email or Slack",
            "ok": _configured(settings.ops_alert_email) or _configured(settings.slack_webhook_url),
            "hint": "Set OPS_ALERT_EMAIL or SLACK_WEBHOOK_URL for fulfillment failures.",
        },
        {
            "label": "Environment",
            "ok": True,
            "hint": f"Current: {settings.environment}",
        },
    ]

    recent_audit: List[Dict[str, Any]] = []
    staff_users: List[Dict[str, Any]] = []
    factory = get_session_factory()
    if factory is not None:
        with factory() as session:
            logs = session.scalars(
                select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(15)
            ).all()
            for entry in logs:
                recent_audit.append(
                    {
                        "at": entry.created_at.isoformat() if entry.created_at else "",
                        "user": entry.admin_username,
                        "action": entry.action,
                        "table": entry.table_name,
                        "record": entry.record_id,
                        "ip": entry.ip_address,
                    }
                )
            users = session.scalars(
                select(AdminUser).where(AdminUser.is_active.is_(True)).order_by(AdminUser.username)
            ).all()
            for user in users:
                staff_users.append(
                    {
                        "username": user.username,
                        "display_name": user.display_name or user.username,
                        "role": user.role,
                        "last_login": user.last_login_at.isoformat() if user.last_login_at else "Never",
                        "notify_email": user.notify_email,
                    }
                )

    return {
        "checklist": checklist,
        "checklist_ok": all(item["ok"] for item in checklist),
        "recent_audit": recent_audit,
        "staff_users": staff_users,
        "threats": security_threats_summary(hours=24),
        "db_engine_ok": get_engine() is not None,
        "environment": settings.environment,
        "client_ip": client_ip,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
