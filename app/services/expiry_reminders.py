"""
eSIM validity reminders: expiring soon + expired → repurchase / add-data CTA.

Uses order metadata.validity_days (and breakage_allowances.valid_until when present).
Reminders are tracked in orders.metadata.reminders so we never spam.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.email_service import (
    EmailDeliveryError,
    send_esim_expired_email,
    send_esim_expiring_soon_email,
)
from app.services.order_customer_view import (
    enrich_order_row,
)

logger = logging.getLogger(__name__)

# Look back this far for delivered orders that may have expired
CANDIDATE_LOOKBACK_DAYS = 90
# Only send "expired" email within this window after expiry (avoid old orders)
EXPIRED_NOTIFY_WINDOW_DAYS = 3
# "Expiring soon" when this many calendar days remain
EXPIRING_SOON_DAYS = 1


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


def _country_plans_url(app_url: str, country: str) -> str:
    base = app_url.rstrip("/")
    slug = (country or "").strip().lower().replace(" ", "-")
    if not slug or slug in {"your-destination", "unknown"}:
        return f"{base}/destinations"
    if slug.startswith("regional-"):
        return f"{base}/plans/regional/{quote(slug.replace('regional-', '', 1))}"
    return f"{base}/plans/{quote(slug)}"


def process_esim_expiry_reminders(*, limit: int = 100) -> Dict[str, Any]:
    """
    Cron entry: send expiring-soon and expired emails for qualifying orders.
    Returns counts for CronRunResponse.
    """
    settings = get_settings()
    app_url = settings.app_url.rstrip("/")
    now = _utc_now()
    since = (now - timedelta(days=CANDIDATE_LOOKBACK_DAYS)).isoformat()

    try:
        rows = db.list_orders_for_expiry_reminders(since_iso=since, limit=limit)
    except db.SupabaseRepositoryError as exc:
        logger.exception("Failed to list orders for expiry reminders")
        return {
            "success": False,
            "error": str(exc),
            "expiring_soon_sent": 0,
            "expired_sent": 0,
            "skipped": 0,
            "examined": 0,
        }

    expiring_soon_sent = 0
    expired_sent = 0
    skipped = 0
    errors: List[str] = []

    for row in rows:
        order_number = str(row.get("order_number") or "")
        email = str(row.get("email") or "").strip()
        if not order_number or not email:
            skipped += 1
            continue

        status = str(row.get("status") or "")
        if status in {"refunded", "failed", "pending"}:
            skipped += 1
            continue

        reminders = _reminders(row.get("metadata"))
        allowance = None
        try:
            if row.get("id"):
                allowance = db.get_breakage_allowance_by_order_id(str(row["id"]))
        except db.SupabaseRepositoryError:
            allowance = None

        extras, _order = enrich_order_row(row, allowance_row=allowance)
        days_remaining = extras.get("days_remaining")
        validity_days = extras.get("validity_days")

        if days_remaining is None or validity_days is None:
            skipped += 1
            continue

        country = str(row.get("country") or "your destination")
        package_name = str(row.get("package_name") or "Travel eSIM")
        flag = row.get("flag_emoji")
        plans_url = _country_plans_url(app_url, country)
        dashboard_url = (
            f"{app_url}/dashboard?email={quote(email)}"
            f"&orderId={quote(order_number)}"
        )

        # —— Expired ——
        if days_remaining <= 0 and not reminders.get("expiry_sent_at"):
            # Avoid emailing ancient expiries if we never tracked them
            valid_until = None
            if allowance:
                valid_until = _parse_dt(allowance.get("valid_until"))
            if valid_until is None:
                # Approximate end from start + validity
                start = (
                    _parse_dt(row.get("fulfilled_at"))
                    or _parse_dt(row.get("paid_at"))
                    or _parse_dt(row.get("created_at"))
                )
                if start and validity_days:
                    valid_until = start + timedelta(days=int(validity_days))

            if valid_until and (now - valid_until) > timedelta(
                days=EXPIRED_NOTIFY_WINDOW_DAYS
            ):
                skipped += 1
                continue

            try:
                send_esim_expired_email(
                    to_email=email,
                    order_number=order_number,
                    country=country,
                    package_name=package_name,
                    flag_emoji=flag if isinstance(flag, str) else None,
                    plans_url=plans_url,
                    dashboard_url=dashboard_url,
                    app_url=app_url,
                )
                db.merge_order_metadata(
                    order_number,
                    {
                        "reminders": {
                            **reminders,
                            "expiry_sent_at": now.isoformat(),
                        }
                    },
                )
                if allowance and str(allowance.get("status")) not in {
                    "expired",
                    "cancelled",
                }:
                    try:
                        db.update_breakage_allowance(
                            str(allowance["id"]),
                            {"status": "expired"},
                        )
                    except db.SupabaseRepositoryError:
                        pass
                expired_sent += 1
            except EmailDeliveryError as exc:
                logger.error("Expired reminder failed for %s: %s", order_number, exc)
                errors.append(f"{order_number}: {exc}")
            continue

        # —— Expiring soon (1 day left) ——
        if (
            days_remaining == EXPIRING_SOON_DAYS
            and not reminders.get("expiring_soon_sent_at")
            and not reminders.get("expiry_sent_at")
        ):
            try:
                send_esim_expiring_soon_email(
                    to_email=email,
                    order_number=order_number,
                    country=country,
                    package_name=package_name,
                    flag_emoji=flag if isinstance(flag, str) else None,
                    days_remaining=int(days_remaining),
                    data_remaining_gb=extras.get("data_remaining_gb"),
                    plans_url=plans_url,
                    dashboard_url=dashboard_url,
                    app_url=app_url,
                )
                db.merge_order_metadata(
                    order_number,
                    {
                        "reminders": {
                            **reminders,
                            "expiring_soon_sent_at": now.isoformat(),
                        }
                    },
                )
                expiring_soon_sent += 1
            except EmailDeliveryError as exc:
                logger.error(
                    "Expiring-soon reminder failed for %s: %s", order_number, exc
                )
                errors.append(f"{order_number}: {exc}")
            continue

        skipped += 1

    return {
        "success": len(errors) == 0,
        "expiring_soon_sent": expiring_soon_sent,
        "expired_sent": expired_sent,
        "skipped": skipped,
        "examined": len(rows),
        "errors": errors[:10],
    }
