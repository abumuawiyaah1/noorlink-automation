"""Scheduled usage sync for active eSIM orders."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.api import supabase_repository as db
from app.services.esim_usage_sync import UsageSyncError, sync_order_usage

logger = logging.getLogger(__name__)

SYNC_LOOKBACK_DAYS = 120
SYNC_BATCH_LIMIT = 150


def process_esim_usage_sync(*, limit: int = SYNC_BATCH_LIMIT) -> Dict[str, Any]:
    """Poll upstream providers for delivered/active orders and refresh usage snapshots."""
    since = (datetime.now(timezone.utc) - timedelta(days=SYNC_LOOKBACK_DAYS)).isoformat()
    try:
        rows = db.list_orders_for_usage_sync(since_iso=since, limit=limit)
    except db.SupabaseRepositoryError as exc:
        return {"success": False, "error": str(exc)[:240]}

    synced = 0
    skipped = 0
    errors: List[str] = []

    async def _run_batch() -> None:
        nonlocal synced, skipped
        for row in rows:
            order_number = str(row.get("order_number") or "")
            iccid = str(row.get("iccid") or "").strip()
            if not iccid:
                skipped += 1
                continue
            try:
                await sync_order_usage(row, source="cron")
                synced += 1
            except UsageSyncError as exc:
                errors.append(f"{order_number}: {exc}")
            except Exception as exc:
                logger.exception("Usage sync cron failed for %s", order_number)
                errors.append(f"{order_number}: {str(exc)[:80]}")

    try:
        asyncio.run(_run_batch())
    except RuntimeError:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(lambda: asyncio.run(_run_batch())).result()

    return {
        "success": True,
        "candidates": len(rows),
        "synced": synced,
        "skipped": skipped,
        "errors": errors[:20],
    }
