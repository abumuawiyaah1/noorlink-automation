"""
Inbound provider webhooks (Simbase + Citrus Mobile + eSIM Access).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.citrus import CitrusClient, CitrusError
from app.services.simbase import SimbaseClient, SimbaseError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

# Task names + Simbase-documented limit.* events
USAGE_GUARD_EVENTS = {
    "usage_limits",
    "usage_exceeds_threshold",
    "limit.100mb",
    "limit.1gb",
}

# Citrus events that mean the SIM wallet / package is exhausted
CITRUS_SUSPEND_EVENTS = {
    "esim.balance_depleted",
    "esim.data_suspended",
    "esim.terminated",
}

# eSIM Access notify types (docs)
ESIMACCESS_KNOWN_TYPES = {
    "ORDER_STATUS",
    "ESIM_STATUS",
    "SMDP_EVENT",
    "DATA_USAGE",
    "VALIDITY_USAGE",
    "CHECK_HEALTH",
}


def _extract_event_type(payload: Dict[str, Any]) -> str:
    for key in ("event", "event_type", "type", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("event", "event_type", "type"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _extract_iccid(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("iccid", "ICCID"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("iccid", "ICCID"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    simcard = payload.get("simcard")
    if isinstance(simcard, dict):
        value = simcard.get("iccid")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_usage_bytes(payload: Dict[str, Any]) -> Optional[int]:
    candidates = (
        payload.get("current_bytes"),
        payload.get("usageBytes"),
        payload.get("usage_bytes"),
        payload.get("bytes"),
        payload.get("consumed_bytes"),
    )
    data = payload.get("data")
    if isinstance(data, dict):
        candidates = candidates + (
            data.get("current_bytes"),
            data.get("usageBytes"),
            data.get("usage_bytes"),
            data.get("bytes"),
            data.get("consumed_bytes"),
        )
    for value in candidates:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _is_usage_guard_event(event_type: str) -> bool:
    if not event_type:
        return False
    if event_type in USAGE_GUARD_EVENTS:
        return True
    lowered = event_type.lower()
    return lowered.startswith("limit.") or "usage" in lowered


def _token_valid(provided: Optional[str], expected: str) -> bool:
    if not expected:
        return False
    if not provided:
        return False
    return hmac.compare_digest(provided.strip(), expected.strip())


@router.post("/simbase")
async def simbase_usage_webhook(
    request: Request,
    x_simbase_requesttoken: Optional[str] = Header(
        default=None, alias="x-simbase-requesttoken"
    ),
):
    """
    Margin guard: when package data is exhausted, disable the SIM and suspend the order.
    """
    settings = get_settings()
    secret = (settings.simbase_webhook_secret or "").strip()
    if not _token_valid(x_simbase_requesttoken, secret):
        logger.warning("Simbase webhook rejected: invalid request token")
        raise HTTPException(status_code=401, detail="Invalid Simbase webhook token")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")

    event_type = _extract_event_type(payload)
    if not _is_usage_guard_event(event_type):
        return JSONResponse(
            {
                "ok": True,
                "handled": False,
                "reason": "ignored_event",
                "event": event_type or None,
            }
        )

    iccid = _extract_iccid(payload)
    if not iccid:
        raise HTTPException(status_code=400, detail="Missing iccid in webhook payload")

    usage_bytes = _extract_usage_bytes(payload)
    order = db.get_order_row_by_iccid(iccid)
    if not order:
        logger.info("Simbase webhook: no order for iccid=%s", iccid)
        return JSONResponse(
            {
                "ok": True,
                "handled": False,
                "reason": "order_not_found",
                "iccid": iccid,
                "event": event_type,
            }
        )

    limit_bytes = order.get("data_limit_bytes")
    try:
        limit_bytes_int = int(limit_bytes) if limit_bytes is not None else None
    except (TypeError, ValueError):
        limit_bytes_int = None

    # Suspend when usage meets/exceeds package cap, or when Simbase fires a limit.*
    # event and we cannot resolve a numeric package limit (fail closed on known limits).
    should_suspend = False
    if usage_bytes is not None and limit_bytes_int is not None:
        should_suspend = usage_bytes >= limit_bytes_int
    elif event_type.lower().startswith("limit.") or event_type in {
        "usage_limits",
        "usage_exceeds_threshold",
    }:
        if limit_bytes_int is None:
            should_suspend = True
        elif usage_bytes is not None:
            should_suspend = usage_bytes >= limit_bytes_int

    if not should_suspend:
        return JSONResponse(
            {
                "ok": True,
                "handled": False,
                "reason": "under_limit",
                "iccid": iccid,
                "usage_bytes": usage_bytes,
                "data_limit_bytes": limit_bytes_int,
                "event": event_type,
            }
        )

    if (order.get("status") or "") == "suspended":
        return JSONResponse(
            {
                "ok": True,
                "handled": True,
                "reason": "already_suspended",
                "iccid": iccid,
                "event": event_type,
            }
        )

    try:
        async with SimbaseClient() as client:
            await client.update_sim_state(iccid, "disabled")
    except SimbaseError as exc:
        logger.error(
            "Failed to disable SIM iccid=%s status=%s: %s",
            iccid,
            exc.status_code,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to disable SIM on provider.",
        ) from exc

    try:
        updated = db.suspend_order_by_iccid(iccid, usage_bytes=usage_bytes)
    except db.SupabaseRepositoryError as exc:
        logger.exception("Failed to suspend order for iccid=%s", iccid)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    logger.warning(
        "Margin guard suspended iccid=%s usage_bytes=%s limit=%s order=%s",
        iccid,
        usage_bytes,
        limit_bytes_int,
        (updated or {}).get("order_number"),
    )
    return JSONResponse(
        {
            "ok": True,
            "handled": True,
            "action": "suspended",
            "iccid": iccid,
            "usage_bytes": usage_bytes,
            "data_limit_bytes": limit_bytes_int,
            "order_number": (updated or {}).get("order_number"),
            "event": event_type,
        }
    )


def _citrus_signature_valid(raw_body: bytes, provided: Optional[str], secret: str) -> bool:
    if not secret or not provided:
        return False
    digest = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    expected = provided.strip()
    # Accept raw hex or sha256=<hex>
    if expected.lower().startswith("sha256="):
        expected = expected.split("=", 1)[1].strip()
    return hmac.compare_digest(digest, expected)


@router.post("/citrus")
async def citrus_lifecycle_webhook(
    request: Request,
    x_citrus_signature: Optional[str] = Header(default=None, alias="X-Citrus-Signature"),
):
    """
    Citrus Mobile webhooks.

    Margin model: fund each eSIM only up to the sold package value. When
    `esim.balance_depleted` fires, disable the SIM and mark the order suspended.
    """
    settings = get_settings()
    secret = (settings.citrus_webhook_secret or "").strip()
    raw = await request.body()
    if not _citrus_signature_valid(raw, x_citrus_signature, secret):
        logger.warning("Citrus webhook rejected: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid Citrus webhook signature")

    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")

    event_type = _extract_event_type(payload)
    if event_type in {"test", "ping"}:
        return JSONResponse({"ok": True, "handled": True, "reason": "test_event"})

    if event_type not in CITRUS_SUSPEND_EVENTS:
        return JSONResponse(
            {
                "ok": True,
                "handled": False,
                "reason": "ignored_event",
                "event": event_type or None,
            }
        )

    iccid = _extract_iccid(payload)
    if not iccid:
        raise HTTPException(status_code=400, detail="Missing iccid in webhook payload")

    order = db.get_order_row_by_iccid(iccid)
    if not order:
        logger.info("Citrus webhook: no order for iccid=%s event=%s", iccid, event_type)
        return JSONResponse(
            {
                "ok": True,
                "handled": False,
                "reason": "order_not_found",
                "iccid": iccid,
                "event": event_type,
            }
        )

    if (order.get("status") or "") == "suspended":
        return JSONResponse(
            {
                "ok": True,
                "handled": True,
                "reason": "already_suspended",
                "iccid": iccid,
                "event": event_type,
            }
        )

    if event_type == "esim.balance_depleted":
        try:
            async with CitrusClient() as client:
                await client.disable_esim(iccid)
        except CitrusError as exc:
            # Already depleted network-side — still suspend locally; log disable failures.
            logger.error(
                "Citrus disable failed iccid=%s status=%s: %s",
                iccid,
                getattr(exc, "status_code", None),
                exc,
            )

    try:
        updated = db.suspend_order_by_iccid(iccid)
    except db.SupabaseRepositoryError as exc:
        logger.exception("Failed to suspend order for citrus iccid=%s", iccid)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    logger.warning(
        "Citrus margin guard suspended iccid=%s event=%s order=%s",
        iccid,
        event_type,
        (updated or {}).get("order_number"),
    )
    return JSONResponse(
        {
            "ok": True,
            "handled": True,
            "action": "suspended",
            "iccid": iccid,
            "order_number": (updated or {}).get("order_number"),
            "event": event_type,
        }
    )


@router.post("/esimaccess")
async def esimaccess_webhook(request: Request) -> JSONResponse:
    """
    Ingest eSIM Access notifications (ORDER_STATUS, SMDP_EVENT, low-balance, etc.).

    Phase A: acknowledge + log. Profile details are fetched at provision time;
    webhooks are used for ops visibility and future status sync.
    """
    settings = get_settings()
    secret = (settings.esim_access_webhook_secret or "").strip()
    if settings.environment.lower() == "production" and not secret:
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    raw = await request.body()

    if secret:
        token = (
            request.headers.get("x-esimaccess-token")
            or request.headers.get("x-webhook-token")
            or request.headers.get("x-esim-access-token")
            or ""
        ).strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token or not hmac.compare_digest(token, secret):
            raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be an object")

    notify_type = str(
        payload.get("notifyType")
        or payload.get("type")
        or payload.get("event")
        or ""
    ).strip().upper()

    content = payload.get("content")
    order_no = payload.get("orderNo")
    if not order_no and isinstance(content, dict):
        order_no = content.get("orderNo")

    iccid = _extract_iccid(payload)
    if not iccid and isinstance(content, dict):
        iccid = _extract_iccid(content)

    logger.info(
        "eSIM Access webhook type=%s orderNo=%s iccid=%s",
        notify_type or "(none)",
        order_no,
        iccid,
    )

    if notify_type == "CHECK_HEALTH":
        return JSONResponse({"ok": True, "handled": True, "reason": "health_check"})

    # Persist lightweight breadcrumb on matching order when we already have ICCID
    if iccid:
        try:
            order = db.get_order_row_by_iccid(str(iccid))
            if order:
                db.merge_order_metadata(
                    order["order_number"],
                    {
                        "fulfillment": {
                            "esimaccess_last_webhook": notify_type or "unknown",
                            "esimaccess_order_no": order_no,
                        }
                    },
                )
        except Exception:
            logger.exception("Failed to merge eSIM Access webhook metadata")

    return JSONResponse(
        {
            "ok": True,
            "handled": notify_type in ESIMACCESS_KNOWN_TYPES or not notify_type,
            "notifyType": notify_type or None,
            "orderNo": order_no,
            "iccid": iccid,
        }
    )
