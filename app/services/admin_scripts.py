"""Whitelisted admin maintenance and test scripts."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.db.engine import get_engine
from app.services.admin_diagnostics import get_email_diagnostics
from app.services.insider_release import expire_finished_promos
from app.services.provider_catalog import sync_telna_catalog

logger = logging.getLogger(__name__)


class AdminScriptError(Exception):
    """Whitelisted script failed."""


@dataclass(frozen=True)
class AdminScript:
    key: str
    title: str
    summary: str
    category: str  # test | maintenance
    confirmation: str


ADMIN_SCRIPTS: tuple[AdminScript, ...] = (
    AdminScript(
        key="health_check",
        title="Health check",
        summary="Verify database and Supabase connectivity.",
        category="test",
        confirmation="Run a read-only health check?",
    ),
    AdminScript(
        key="email_probe",
        title="Email probe",
        summary="Send a test message to Resend's sandbox inbox.",
        category="test",
        confirmation="Send a test email via Resend?",
    ),
    AdminScript(
        key="telna_probe",
        title="Telna connectivity probe",
        summary="Read-only check that Telna Ordering API responds (needs User-Agent).",
        category="test",
        confirmation="Ping Telna API (read-only)?",
    ),
    AdminScript(
        key="expire_promos",
        title="Expire finished promos",
        summary="Mark promos past end date as inactive.",
        category="maintenance",
        confirmation="Expire promos whose end date has passed?",
    ),
    AdminScript(
        key="sync_telna_catalog",
        title="Sync Telna catalog",
        summary="Refresh provider_catalog_products from Telna.",
        category="maintenance",
        confirmation="Sync Telna provider SKUs into the warehouse?",
    ),
    AdminScript(
        key="run_cron_subset",
        title="Run maintenance batch",
        summary="Expire promos + sync catalog + usage sync (no Insider send).",
        category="maintenance",
        confirmation="Run maintenance tasks (excludes Insider mass send)?",
    ),
)


async def _telna_probe_async() -> Dict[str, Any]:
    settings = get_settings()
    token = (settings.telna_api_token or "").strip()
    account = (settings.telna_account_id or "").strip()
    ordering = settings.telna_ordering_base_url.rstrip("/")

    result: Dict[str, Any] = {
        "token_configured": bool(token),
        "account_id_configured": bool(account),
        "checks": [],
    }
    if not token:
        result["ok"] = False
        result["summary"] = "TELNA_API_TOKEN is not configured."
        return result

    headers = {
        "Authorization": token,
        "Accept": "application/json",
        "User-Agent": "NoorLink/1.0 (+https://noorlink.co)",
    }
    params: Optional[Dict[str, Any]] = {"count": 1, "offset": 0}
    if account:
        params["account"] = account

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{ordering}/products", headers=headers, params=params)
            ok = response.status_code == 200
            result["checks"].append(
                {"name": "list_products", "status_code": response.status_code, "ok": ok}
            )
            result["ok"] = ok
            result["summary"] = (
                "Telna Ordering API is reachable."
                if ok
                else f"Telna probe failed with HTTP {response.status_code}."
            )
        except httpx.RequestError as exc:
            result["ok"] = False
            result["summary"] = str(exc)
    return result


def run_admin_script(key: str) -> Dict[str, Any]:
    script = next((s for s in ADMIN_SCRIPTS if s.key == key), None)
    if script is None:
        raise AdminScriptError(f"Unknown script: {key}")

    if key == "health_check":
        engine_ok = get_engine() is not None
        supabase_ok = False
        try:
            db.get_supabase_client()
            supabase_ok = True
        except Exception as exc:
            logger.warning("Supabase health check failed: %s", exc)
        return {
            "ok": engine_ok and supabase_ok,
            "database_engine": engine_ok,
            "supabase_client": supabase_ok,
        }

    if key == "email_probe":
        result = get_email_diagnostics(probe=True)
        if not result.get("test_send_ok"):
            raise AdminScriptError(result.get("test_send_error") or result.get("hint") or "Email probe failed.")
        return result

    if key == "telna_probe":
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_telna_probe_async())
        finally:
            loop.close()

    if key == "expire_promos":
        count = expire_finished_promos()
        return {"ok": True, "expired_promos": count}

    if key == "sync_telna_catalog":
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(sync_telna_catalog(use_builtin_on_failure=True))
        finally:
            loop.close()

    if key == "run_cron_subset":
        from app.services.expiry_reminders import process_esim_expiry_reminders
        from app.services.usage_sync_cron import process_esim_usage_sync

        result: Dict[str, Any] = {"ok": True, "tasks": {}}
        try:
            result["tasks"]["expired_promos"] = expire_finished_promos()
        except Exception as exc:
            result["tasks"]["expired_promos"] = {"error": str(exc)}
            result["ok"] = False
        try:
            loop = asyncio.new_event_loop()
            try:
                result["tasks"]["catalog_sync"] = loop.run_until_complete(
                    sync_telna_catalog(use_builtin_on_failure=True)
                )
            finally:
                loop.close()
        except Exception as exc:
            result["tasks"]["catalog_sync"] = {"error": str(exc)[:240]}
        try:
            result["tasks"]["expiry_reminders"] = process_esim_expiry_reminders()
        except Exception as exc:
            result["tasks"]["expiry_reminders"] = {"error": str(exc)[:240]}
        try:
            result["tasks"]["usage_sync"] = process_esim_usage_sync()
        except Exception as exc:
            result["tasks"]["usage_sync"] = {"error": str(exc)[:240]}
        result["note"] = "Insider mass-send excluded — use full cron for newsletters."
        return result

    raise AdminScriptError(f"Script not implemented: {key}")


def get_script_by_key(key: str) -> Optional[AdminScript]:
    return next((s for s in ADMIN_SCRIPTS if s.key == key), None)
