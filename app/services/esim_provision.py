"""
eSIM provisioning adapter.

Providers:
  - mock (default / development)
  - citrus (Citrus Mobile reseller API)
  - simbase (reserved; not wired for auto-provision yet)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Demo SM-DP+ host — swap for real provider endpoint in production
MOCK_SMDP_HOST = "smdp.noorlink-demo.example"


def _activation_code_from_lpa(lpa_string: str) -> str:
    parts = (lpa_string or "").split("$")
    if len(parts) >= 3 and parts[-1].strip():
        return parts[-1].strip()
    return lpa_string.strip()


def _smdp_from_lpa(lpa_string: str) -> str:
    parts = (lpa_string or "").split("$")
    if len(parts) >= 2:
        return parts[1].strip()
    return ""


def _mock_provision(order_row: Dict[str, Any]) -> Dict[str, str]:
    order_number = order_row["order_number"]
    digest = hashlib.sha256(order_number.encode()).hexdigest()[:12].upper()
    activation_code = f"NL-{digest}"
    lpa_string = f"LPA:1${MOCK_SMDP_HOST}${activation_code}"
    qr_code_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=320x320&data={quote(lpa_string)}"
    )
    logger.info("Provisioned mock eSIM for order %s", order_number)
    return {
        "activation_code": activation_code,
        "qr_code_url": qr_code_url,
        "lpa_string": lpa_string,
        "provider": "noorlink-mock",
    }


async def _citrus_provision_async(order_row: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.citrus import CitrusClient

    order_number = order_row["order_number"]
    email = str(order_row.get("email") or "")
    country = str(order_row.get("country") or "")
    label = f"{email} — {country}".strip(" —")

    async with CitrusClient() as client:
        payload = await client.provision_esim(
            end_user_reference=order_number,
            label=label[:120] if label else order_number,
        )

    lpa_string = str(payload.get("lpa_string") or "").strip()
    if not lpa_string:
        raise RuntimeError("Citrus provision response missing lpa_string")

    qr_code = str(payload.get("qr_code") or "").strip()
    if not qr_code:
        # Fallback external QR if Citrus omits data-URI
        qr_code = (
            "https://api.qrserver.com/v1/create-qr-code/"
            f"?size=320x320&data={quote(lpa_string)}"
        )

    activation_code = _activation_code_from_lpa(lpa_string)
    smdp = _smdp_from_lpa(lpa_string)
    iccid = str(payload.get("iccid") or "").strip()

    logger.info(
        "Provisioned Citrus eSIM for order %s iccid=%s",
        order_number,
        iccid or "(none)",
    )
    return {
        "activation_code": activation_code,
        "qr_code_url": qr_code,
        "lpa_string": lpa_string,
        "provider": "citrus",
        "iccid": iccid,
        "smdp_address": smdp,
        "raw": payload,
    }


def _citrus_provision(order_row: Dict[str, Any]) -> Dict[str, Any]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Called from async context — run in a dedicated thread/loop.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(_citrus_provision_async(order_row))
            ).result()
    return asyncio.run(_citrus_provision_async(order_row))


def resolve_provider(explicit: Optional[str] = None) -> str:
    settings = get_settings()
    provider = (explicit or settings.esim_provider or "mock").strip().lower()
    if provider == "citrus" and not settings.citrus_api_key.strip():
        logger.warning("ESIM_PROVIDER=citrus but CITRUS_API_KEY empty; using mock")
        return "mock"
    if provider == "simbase" and not settings.simbase_api_key.strip():
        logger.warning("ESIM_PROVIDER=simbase but SIMBASE_API_KEY empty; using mock")
        return "mock"
    return provider or "mock"


def provision_esim(order_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return QR image URL/data-URI and activation credentials for the order.
    """
    provider = resolve_provider()
    if provider == "citrus":
        return _citrus_provision(order_row)
    if provider == "simbase":
        raise NotImplementedError(
            "Simbase auto-provision is not wired yet; set ESIM_PROVIDER=citrus or mock"
        )
    return _mock_provision(order_row)
