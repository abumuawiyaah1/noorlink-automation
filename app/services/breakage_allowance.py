"""
Breakage allowance ledger — virtual bundle enforcement on WeConnect PAYG.

Creates and updates rows in breakage_allowances after checkout/provision.
Usage sync + suspend hooks are stubs until WeConnect sandbox is wired.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.services.breakage_strategy import (
    build_allowance,
    fulfillment_mode_for_order,
    is_breakage_eligible,
)

logger = logging.getLogger(__name__)

ALLOWANCE_SYNC_GRACE_MB = 64  # suspend slightly before hard cap if provider lags


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def should_create_allowance(
    *,
    country: str,
    data_gb: Optional[float],
    validity_days: Optional[int],
    wants_topup: bool = False,
) -> bool:
    mode = fulfillment_mode_for_order(
        country=country,
        data_gb=data_gb,
        validity_days=validity_days,
        wants_topup=wants_topup,
    )
    return mode.get("mode") == "virtual_bundle" and bool(data_gb) and bool(validity_days)


def allowance_valid_until(*, validity_days: int, from_dt: Optional[datetime] = None) -> datetime:
    start = from_dt or _utc_now()
    return start + timedelta(days=int(validity_days))


def prepare_allowance_record(
    *,
    order_id: str,
    order_number: str,
    country: str,
    data_gb: float,
    validity_days: int,
    retail_usd: float,
    plan_key: str = "traveler",
    provider_profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    valid_until = allowance_valid_until(validity_days=validity_days)
    virtual = build_allowance(
        order_id=order_id,
        country=country,
        data_gb=data_gb,
        validity_days=validity_days,
        retail_usd=retail_usd,
        plan_key=plan_key,
        valid_until_iso=valid_until.isoformat(),
    )
    return {
        "order_id": order_id,
        "order_number": order_number,
        "country_slug": virtual.country_slug,
        "plan_key": virtual.plan_key,
        "fulfillment_mode": "virtual_bundle",
        "provider": "weconnect",
        "provider_profile_id": provider_profile_id,
        "allowance_mb": virtual.allowance_mb,
        "used_mb": 0,
        "wholesale_cost_usd": 0,
        "retail_usd": float(retail_usd),
        "valid_from": _utc_now().isoformat(),
        "valid_until": valid_until.isoformat(),
        "status": "pending" if not provider_profile_id else "active",
        "metadata": {
            "breakage_eligible": is_breakage_eligible(country),
            "validity_days": int(validity_days),
            "data_gb": float(data_gb),
        },
    }


def evaluate_allowance_status(row: Dict[str, Any], *, now: Optional[datetime] = None) -> str:
    """Return the status the allowance should have based on usage and time."""
    current = str(row.get("status") or "pending")
    if current in {"cancelled", "suspended", "exhausted", "expired"}:
        return current

    now = now or _utc_now()
    valid_until_raw = row.get("valid_until")
    valid_until: Optional[datetime] = None
    if valid_until_raw:
        if isinstance(valid_until_raw, datetime):
            valid_until = valid_until_raw if valid_until_raw.tzinfo else valid_until_raw.replace(tzinfo=timezone.utc)
        else:
            valid_until = datetime.fromisoformat(str(valid_until_raw).replace("Z", "+00:00"))

    used_mb = int(row.get("used_mb") or 0)
    allowance_mb = int(row.get("allowance_mb") or 0)

    if valid_until and now >= valid_until:
        return "expired"
    if allowance_mb > 0 and used_mb >= max(0, allowance_mb - ALLOWANCE_SYNC_GRACE_MB):
        return "exhausted"
    if current == "pending":
        return "pending"
    return "active"


def remaining_mb(row: Dict[str, Any]) -> int:
    allowance_mb = int(row.get("allowance_mb") or 0)
    used_mb = int(row.get("used_mb") or 0)
    return max(0, allowance_mb - used_mb)


def breakage_profit_estimate(row: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate breakage upside: retail minus wholesale so far (not future usage)."""
    retail = float(row.get("retail_usd") or 0)
    wholesale = float(row.get("wholesale_cost_usd") or 0)
    allowance_mb = int(row.get("allowance_mb") or 0)
    used_mb = int(row.get("used_mb") or 0)
    unused_mb = max(0, allowance_mb - used_mb)
    status = str(row.get("status") or "")
    return {
        "retail_usd": retail,
        "wholesale_cost_usd": wholesale,
        "margin_usd_so_far": round(retail - wholesale, 2),
        "allowance_mb": allowance_mb,
        "used_mb": used_mb,
        "unused_mb": unused_mb,
        "status": status,
        "is_breakage_event": status == "expired" and unused_mb > 0,
    }


async def sync_allowance_from_provider(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull usage from provider profile linked on the allowance row.
    """
    order_number = str(row.get("order_number") or "")
    profile_id = str(row.get("provider_profile_id") or "").strip()
    if not order_number:
        return {"ok": False, "message": "Missing order_number on allowance."}

    order_row = None
    try:
        from app.api import supabase_repository as db

        order_row = db.get_order_row_by_order_number(order_number)
    except Exception as exc:
        return {"ok": False, "message": str(exc)[:200]}

    if not order_row:
        return {"ok": False, "message": f"Order {order_number} not found."}

    if profile_id and not order_row.get("iccid"):
        order_row = {**order_row, "iccid": profile_id}

    try:
        from app.services.esim_usage_sync import sync_order_usage_blocking

        sync_order_usage_blocking(order_row, source="allowance_sync")
        return {"ok": True, "order_number": order_number}
    except Exception as exc:
        logger.warning("Allowance sync failed for %s: %s", order_number, exc)
        return {"ok": False, "message": str(exc)[:200], "order_number": order_number}
