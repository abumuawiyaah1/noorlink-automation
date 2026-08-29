"""Purge old operational log rows."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.api import supabase_repository as db

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


def purge_old_ops_logs(*, retention_days: int = DEFAULT_RETENTION_DAYS) -> Dict[str, Any]:
    """Delete ops_event_log and email_delivery_events older than retention window."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    deleted: Dict[str, int] = {}

    for table in ("ops_event_log", "email_delivery_events"):
        try:
            client = db.get_supabase_client()
            result = client.table(table).delete().lt("created_at", cutoff).execute()
            deleted[table] = len(result.data or [])
        except Exception as exc:
            logger.warning("Log retention purge failed for %s: %s", table, exc)
            deleted[table] = 0

    return {"retention_days": retention_days, "cutoff": cutoff, "deleted": deleted}
