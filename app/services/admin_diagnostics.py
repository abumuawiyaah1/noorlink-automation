"""System diagnostics for admin: email, analytics, provider catalog."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.analytics_store import get_trending, get_fallback
from app.services.provider_catalog import fetch_catalog_products


def get_email_diagnostics(*, probe: bool = False) -> Dict[str, Any]:
    settings = get_settings()
    from_email = (settings.resend_from_email or "").strip()
    configured = bool((settings.resend_api_key or "").strip())
    domain = from_email.rsplit("@", 1)[-1].rstrip(">").strip().lower() if "@" in from_email else None
    expected = "noorlink.co"
    matches = domain == expected

    result: Dict[str, Any] = {
        "ok": configured and matches,
        "resend_configured": configured,
        "from_email": from_email or "(empty)",
        "from_domain": domain,
        "domain_matches": matches,
        "hint": None,
        "test_send_ok": None,
        "test_send_error": None,
    }

    if not configured:
        result["hint"] = "Set RESEND_API_KEY in your environment."
    elif not matches:
        result["hint"] = f"RESEND_FROM_EMAIL should use @{expected}."

    if probe and configured:
        try:
            from app.services.email_service import send_email

            send_email(
                to_email="delivered@resend.dev",
                subject="NoorLink admin diagnostics probe",
                html_body="<p>Probe from NoorLink admin diagnostics.</p>",
            )
            result["test_send_ok"] = True
        except Exception as exc:
            result["test_send_ok"] = False
            result["test_send_error"] = str(exc)[:400]
            result["ok"] = False

    return result


def get_analytics_summary(*, limit: int = 10) -> Dict[str, Any]:
    trending = get_trending(limit=limit)
    fallback = get_fallback()
    return {"trending": trending, "fallback": fallback}


def search_provider_catalog(
    *,
    query: str = "",
    provider: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    products = fetch_catalog_products(provider=provider or None)
    needle = query.strip().lower()
    rows: List[Dict[str, Any]] = []
    for product in products:
        haystack = " ".join(
            [
                product.provider,
                product.provider_sku,
                product.name,
                " ".join(product.country_slugs),
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        rows.append(
            {
                "provider": product.provider,
                "provider_sku": product.provider_sku,
                "name": product.name,
                "scope": product.scope,
                "country_slugs": ", ".join(product.country_slugs),
                "data_gb": product.data_gb,
                "validity_days": product.validity_days,
                "wholesale_cents": product.wholesale_cents,
            }
        )
        if len(rows) >= limit:
            break
    return rows
