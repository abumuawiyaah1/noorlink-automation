"""eSIM data top-up (Citrus fund + Stripe checkout)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.api import supabase_repository as db
from app.services.esim_usage_sync import resolve_order_provider, sync_order_usage_blocking

logger = logging.getLogger(__name__)

TOPUP_AMOUNTS_USD = [5.0, 10.0, 15.0, 20.0, 30.0]
MIN_TOPUP_USD = 5.0
MAX_TOPUP_USD = 100.0
TOPUP_MARKUP = 1.35  # retail = wholesale fund * markup


class TopUpError(Exception):
    """Top-up action failed."""


def topup_retail_cents(fund_usd: float) -> int:
    retail = round(float(fund_usd) * TOPUP_MARKUP, 2)
    return int(round(retail * 100))


def topup_capabilities(row: Dict[str, Any]) -> Dict[str, Any]:
    provider = resolve_order_provider(row)
    iccid = str(row.get("iccid") or "").strip()
    status = str(row.get("status") or "").lower()
    meta = row.get("metadata") or {}
    snapshot = meta.get("usage_snapshot") if isinstance(meta, dict) else None
    topup_supported = False
    reason = None

    if status in {"refunded", "failed", "pending"}:
        reason = "Order is not active."
    elif not iccid:
        reason = "No ICCID on this order yet."
    elif provider == "citrus":
        topup_supported = status in {"delivered", "active", "suspended"}
    elif provider == "esimaccess":
        topup_supported = False
        reason = "Fixed-pack eSIM Access plans are repurchased as a new plan, not topped up in place."
    elif provider == "telna":
        topup_supported = False
        reason = "Telna top-up is not wired yet — contact support."
    else:
        reason = f"Top-up not available for provider '{provider or 'unknown'}'."

    if isinstance(snapshot, dict) and snapshot.get("topup_supported") is False and provider == "citrus":
        topup_supported = True

    return {
        "supported": topup_supported,
        "provider": provider,
        "iccid": iccid or None,
        "amounts_usd": TOPUP_AMOUNTS_USD if topup_supported else [],
        "min_usd": MIN_TOPUP_USD if topup_supported else None,
        "max_usd": MAX_TOPUP_USD if topup_supported else None,
        "reason": reason,
    }


async def fund_citrus_topup(
    row: Dict[str, Any],
    fund_usd: float,
    *,
    source: str = "admin",
    actor: Optional[str] = None,
    stripe_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move wholesale USD onto a Citrus SIM wallet."""
    order_number = str(row.get("order_number") or "")
    iccid = str(row.get("iccid") or "").strip()
    provider = resolve_order_provider(row)

    if provider != "citrus":
        raise TopUpError("Only Citrus PAYG eSIMs support in-place top-up today.")
    if not iccid:
        raise TopUpError("Order has no ICCID.")
    if fund_usd < MIN_TOPUP_USD or fund_usd > MAX_TOPUP_USD:
        raise TopUpError(f"Top-up must be between ${MIN_TOPUP_USD} and ${MAX_TOPUP_USD}.")

    from app.services.citrus import CitrusClient, CitrusError

    async with CitrusClient() as client:
        try:
            result = await client.fund_esim(iccid, float(fund_usd))
        except CitrusError as exc:
            raise TopUpError(str(exc)) from exc

        if str(row.get("status") or "") == "suspended":
            try:
                await client.enable_esim(iccid)
                db.get_supabase_client().table("orders").update({"status": "active"}).eq(
                    "order_number", order_number
                ).execute()
            except Exception:
                logger.warning("Could not re-enable Citrus eSIM after top-up for %s", order_number)

    meta = row.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    history = []
    topups = meta.get("topups")
    if isinstance(topups, dict) and isinstance(topups.get("history"), list):
        history = list(topups["history"])

    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "fund_usd": float(fund_usd),
        "source": source,
        "actor": actor,
        "stripe_session_id": stripe_session_id,
        "provider_result": result if isinstance(result, dict) else {"raw": result},
    }
    history.append(entry)

    fulfillment = meta.get("fulfillment") if isinstance(meta.get("fulfillment"), dict) else {}
    fulfillment = {
        **fulfillment,
        "last_topup_at": entry["at"],
        "last_topup_usd": fund_usd,
    }
    db.merge_order_metadata(
        order_number,
        {
            "topups": {"history": history},
            "fulfillment": fulfillment,
        },
    )

    refreshed = db.get_order_row_by_order_number(order_number) or row
    try:
        sync_order_usage_blocking(refreshed, source="topup")
    except Exception:
        logger.warning("Post top-up usage sync failed for %s", order_number)

    logger.info(
        "Top-up $%s on %s iccid=%s source=%s actor=%s",
        fund_usd,
        order_number,
        iccid,
        source,
        actor,
    )
    return {"ok": True, "order_number": order_number, "fund_usd": fund_usd, "entry": entry}


def fund_citrus_topup_blocking(
    row: Dict[str, Any],
    fund_usd: float,
    **kwargs: Any,
) -> Dict[str, Any]:
    import asyncio

    return asyncio.run(fund_citrus_topup(row, fund_usd, **kwargs))


async def process_topup_checkout(
    *,
    order_number: str,
    fund_usd: float,
    stripe_session_id: Optional[str] = None,
    buyer_email: Optional[str] = None,
) -> Dict[str, Any]:
    row = db.get_order_row_by_order_number(order_number)
    if not row:
        raise TopUpError(f"Order {order_number} not found.")

    caps = topup_capabilities(row)
    if not caps.get("supported"):
        raise TopUpError(str(caps.get("reason") or "Top-up not supported."))

    return await fund_citrus_topup(
        row,
        fund_usd,
        source="stripe_checkout",
        actor=buyer_email,
        stripe_session_id=stripe_session_id,
    )
