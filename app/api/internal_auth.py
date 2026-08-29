"""Shared auth helpers for cron jobs and internal/admin API routes."""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException, Request

from app.core.config import get_settings


def _cron_secret() -> str:
    return (get_settings().cron_secret or "").strip()


def require_cron_secret(authorization: Optional[str] = Header(None)) -> None:
    secret = _cron_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Cron is not configured.")
    expected = f"Bearer {secret}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        from app.services.security_threats import log_security_event

        log_security_event(
            threat_type="cron_unauthorized",
            source="cron_api",
            message="Invalid or missing CRON_SECRET bearer token",
            severity="warning",
        )
        raise HTTPException(status_code=401, detail="Unauthorized.")


def require_internal_in_production(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> None:
    """In production, admin/debug routes need CRON_SECRET bearer token."""
    settings = get_settings()
    if settings.environment.lower() != "production":
        return
    secret = _cron_secret()
    expected = f"Bearer {secret}"
    if not authorization or not secret or not hmac.compare_digest(authorization, expected):
        ip_address = None
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        elif request.client:
            ip_address = request.client.host
        from app.services.security_threats import log_security_event

        log_security_event(
            threat_type="internal_unauthorized",
            source="internal_api",
            message="Unauthorized access to protected internal route",
            severity="warning",
            ip_address=ip_address,
            details={"path": str(request.url.path)},
        )
        raise HTTPException(status_code=401, detail="Unauthorized.")
