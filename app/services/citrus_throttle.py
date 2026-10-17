"""Citrus eSIM speed throttle helpers (fair-use soft step)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.api import supabase_repository as db

logger = logging.getLogger(__name__)

SPEED_FULL = "NO_LIMIT"
SPEED_500 = "SPEED_500_KBPS"


async def throttle_citrus_esim(
    row: Dict[str, Any],
    *,
    speed: str,
    reason: str,
) -> Dict[str, Any]:
    """Apply a Citrus throttle speed and record it on the order."""
    from app.services.citrus import CitrusClient, CitrusError
    from app.services.esim_usage_sync import resolve_order_provider

    order_number = str(row.get("order_number") or "")
    iccid = str(row.get("iccid") or "").strip()
    if resolve_order_provider(row) != "citrus":
        return {"skipped": True, "reason": "not_citrus"}
    if not iccid:
        raise ValueError(f"Order {order_number} has no ICCID for throttle")

    speed_value = (speed or "").strip().upper() or SPEED_FULL
    async with CitrusClient() as client:
        try:
            result = await client.throttle_esim(iccid, speed_value)
        except CitrusError:
            raise

    now = datetime.now(timezone.utc).isoformat()
    if order_number:
        try:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            fulfillment = (
                meta.get("fulfillment") if isinstance(meta.get("fulfillment"), dict) else {}
            )
            db.merge_order_metadata(
                order_number,
                {
                    "fulfillment": {
                        **fulfillment,
                        "throttle_speed": speed_value,
                        "throttled_at": now,
                        "throttle_reason": reason,
                    }
                },
            )
        except Exception:
            logger.warning("Could not persist throttle metadata for %s", order_number)

    logger.info(
        "Citrus throttle order=%s iccid=%s speed=%s reason=%s",
        order_number,
        iccid,
        speed_value,
        reason,
    )
    return {"ok": True, "speed": speed_value, "result": result if isinstance(result, dict) else {}}


def throttle_citrus_esim_blocking(
    row: Dict[str, Any],
    *,
    speed: str,
    reason: str,
) -> Dict[str, Any]:
    """Sync wrapper for cron / reminder paths."""

    async def _run() -> Dict[str, Any]:
        return await throttle_citrus_esim(row, speed=speed, reason=reason)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(_run())).result()
    return asyncio.run(_run())
