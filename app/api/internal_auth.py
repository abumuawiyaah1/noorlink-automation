"""Shared auth helpers for cron jobs and internal/admin API routes."""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import get_settings


def _cron_secret() -> str:
    return (get_settings().cron_secret or "").strip()


def require_cron_secret(authorization: Optional[str] = Header(None)) -> None:
    secret = _cron_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Cron is not configured.")
    expected = f"Bearer {secret}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized.")


def require_internal_in_production(authorization: Optional[str] = Header(None)) -> None:
    """In production, admin/debug routes need CRON_SECRET bearer token."""
    settings = get_settings()
    if settings.environment.lower() != "production":
        return
    require_cron_secret(authorization)
