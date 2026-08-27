"""
eSIM reminders: low data (70%), expiring soon, expired → top-up / repurchase CTA.

Uses order data usage + metadata.validity_days (and breakage_allowances when present).
Reminders are tracked in orders.metadata.reminders so we never spam.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.email_service import (
    EmailDeliveryError,
    send_esim_expired_email,
    send_esim_expiring_soon_email,
    send_esim_low_data_email,
)
from app.services.order_customer_view import enrich_order_row

logger = logging.getLogger(__name__)

CANDIDATE_LOOKBACK_DAYS = 90
EXPIRED_NOTIFY_WINDOW_DAYS = 3
EXPIRING_SOON_DAYS = 1
LOW_DATA_USAGE_PCT = 70.0


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


def _usage_stats(
    row: Dict[str, Any],
    extras: Dict[str, Any],
    allowance: Optional[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (used_gb, total_gb, usage_pct) or Nones if unknown."""
    total: Optional[float] = None
    used: Optional[float] = None

    if allowance and allowance.get("allowance_mb") is not None:
        try:
            total = float(allowance["allowance_mb"]) / 1024.0
            used = float(allowance.get("used_mb") or 0) / 1024.0
        except (TypeError, ValueError):
            total = None
            used = None

    if total is None and row.get("data_total_gb") is not None:
        try:
            total = float(row["data_total_gb"])
        except (TypeError, ValueError):
            total = None
    if used is None and row.get("data_used_gb") is not None:
        try:
            used = float(row["data_used_gb"])
        except (TypeError, ValueError):
            used = None

    if used is None and extras.get("data_remaining_gb") is not None and total is not None:
        try:
            used = max(0.0, float(total) - float(extras["data_remaining_gb"]))
        except (TypeError, ValueError):
            used = None

    if total is None or total <= 0 or used is None:
        return used, total, None

    pct = min(100.0, max(0.0, (float(used) / float(total)) * 100.0))
    return round(used, 2), round(total, 2), round(pct, 1)


def process_esim_expiry_reminders(*, limit: int = 100) -> Dict[str, Any]:
    """
    Cron entry: low-data, expiring-soon, and expired reminder emails.
    Returns counts for CronRunResponse.
    """
    settings = get_settings()
    app_url = settings.app_url.rstrip("/")
    now = _utc_now()
    since = (now - timedelta(days=CANDIDATE_LOOKBACK_DAYS)).isoformat()

    try:
        rows = db.list_orders_for_expiry_reminders(since_iso=since, limit=limit)
    except db.SupabaseRepositoryError as exc:
        logger.exception("Failed to list orders for eSIM reminders")
        return {
            "success": False,
            "error": str(exc),
            "low_data_sent": 0,
            "expiring_soon_sent": 0,
            "expired_sent": 0,
            "skipped": 0,
            "examined": 0,
        }

    low_data_sent = 0
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
        used_gb, total_gb, usage_pct = _usage_stats(row, extras, allowance)

        country = str(row.get("country") or "your destination")
        package_name = str(row.get("package_name") or "Travel eSIM")
        flag = row.get("flag_emoji")
        plans_url = _country_plans_url(app_url, country)
        dashboard_url = (
            f"{app_url}/dashboard?email={quote(email)}"
            f"&orderId={quote(order_number)}"
        )
        acted = False

        # —— Low data (70% used), while plan is still within validity ——
        still_valid = days_remaining is None or int(days_remaining) > 0
        if (
            still_valid
            and usage_pct is not None
            and usage_pct >= LOW_DATA_USAGE_PCT
            and not reminders.get("low_data_70_sent_at")
            and not reminders.get("expiry_sent_at")
        ):
            try:
                send_esim_low_data_email(
                    to_email=email,
                    order_number=order_number,
                    country=country,
                    package_name=package_name,
                    flag_emoji=flag if isinstance(flag, str) else None,
                    usage_pct=float(usage_pct),
                    used_gb=used_gb,
                    total_gb=total_gb,
                    plans_url=plans_url,
                    dashboard_url=dashboard_url,
                    app_url=app_url,
                )
                reminders = {
                    **reminders,
                    "low_data_70_sent_at": now.isoformat(),
                }
                db.merge_order_metadata(
                    order_number,
                    {"reminders": reminders},
                )
                low_data_sent += 1
                acted = True
            except EmailDeliveryError as exc:
                logger.error("Low-data reminder failed for %s: %s", order_number, exc)
                errors.append(f"{order_number}: {exc}")
                continue

        # —— Expired ——
        if (
            days_remaining is not None
            and validity_days is not None
            and int(days_remaining) <= 0
            and not reminders.get("expiry_sent_at")
        ):
            valid_until = None
            if allowance:
                valid_until = _parse_dt(allowance.get("valid_until"))
            if valid_until is None:
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
                if not acted:
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
                acted = True
            except EmailDeliveryError as exc:
                logger.error("Expired reminder failed for %s: %s", order_number, exc)
                errors.append(f"{order_number}: {exc}")
            continue

        # —— Expiring soon (1 day left) ——
        if (
            days_remaining is not None
            and int(days_remaining) == EXPIRING_SOON_DAYS
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
                acted = True
            except EmailDeliveryError as exc:
                logger.error(
                    "Expiring-soon reminder failed for %s: %s", order_number, exc
                )
                errors.append(f"{order_number}: {exc}")
            continue

        if not acted:
            skipped += 1

    return {
        "success": len(errors) == 0,
        "low_data_sent": low_data_sent,
        "expiring_soon_sent": expiring_soon_sent,
        "expired_sent": expired_sent,
        "skipped": skipped,
        "examined": len(rows),
        "errors": errors[:10],
    }
