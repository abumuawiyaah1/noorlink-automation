"""
Post-purchase install emails:

1) Install-help nudge — after N hours if not yet installed.
2) Install congrats — when install is detected, with landing connect steps.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.email_service import (
    EmailDeliveryError,
    send_esim_install_congrats_email,
    send_esim_install_help_email,
)

logger = logging.getLogger(__name__)

INSTALLED_STATUSES = frozenset({"installed", "activated", "active"})
SKIP_ORDER_STATUSES = frozenset(
    {"pending", "failed", "refunded", "cancelled", "canceled", "expired", "suspended"}
)
HELP_REMINDER_KEY = "install_help_sent_at"
CONGRATS_REMINDER_KEY = "install_congrats_sent_at"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _reminders(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    raw = metadata.get("reminders")
    return dict(raw) if isinstance(raw, dict) else {}


def _usage_snapshot(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    raw = metadata.get("usage_snapshot")
    return dict(raw) if isinstance(raw, dict) else {}


def order_looks_installed(row: Dict[str, Any]) -> bool:
    """True when provider sync / order status says the profile is on the device."""
    status = str(row.get("status") or "").strip().lower()
    if status == "active":
        return True

    snapshot = _usage_snapshot(row.get("metadata"))
    if snapshot.get("activated") is True:
        return True
    activation = str(snapshot.get("activation_status") or "").strip().lower()
    if activation in INSTALLED_STATUSES:
        return True

    fulfillment = (row.get("metadata") or {}).get("fulfillment") if isinstance(row.get("metadata"), dict) else {}
    if isinstance(fulfillment, dict) and fulfillment.get("activated_at"):
        return True

    return False


def order_eligible_for_install_help(
    row: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    wait_hours: int = 24,
) -> bool:
    """Qualify a delivered order for the one-time install-help email."""
    now = now or _utc_now()
    status = str(row.get("status") or "").strip().lower()
    if status in SKIP_ORDER_STATUSES:
        return False
    if status not in {"delivered", "paid", "active"}:
        return False
    if order_looks_installed(row):
        return False

    reminders = _reminders(row.get("metadata"))
    if reminders.get(HELP_REMINDER_KEY):
        return False

    has_install = bool(
        (row.get("qr_code_url") or "").strip()
        or (row.get("lpa_string") or "").strip()
        or (row.get("activation_code") or "").strip()
    )
    if not has_install:
        return False

    fulfilled = _parse_dt(row.get("fulfilled_at")) or _parse_dt(row.get("paid_at"))
    if fulfilled is None:
        return False
    if fulfilled > now - timedelta(hours=max(1, int(wait_hours))):
        return False

    return True


def order_eligible_for_install_congrats(row: Dict[str, Any]) -> bool:
    """Qualify an installed order for the one-time landing-prep congrats email."""
    status = str(row.get("status") or "").strip().lower()
    if status in SKIP_ORDER_STATUSES:
        return False
    if not order_looks_installed(row):
        return False

    reminders = _reminders(row.get("metadata"))
    if reminders.get(CONGRATS_REMINDER_KEY):
        return False

    email = str(row.get("email") or "").strip()
    return bool(email)


def maybe_send_install_congrats(order_number: str) -> bool:
    """
    Send congrats + landing steps if this order newly looks installed.
    Safe to call from usage sync / webhooks; idempotent via reminders stamp.
    """
    normalized = (order_number or "").strip().upper()
    if not normalized:
        return False
    try:
        row = db.get_order_row_by_order_number(normalized)
    except db.SupabaseRepositoryError as exc:
        logger.warning("Install congrats lookup failed for %s: %s", normalized, exc)
        return False
    if not row or not order_eligible_for_install_congrats(row):
        return False

    settings = get_settings()
    app_url = settings.app_url.rstrip("/")
    email = str(row.get("email") or "").strip()
    dashboard_url = f"{app_url}/dashboard?orderId={quote(normalized)}"
    now = _utc_now()

    try:
        send_esim_install_congrats_email(
            to_email=email,
            order_number=normalized,
            country=str(row.get("country") or "your destination"),
            package_name=str(row.get("package_name") or "eSIM plan"),
            flag_emoji=row.get("flag_emoji"),
            dashboard_url=dashboard_url,
            app_url=app_url,
        )
        db.merge_order_metadata(
            normalized,
            {"reminders": {CONGRATS_REMINDER_KEY: now.isoformat()}},
        )
        return True
    except (EmailDeliveryError, db.SupabaseRepositoryError) as exc:
        logger.warning("Install congrats email failed for %s: %s", normalized, exc)
        return False
    except Exception:
        logger.exception("Unexpected install congrats failure for %s", normalized)
        return False


def process_install_reminders(*, limit: int = 100) -> Dict[str, Any]:
    """Cron entry: one install-help nudge per order after wait_hours."""
    settings = get_settings()
    app_url = settings.app_url.rstrip("/")
    wait_hours = max(1, int(settings.install_reminder_hours or 24))
    lookback_days = max(1, int(settings.install_reminder_lookback_days or 14))
    now = _utc_now()
    since = (now - timedelta(days=lookback_days)).isoformat()

    try:
        rows = db.list_orders_for_install_reminders(since_iso=since, limit=limit)
    except db.SupabaseRepositoryError as exc:
        logger.exception("Failed to list orders for install reminders")
        return {
            "success": False,
            "error": str(exc)[:240],
            "checked": 0,
            "sent": 0,
            "skipped": 0,
        }

    sent = 0
    skipped = 0
    errors = 0

    for row in rows:
        order_number = str(row.get("order_number") or "").strip()
        email = str(row.get("email") or "").strip()
        if not order_number or not email:
            skipped += 1
            continue

        if not order_eligible_for_install_help(row, now=now, wait_hours=wait_hours):
            skipped += 1
            continue

        dashboard_url = f"{app_url}/dashboard?orderId={quote(order_number)}"
        support_url = (
            f"{app_url}/support?subject={quote('Install / QR code')}"
            f"&email={quote(email)}&orderId={quote(order_number)}"
        )

        try:
            send_esim_install_help_email(
                to_email=email,
                order_number=order_number,
                country=str(row.get("country") or "your destination"),
                package_name=str(row.get("package_name") or "eSIM plan"),
                flag_emoji=row.get("flag_emoji"),
                dashboard_url=dashboard_url,
                support_url=support_url,
                app_url=app_url,
            )
            db.merge_order_metadata(
                order_number,
                {"reminders": {HELP_REMINDER_KEY: now.isoformat()}},
            )
            sent += 1
        except (EmailDeliveryError, db.SupabaseRepositoryError) as exc:
            errors += 1
            logger.warning("Install help email failed for %s: %s", order_number, exc)
        except Exception as exc:
            errors += 1
            logger.exception("Unexpected install help failure for %s: %s", order_number, exc)

    return {
        "success": errors == 0,
        "checked": len(rows),
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "wait_hours": wait_hours,
        "lookback_days": lookback_days,
    }


def process_install_congrats(*, limit: int = 100) -> Dict[str, Any]:
    """Cron entry: congratulate newly installed eSIMs with landing connect steps."""
    settings = get_settings()
    lookback_days = max(1, int(settings.install_reminder_lookback_days or 14))
    since = (_utc_now() - timedelta(days=lookback_days)).isoformat()

    try:
        rows = db.list_orders_for_install_reminders(since_iso=since, limit=limit)
    except db.SupabaseRepositoryError as exc:
        logger.exception("Failed to list orders for install congrats")
        return {
            "success": False,
            "error": str(exc)[:240],
            "checked": 0,
            "sent": 0,
            "skipped": 0,
        }

    sent = 0
    skipped = 0
    for row in rows:
        order_number = str(row.get("order_number") or "").strip()
        if not order_number:
            skipped += 1
            continue
        if maybe_send_install_congrats(order_number):
            sent += 1
        else:
            skipped += 1

    return {
        "success": True,
        "checked": len(rows),
        "sent": sent,
        "skipped": skipped,
        "lookback_days": lookback_days,
    }
