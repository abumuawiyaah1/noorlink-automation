"""Breakage allowance admin list."""

from __future__ import annotations

from typing import Any, Dict, List

from app.api import supabase_repository as db


def list_breakage_allowances(*, limit: int = 100) -> List[Dict[str, Any]]:
    try:
        client = db.get_supabase_client()
        result = (
            client.table("breakage_allowances")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        return []
