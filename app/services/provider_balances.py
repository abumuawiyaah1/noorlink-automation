"""Fetch reseller wallet balances from upstream providers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def _citrus_balance() -> Dict[str, Any]:
    settings = get_settings()
    if not (settings.citrus_api_key or "").strip():
        return {"provider": "citrus", "configured": False}
    try:
        from app.services.citrus import CitrusClient

        async with CitrusClient() as client:
            wallet = await client.get_wallet_balance()
            account = await client.get_account()
        balance = wallet.get("balance_usd") or wallet.get("balance") or account.get("balance_usd")
        return {
            "provider": "citrus",
            "configured": True,
            "ok": True,
            "balance_usd": balance,
            "detail": account.get("email") or "Citrus reseller wallet",
        }
    except Exception as exc:
        logger.warning("Citrus balance fetch failed: %s", exc)
        return {"provider": "citrus", "configured": True, "ok": False, "error": str(exc)[:200]}


async def _simbase_balance() -> Dict[str, Any]:
    settings = get_settings()
    if not (settings.simbase_api_key or "").strip():
        return {"provider": "simbase", "configured": False}
    try:
        from app.services.simbase import SimbaseClient

        async with SimbaseClient() as client:
            payload = await client.get_account_balance()
        return {
            "provider": "simbase",
            "configured": True,
            "ok": True,
            "balance_usd": payload.get("balance") or payload.get("amount"),
            "currency": payload.get("currency") or "USD",
        }
    except Exception as exc:
        logger.warning("Simbase balance fetch failed: %s", exc)
        return {"provider": "simbase", "configured": True, "ok": False, "error": str(exc)[:200]}


async def fetch_provider_balances() -> List[Dict[str, Any]]:
    citrus, simbase = await asyncio.gather(_citrus_balance(), _simbase_balance())
    rows = [citrus, simbase]
    settings = get_settings()
    rows.append(
        {
            "provider": "telna",
            "configured": bool((settings.telna_api_token or "").strip()),
            "ok": None,
            "detail": "Telna Flex — check balance in Telna portal",
            "portal_url": "https://portal.telna.com/",
        }
    )
    rows.append(
        {
            "provider": "esimaccess",
            "configured": bool((settings.esim_access_access_code or "").strip()),
            "ok": None,
            "detail": "Check eSIM Access partner portal for prepaid balance",
        }
    )
    return rows


def fetch_provider_balances_sync() -> List[Dict[str, Any]]:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(fetch_provider_balances())
    finally:
        loop.close()
