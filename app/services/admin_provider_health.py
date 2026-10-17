"""Provider connectivity health checks."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import get_settings
from app.services.admin_scripts import _telna_probe_async


def build_provider_health() -> List[Dict[str, Any]]:
    settings = get_settings()
    rows: List[Dict[str, Any]] = []

    rows.append(
        {
            "provider": "citrus",
            "configured": bool((settings.citrus_api_key or "").strip()),
            "status": "configured" if settings.citrus_api_key else "missing",
            "detail": "PAYG / Flex top-ups and many regional plans",
        }
    )
    rows.append(
        {
            "provider": "esimaccess",
            "configured": bool((settings.esim_access_access_code or "").strip()),
            "status": "configured" if settings.esim_access_access_code else "missing",
            "detail": "Saudi / Umrah, Ghana, and Access-mapped routes",
        }
    )
    rows.append(
        {
            "provider": "zesimo",
            "configured": bool((settings.zesimo_api_key or "").strip()),
            "status": "configured" if settings.zesimo_api_key else "missing",
            "detail": "SA unlimited and Zesimo-mapped fixed plans",
        }
    )
    rows.append(
        {
            "provider": "simbase",
            "configured": bool((settings.simbase_api_key or "").strip()),
            "status": "configured" if settings.simbase_api_key else "optional",
            "detail": "Legacy usage guard provider",
        }
    )
    rows.append(
        {
            "provider": "telna",
            "configured": bool((settings.telna_api_token or "").strip()),
            "status": "retired",
            "detail": "Retired for new sales — legacy SIMs only",
        }
    )
    rows.append(
        {
            "provider": "stripe",
            "configured": bool((settings.stripe_secret_key or "").strip()),
            "status": "configured" if settings.stripe_webhook_secret else "partial",
            "detail": "Payments + webhooks",
        }
    )
    rows.append(
        {
            "provider": "resend",
            "configured": bool((settings.resend_api_key or "").strip()),
            "status": "configured",
            "detail": settings.resend_from_email or "",
        }
    )
    return rows


async def run_provider_probes() -> Dict[str, Any]:
    """Refresh health rows; Telna probe kept for legacy diagnostics only."""
    telna = await _telna_probe_async()
    return {"telna": telna, "providers": build_provider_health()}
