"""Customer-facing order fields: data remaining, days left, fulfillment pending."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from app.api.schemas import Order


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _validity_days_from_row(row: Dict[str, Any]) -> Optional[int]:
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    for key in ("validity_days", "duration_days"):
        raw = metadata.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass

    plan = metadata.get("fulfillment_plan")
    if isinstance(plan, dict) and plan.get("validity_days") is not None:
        try:
            return int(plan["validity_days"])
        except (TypeError, ValueError):
            pass

    return None


def _start_at_from_row(row: Dict[str, Any]) -> datetime:
    for key in ("fulfilled_at", "paid_at", "created_at"):
        parsed = _parse_dt(row.get(key))
        if parsed:
            return parsed
    return datetime.now(timezone.utc)


def compute_days_remaining(
    *,
    validity_days: Optional[int],
    start_at: datetime,
    valid_until: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> Optional[int]:
    now = now or datetime.now(timezone.utc)
    if valid_until is not None:
        if now >= valid_until:
            return 0
        return max(0, (valid_until.date() - now.date()).days)

    if validity_days is None:
        return None

    end = start_at + timedelta(days=int(validity_days))
    delta = end - now
    if delta.total_seconds() <= 0:
        return 0
    # Calendar-day countdown (customer-friendly: "15 days left" on purchase day)
    return max(0, (end.date() - now.date()).days)


def compute_data_remaining_gb(
    *,
    data_total_gb: Optional[float] = None,
    data_used_gb: Optional[float] = None,
    allowance_mb: Optional[int] = None,
    used_mb: Optional[int] = None,
) -> Optional[float]:
    if allowance_mb is not None:
        used = int(used_mb or 0)
        remaining_mb = max(0, int(allowance_mb) - used)
        return round(remaining_mb / 1024.0, 2)

    if data_total_gb is None:
        return None
    used = float(data_used_gb or 0)
    return round(max(0.0, float(data_total_gb) - used), 2)


def fulfillment_pending(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or "")
    has_qr = bool(row.get("qr_code_url") or row.get("activation_code") or row.get("lpa_string"))
    if status in {"refunded", "failed", "cancelled"}:
        return False
    if status == "paid" and not has_qr:
        return True
    metadata = row.get("metadata") or {}
    if isinstance(metadata, dict):
        fulfillment = metadata.get("fulfillment") or {}
        if isinstance(fulfillment, dict) and fulfillment.get("error") and not has_qr:
            return True
    return False


def gift_fields_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        return {"is_gift": False}
    gift = metadata.get("gift")
    if not isinstance(gift, dict) or not gift.get("is_gift"):
        return {"is_gift": False}
    return {
        "is_gift": True,
        "gift_recipient_name": gift.get("recipient_name"),
        "gift_recipient_email": gift.get("recipient_email"),
    }


def enrich_order_row(
    row: Dict[str, Any],
    *,
    allowance_row: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Order]:
    from app.api.supabase_repository import _row_to_order

    validity_days = _validity_days_from_row(row)
    start_at = _start_at_from_row(row)

    valid_until = None
    allowance_mb = None
    used_mb = None
    allowance_status = None

    if allowance_row:
        valid_until = _parse_dt(allowance_row.get("valid_until"))
        allowance_mb = allowance_row.get("allowance_mb")
        used_mb = allowance_row.get("used_mb")
        allowance_status = allowance_row.get("status")
        try:
            validity_days = validity_days or (
                int((allowance_row.get("metadata") or {}).get("validity_days"))
                if isinstance(allowance_row.get("metadata"), dict)
                and (allowance_row.get("metadata") or {}).get("validity_days")
                else None
            )
        except (TypeError, ValueError):
            pass

    data_total_gb = (
        float(row["data_total_gb"]) if row.get("data_total_gb") is not None else None
    )
    data_used_gb = (
        float(row["data_used_gb"]) if row.get("data_used_gb") is not None else None
    )

    if allowance_mb is not None and data_total_gb is None:
        data_total_gb = round(int(allowance_mb) / 1024.0, 2)
    if used_mb is not None:
        data_used_gb = round(int(used_mb) / 1024.0, 2)

    days_remaining = compute_days_remaining(
        validity_days=validity_days,
        start_at=start_at,
        valid_until=valid_until,
    )
    data_remaining_gb = compute_data_remaining_gb(
        data_total_gb=data_total_gb,
        data_used_gb=data_used_gb,
        allowance_mb=int(allowance_mb) if allowance_mb is not None else None,
        used_mb=int(used_mb) if used_mb is not None else None,
    )

    base = _row_to_order(row)
    gift_fields = gift_fields_from_row(row)
    usage_fields = _usage_fields_from_row(
        row,
        {
            "days_remaining": days_remaining,
            "data_remaining_gb": data_remaining_gb,
            "data_used_gb": data_used_gb,
            "data_total_gb": data_total_gb,
        },
    )
    order = base.model_copy(
        update={
            "validity_days": validity_days,
            "days_remaining": days_remaining,
            "data_remaining_gb": data_remaining_gb,
            "fulfillment_pending": fulfillment_pending(row),
            "allowance_status": allowance_status,
            **gift_fields,
            **usage_fields,
        }
    )
    extras = {
        "validity_days": validity_days,
        "days_remaining": days_remaining,
        "data_remaining_gb": data_remaining_gb,
        "fulfillment_pending": fulfillment_pending(row),
        "allowance_status": allowance_status,
        **gift_fields,
        **usage_fields,
    }
    return extras, order


def _usage_fields_from_row(row: Dict[str, Any], extras: Dict[str, Any]) -> Dict[str, Any]:
    meta = row.get("metadata") or {}
    if not isinstance(meta, dict):
        return {}
    snapshot = meta.get("usage_snapshot")
    if not isinstance(snapshot, dict):
        from app.services.esim_topup import topup_capabilities

        caps = topup_capabilities(row)
        return {
            "topup_supported": bool(caps.get("supported")),
            "topup_reason": caps.get("reason"),
        }

    days_remaining = snapshot.get("days_remaining", extras.get("days_remaining"))
    data_remaining_gb = snapshot.get("data_remaining_gb", extras.get("data_remaining_gb"))
    data_used_gb = snapshot.get("data_used_gb")
    data_total_gb = snapshot.get("data_total_gb")

    return {
        "activation_status": snapshot.get("activation_status"),
        "activated_at": snapshot.get("activated_at"),
        "usage_synced_at": snapshot.get("synced_at"),
        "usage_pct": snapshot.get("usage_pct"),
        "days_remaining": days_remaining,
        "data_remaining_gb": data_remaining_gb,
        "data_used_gb": data_used_gb if data_used_gb is not None else extras.get("data_used_gb"),
        "data_total_gb": data_total_gb if data_total_gb is not None else extras.get("data_total_gb"),
        "topup_supported": bool(snapshot.get("topup_supported")),
        "wallet_balance_usd": snapshot.get("wallet_balance_usd"),
    }
