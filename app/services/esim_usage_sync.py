"""
Live eSIM usage / activation sync from upstream providers.

Normalizes provider responses into metadata.usage_snapshot on orders and
updates data_used_gb / status where we have reliable numbers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.api import supabase_repository as db
from app.services.order_customer_view import (
    compute_data_remaining_gb,
    compute_days_remaining,
    _parse_dt,
    _validity_days_from_row,
    _start_at_from_row,
)

logger = logging.getLogger(__name__)

ACTIVATION_STATES = frozenset(
    {
        "enabled",
        "installed",
        "installation",
        "in_use",
        "active",
        "activated",
        "using",
    }
)


class UsageSyncError(Exception):
    """Provider usage sync failed."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    meta = row.get("metadata") or {}
    return dict(meta) if isinstance(meta, dict) else {}


def resolve_order_provider(row: Dict[str, Any]) -> str:
    meta = _metadata_dict(row)
    fulfillment = meta.get("fulfillment") or {}
    if isinstance(fulfillment, dict):
        provider = str(fulfillment.get("provider") or "").strip().lower()
        if provider:
            return provider
    plan = meta.get("fulfillment_plan") or {}
    if isinstance(plan, dict):
        provider = str(plan.get("provider") or "").strip().lower()
        if provider:
            return provider
    return ""


def _first_float(*values: Any) -> Optional[float]:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _bytes_to_gb(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value) / (1024**3), 4)
    except (TypeError, ValueError):
        return None


def _mb_to_gb(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value) / 1024.0, 4)
    except (TypeError, ValueError):
        return None


def _activation_from_status(*statuses: Any) -> Tuple[str, bool]:
    parts = [str(s or "").strip().lower() for s in statuses if s]
    joined = " ".join(parts)
    if any(token in joined for token in ACTIVATION_STATES):
        if "enabled" in joined or "in_use" in joined or "using" in joined:
            return "active", True
        if "install" in joined:
            return "installed", True
        return "activated", True
    if any(token in joined for token in ("released", "got_resource", "allocated")):
        return "provisioned", False
    if any(token in joined for token in ("depleted", "used_up", "expired", "terminated")):
        return "expired", True
    return "unknown", False


def build_usage_snapshot(
    *,
    provider: str,
    source: str,
    row: Dict[str, Any],
    provider_payload: Optional[Dict[str, Any]] = None,
    allowance_row: Optional[Dict[str, Any]] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge provider fields + order row into a customer/admin-friendly snapshot."""
    meta = _metadata_dict(row)
    validity_days = _validity_days_from_row(row)
    start_at = _start_at_from_row(row)
    data_total_gb = _first_float(row.get("data_total_gb"))
    data_used_gb = _first_float(row.get("data_used_gb"), 0.0)

    activation_status = "unknown"
    activated = False
    activated_at = None
    valid_until = None
    esim_status = None
    wallet_balance_usd = None
    topup_supported = provider == "citrus"
    provider_notes: List[str] = []

    payload = provider_payload or {}
    fulfillment = meta.get("fulfillment") or {}
    if isinstance(fulfillment, dict):
        activated_at = fulfillment.get("activated_at")
        prev = meta.get("usage_snapshot") or {}
        if isinstance(prev, dict) and not activated_at:
            activated_at = prev.get("activated_at")

    if provider == "citrus":
        esim_status = str(payload.get("status") or payload.get("esim_status") or "")
        wallet_balance_usd = _first_float(
            payload.get("wallet_balance_usd"),
            payload.get("balance_usd"),
            (payload.get("wallet") or {}).get("balance_usd")
            if isinstance(payload.get("wallet"), dict)
            else None,
        )
        data_used_gb = _first_float(
            payload.get("data_used_gb"),
            _mb_to_gb(payload.get("data_used_mb")),
            _bytes_to_gb(payload.get("data_used_bytes")),
            data_used_gb,
        )
        if wallet_balance_usd is not None and data_total_gb is None:
            data_total_gb = wallet_balance_usd  # PAYG wallet as cap hint
        activation_status, activated = _activation_from_status(esim_status, payload.get("lifecycle"))
        topup_supported = True

    elif provider == "esimaccess":
        profile = payload
        if isinstance(payload.get("esimList"), list) and payload["esimList"]:
            profile = payload["esimList"][0]
        esim_status = str(profile.get("esimStatus") or profile.get("esim_status") or "")
        smdp_status = str(profile.get("smdpStatus") or profile.get("smdp_status") or "")
        activation_status, activated = _activation_from_status(esim_status, smdp_status)
        total_bytes = profile.get("totalVolume") or profile.get("total_volume")
        used_bytes = profile.get("orderUsage") or profile.get("order_usage")
        if total_bytes is not None:
            data_total_gb = _bytes_to_gb(total_bytes)
        if used_bytes is not None:
            data_used_gb = _bytes_to_gb(used_bytes)
        expired_raw = profile.get("expiredTime") or profile.get("expired_time")
        valid_until = _parse_dt(expired_raw)
        if profile.get("packageList"):
            provider_notes.append("package_list_present")
        topup_supported = bool(row.get("iccid"))

    elif provider == "telna":
        profile = payload
        esim_status = str(profile.get("state") or profile.get("status") or "")
        activation_status, activated = _activation_from_status(esim_status)
        packages = profile.get("packages") or profile.get("data_packages")
        if isinstance(packages, list) and packages:
            pkg = packages[0] if isinstance(packages[0], dict) else {}
            data_total_gb = _first_float(
                _mb_to_gb(pkg.get("initial_balance_mb")),
                _bytes_to_gb(pkg.get("initial_balance_bytes")),
                data_total_gb,
            )
            data_used_gb = _first_float(
                _mb_to_gb(pkg.get("spent_balance_mb")),
                _bytes_to_gb(pkg.get("spent_balance_bytes")),
                data_used_gb,
            )
            valid_until = _parse_dt(pkg.get("expiry_date") or pkg.get("valid_until"))

    elif provider == "simbase":
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else payload
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        esim_status = str(details.get("state") or usage.get("state") or "")
        activation_status, activated = _activation_from_status(esim_status)
        usage_bytes = usage.get("bytes") or usage.get("total_bytes") or usage.get("current_bytes")
        if usage_bytes is not None:
            data_used_gb = _bytes_to_gb(usage_bytes)
        limit_bytes = row.get("data_limit_bytes") or usage.get("limit_bytes")
        if limit_bytes is not None:
            data_total_gb = _bytes_to_gb(limit_bytes)

    elif provider in {"mock", "noorlink-mock"}:
        activation_status = "provisioned"
        topup_supported = False

    if allowance_row:
        allowance_mb = allowance_row.get("allowance_mb")
        used_mb = allowance_row.get("used_mb")
        if allowance_mb is not None:
            data_total_gb = round(int(allowance_mb) / 1024.0, 2)
        if used_mb is not None:
            data_used_gb = round(int(used_mb) / 1024.0, 2)
        valid_until = _parse_dt(allowance_row.get("valid_until")) or valid_until

    if overrides:
        activation_status = overrides.get("activation_status", activation_status)
        activated = bool(overrides.get("activated", activated))
        activated_at = overrides.get("activated_at", activated_at)
        if overrides.get("data_used_gb") is not None:
            data_used_gb = float(overrides["data_used_gb"])
        if overrides.get("data_total_gb") is not None:
            data_total_gb = float(overrides["data_total_gb"])
        if overrides.get("valid_until") is not None:
            valid_until = _parse_dt(overrides["valid_until"])

    if activated and not activated_at:
        activated_at = _utc_now_iso()

    days_remaining = compute_days_remaining(
        validity_days=validity_days,
        start_at=start_at,
        valid_until=valid_until,
    )
    data_remaining_gb = compute_data_remaining_gb(
        data_total_gb=data_total_gb,
        data_used_gb=data_used_gb,
    )

    usage_pct = None
    if data_total_gb and data_total_gb > 0 and data_used_gb is not None:
        usage_pct = min(100.0, round((data_used_gb / data_total_gb) * 100, 1))

    snapshot = {
        "synced_at": _utc_now_iso(),
        "source": source,
        "provider": provider or "unknown",
        "activation_status": activation_status,
        "activated": activated,
        "activated_at": activated_at,
        "esim_status": esim_status,
        "data_used_gb": data_used_gb,
        "data_total_gb": data_total_gb,
        "data_remaining_gb": data_remaining_gb,
        "usage_pct": usage_pct,
        "validity_days": validity_days,
        "days_remaining": days_remaining,
        "valid_until": valid_until.isoformat() if valid_until else None,
        "wallet_balance_usd": wallet_balance_usd,
        "topup_supported": topup_supported,
        "iccid": row.get("iccid"),
        "provider_notes": provider_notes,
    }
    return snapshot


async def _fetch_provider_payload(provider: str, row: Dict[str, Any]) -> Dict[str, Any]:
    iccid = str(row.get("iccid") or "").strip()
    meta = _metadata_dict(row)
    fulfillment = meta.get("fulfillment") or {}
    if not isinstance(fulfillment, dict):
        fulfillment = {}

    if provider == "citrus":
        if not iccid:
            raise UsageSyncError("Citrus sync requires ICCID on the order.")
        from app.services.citrus import CitrusClient

        async with CitrusClient() as client:
            payload = await client.get_esim(iccid)
            return payload if isinstance(payload, dict) else {"data": payload}

    if provider == "esimaccess":
        from app.services.esim_access import EsimAccessClient

        order_no = str(fulfillment.get("provider_order_id") or "").strip()
        async with EsimAccessClient() as client:
            profiles = await client.query_esims(order_no=order_no, iccid=iccid)
            if profiles:
                return {"esimList": profiles, **profiles[0]}
            return {"esimList": []}

    if provider == "telna":
        if not iccid:
            raise UsageSyncError("Telna sync requires ICCID on the order.")
        from app.services.telna import TelnaClient

        async with TelnaClient() as client:
            return await client.get_euicc_profile(iccid)

    if provider == "simbase":
        if not iccid:
            raise UsageSyncError("Simbase sync requires ICCID on the order.")
        from app.services.simbase import SimbaseClient

        async with SimbaseClient() as client:
            usage = await client.get_sim_usage(iccid)
            try:
                details = await client.get_sim_details(iccid)
            except Exception:
                details = {}
            return {"usage": usage, "details": details}

    if provider in {"mock", "noorlink-mock"}:
        return {"status": "mock"}

    raise UsageSyncError(f"Usage sync not supported for provider '{provider}'.")


def apply_usage_snapshot(
    order_number: str,
    snapshot: Dict[str, Any],
    *,
    merge_fulfillment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist snapshot to order row + optional column updates."""
    row = db.get_order_row_by_order_number(order_number)
    if not row:
        raise UsageSyncError(f"Order {order_number} not found.")

    updates: Dict[str, Any] = {}
    if snapshot.get("data_used_gb") is not None:
        updates["data_used_gb"] = snapshot["data_used_gb"]
    if snapshot.get("data_total_gb") is not None and row.get("data_total_gb") is None:
        updates["data_total_gb"] = snapshot["data_total_gb"]

    status = str(row.get("status") or "")
    if snapshot.get("activated") and status == "delivered":
        updates["status"] = "active"

    if updates:
        client = db.get_supabase_client()
        try:
            client.table("orders").update(updates).eq("order_number", order_number).execute()
        except Exception as exc:
            logger.exception("Failed column updates for usage sync %s", order_number)
            raise UsageSyncError(str(exc)) from exc

    meta_patch: Dict[str, Any] = {"usage_snapshot": snapshot}
    fulfillment_patch = dict(merge_fulfillment or {})
    if snapshot.get("activated_at"):
        fulfillment_patch["activated_at"] = snapshot["activated_at"]
    if fulfillment_patch:
        meta_patch["fulfillment"] = fulfillment_patch

    db.merge_order_metadata(order_number, meta_patch)

    allowance = db.get_breakage_allowance_by_order_number(order_number)
    if allowance and snapshot.get("data_used_gb") is not None:
        used_mb = int(round(float(snapshot["data_used_gb"]) * 1024))
        db.update_breakage_allowance(
            str(allowance["id"]),
            {
                "used_mb": used_mb,
                "last_synced_at": snapshot.get("synced_at"),
            },
        )

    refreshed = db.get_order_row_by_order_number(order_number)
    return refreshed or row


async def sync_order_usage(
    row: Dict[str, Any],
    *,
    source: str = "poll",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fetch live provider data and persist normalized usage snapshot."""
    order_number = str(row.get("order_number") or "")
    if not order_number:
        raise UsageSyncError("Order row missing order_number.")

    provider = resolve_order_provider(row)
    if not provider:
        raise UsageSyncError(f"Order {order_number} has no fulfillment provider.")

    allowance = db.get_breakage_allowance_by_order_number(order_number)
    provider_payload: Dict[str, Any] = {}
    try:
        provider_payload = await _fetch_provider_payload(provider, row)
    except UsageSyncError:
        raise
    except Exception as exc:
        logger.warning("Provider fetch failed for %s (%s): %s", order_number, provider, exc)
        if allowance:
            provider_payload = {}
        else:
            raise UsageSyncError(str(exc)) from exc

    snapshot = build_usage_snapshot(
        provider=provider,
        source=source,
        row=row,
        provider_payload=provider_payload,
        allowance_row=allowance,
        overrides=overrides,
    )
    merge_fulfillment = {}
    if snapshot.get("activated_at"):
        merge_fulfillment["activated_at"] = snapshot["activated_at"]
    return apply_usage_snapshot(order_number, snapshot, merge_fulfillment=merge_fulfillment)


def sync_order_usage_blocking(
    row: Dict[str, Any],
    *,
    source: str = "poll",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(sync_order_usage(row, source=source, overrides=overrides))
            ).result()
    return asyncio.run(sync_order_usage(row, source=source, overrides=overrides))


def parse_esimaccess_webhook_usage(content: Dict[str, Any]) -> Dict[str, Any]:
    """Extract usage overrides from eSIM Access webhook content."""
    overrides: Dict[str, Any] = {}
    total = content.get("totalVolume") or content.get("total_volume")
    used = content.get("orderUsage") or content.get("order_usage")
    if used is not None:
        gb = _bytes_to_gb(used)
        if gb is not None:
            overrides["data_used_gb"] = gb
    if total is not None:
        gb = _bytes_to_gb(total)
        if gb is not None:
            overrides["data_total_gb"] = gb
    esim_status = content.get("esimStatus") or content.get("esim_status")
    smdp_status = content.get("smdpStatus") or content.get("smdp_status")
    activation_status, activated = _activation_from_status(esim_status, smdp_status)
    overrides["activation_status"] = activation_status
    overrides["activated"] = activated
    if activated:
        overrides["activated_at"] = _utc_now_iso()
    expired = content.get("expiredTime") or content.get("expired_time")
    if expired:
        overrides["valid_until"] = expired
    return overrides
