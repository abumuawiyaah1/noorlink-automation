"""
eSIM provisioning adapter.

Providers:
  - mock (default / development)
  - citrus (Citrus Mobile reseller API)
  - esimaccess (eSIM Access / Redtea — Saudi Phase A)
  - telna (Telna Connect Flex)
  - simbase (reserved; not wired for auto-provision yet)

Routing:
  1. plan_fulfillment_map (or static SA seeds) when matched
  2. else global ESIM_PROVIDER
  Saudi enforcement: must map to esimaccess when ESIM_ACCESS_ENFORCE_SAUDI=true
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

from app.core.config import get_settings
from app.services.fulfillment_map import (
    FulfillmentMapError,
    FulfillmentTarget,
    enforce_saudi_access_policy,
    resolve_fulfillment_target,
)

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


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)


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
    return _run_async(_citrus_provision_async(order_row))


def _lpa_from_access_profile(profile: Dict[str, Any]) -> str:
    ac = str(profile.get("ac") or "").strip()
    if ac.startswith("LPA:"):
        return ac
    # Some payloads only return qr / short URL — keep empty and rely on qrCodeUrl
    return ac


async def _esimaccess_provision_async(
    order_row: Dict[str, Any],
    target: FulfillmentTarget,
) -> Dict[str, Any]:
    from app.services.esim_access import (
        EsimAccessClient,
        EsimAccessInsufficientBalanceError,
        usd_to_api_price,
    )

    order_number = str(order_row["order_number"])
    package_code = target.provider_sku or target.provider_slug
    if not package_code:
        raise RuntimeError("eSIM Access map missing provider_sku")

    # Idempotency: reuse Access transactionId = order_number
    transaction_id = order_number

    price_api = None
    amount_api = None
    if target.wholesale_cents is not None:
        price_api = usd_to_api_price(target.wholesale_cents / 100.0)
        amount_api = price_api

    async with EsimAccessClient() as client:
        balance = await client.get_balance()
        if target.wholesale_cents is not None:
            need = target.wholesale_cents / 100.0
            if float(balance.get("balance_usd") or 0) < need:
                raise EsimAccessInsufficientBalanceError(
                    f"eSIM Access balance ${balance.get('balance_usd')} "
                    f"below wholesale ${need:.2f}",
                    code="200007",
                )

        try:
            order_obj = await client.order_esim(
                transaction_id=transaction_id,
                package_code=package_code,
                count=1,
                period_num=target.period_num,
                price_api=price_api,
                amount_api=amount_api,
            )
        except Exception as first_exc:
            # Duplicate transactionId → fetch existing order instead of double-charge
            code = getattr(first_exc, "code", None)
            if str(code) == "310402":
                logger.warning(
                    "eSIM Access duplicate transactionId %s; querying existing",
                    transaction_id,
                )
                # Fall through to query by scanning? Access needs orderNo.
                # Re-raise with context — caller metadata may already have orderNo.
                raise
            # Retry once with slug if PlanId rejected
            if target.provider_slug and package_code != target.provider_slug:
                logger.warning(
                    "eSIM Access order with %s failed (%s); retrying slug %s",
                    package_code,
                    first_exc,
                    target.provider_slug,
                )
                order_obj = await client.order_esim(
                    transaction_id=f"{transaction_id}-slug",
                    package_code=target.provider_slug,
                    count=1,
                    period_num=target.period_num,
                    price_api=price_api,
                    amount_api=amount_api,
                )
            else:
                raise

        order_no = str(order_obj.get("orderNo") or "")
        profile = await client.wait_for_profile(order_no=order_no)

    lpa_string = _lpa_from_access_profile(profile)
    qr_code = str(profile.get("qrCodeUrl") or "").strip()
    if not qr_code and lpa_string:
        qr_code = (
            "https://api.qrserver.com/v1/create-qr-code/"
            f"?size=320x320&data={quote(lpa_string)}"
        )
    if not qr_code and not lpa_string:
        raise RuntimeError("eSIM Access profile missing qrCodeUrl and activation code")

    activation_code = _activation_code_from_lpa(lpa_string) if lpa_string else order_no
    smdp = _smdp_from_lpa(lpa_string)
    iccid = str(profile.get("iccid") or "").strip()

    logger.info(
        "Provisioned eSIM Access for order %s orderNo=%s iccid=%s sku=%s",
        order_number,
        order_no,
        iccid or "(none)",
        package_code,
    )
    return {
        "activation_code": activation_code,
        "qr_code_url": qr_code,
        "lpa_string": lpa_string or qr_code,
        "provider": "esimaccess",
        "iccid": iccid,
        "smdp_address": smdp,
        "provider_order_id": order_no,
        "provider_sku": package_code,
        "catalog_key": target.catalog_key,
        "esim_tran_no": str(profile.get("esimTranNo") or ""),
        "raw": {"order": order_obj, "profile": profile},
    }


def _esimaccess_provision(
    order_row: Dict[str, Any], target: FulfillmentTarget
) -> Dict[str, Any]:
    return _run_async(_esimaccess_provision_async(order_row, target))


async def _telna_provision_async(
    order_row: Dict[str, Any],
    target: FulfillmentTarget,
) -> Dict[str, Any]:
    from app.services.telna import TelnaClient, TelnaError

    order_number = str(order_row["order_number"])
    product_id = (target.provider_sku or target.provider_slug or "").strip()
    if not product_id:
        raise RuntimeError("Telna map missing provider_sku (product id)")

    async with TelnaClient() as client:
        work_order = await client.create_work_order(
            product_id=product_id,
            customer_ref=order_number,
        )
        status = str(work_order.get("status") or "").upper()
        work_order_id = str(work_order.get("id") or "")

        # Poll briefly if profile is still preparing
        if status in {"PREPARING", "PENDING"} and work_order_id:
            for _ in range(8):
                await asyncio.sleep(1.5)
                work_order = await client.get_work_order(work_order_id)
                status = str(work_order.get("status") or "").upper()
                if status in {"SHIPPED", "FAILED", "REFUNDED"}:
                    break

        if status == "FAILED":
            raise TelnaError(
                f"Telna work order failed: {work_order.get('failure_msg') or status}"
            )
        if status == "REFUNDED":
            raise TelnaError("Telna work order was refunded")

        euicc = work_order.get("euicc_profile")
        if not isinstance(euicc, dict):
            euicc = {}
        sim_registry = work_order.get("sim_registry")
        if not isinstance(sim_registry, dict):
            sim_registry = {}
        iccid = str(euicc.get("iccid") or sim_registry.get("iccid") or "").strip()
        lpa_string = str(euicc.get("activation_code") or "").strip()

        if (not lpa_string or not iccid) and iccid:
            try:
                refreshed = await client.get_euicc_profile(iccid)
                if isinstance(refreshed, dict):
                    lpa_string = str(
                        refreshed.get("activation_code") or lpa_string
                    ).strip()
                    iccid = str(refreshed.get("iccid") or iccid).strip()
                    euicc = refreshed
            except TelnaError as exc:
                logger.warning(
                    "Telna euicc refresh failed for %s: %s", order_number, exc
                )

    if not lpa_string:
        raise RuntimeError("Telna work order missing activation_code / LPA")

    qr_code = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=320x320&data={quote(lpa_string)}"
    )
    activation_code = _activation_code_from_lpa(lpa_string)
    smdp = _smdp_from_lpa(lpa_string)

    logger.info(
        "Provisioned Telna eSIM for order %s work_order=%s iccid=%s sku=%s",
        order_number,
        work_order_id or "(none)",
        iccid or "(none)",
        product_id,
    )
    return {
        "activation_code": activation_code,
        "qr_code_url": qr_code,
        "lpa_string": lpa_string,
        "provider": "telna",
        "iccid": iccid,
        "smdp_address": smdp,
        "provider_order_id": work_order_id,
        "provider_sku": product_id,
        "catalog_key": target.catalog_key,
        "raw": {"work_order": work_order, "euicc_profile": euicc},
    }


def _telna_provision(
    order_row: Dict[str, Any], target: FulfillmentTarget
) -> Dict[str, Any]:
    return _run_async(_telna_provision_async(order_row, target))


def resolve_provider(explicit: Optional[str] = None) -> str:
    settings = get_settings()
    provider = (explicit or settings.esim_provider or "mock").strip().lower()
    if provider == "citrus" and not settings.citrus_api_key.strip():
        logger.warning("ESIM_PROVIDER=citrus but CITRUS_API_KEY empty; using mock")
        return "mock"
    if provider == "esimaccess" and not settings.esim_access_access_code.strip():
        logger.warning(
            "ESIM_PROVIDER=esimaccess but ESIM_ACCESS_ACCESS_CODE empty; using mock"
        )
        return "mock"
    if provider == "telna" and not settings.telna_api_token.strip():
        logger.warning("ESIM_PROVIDER=telna but TELNA_API_TOKEN empty; using mock")
        return "mock"
    if provider == "simbase" and not settings.simbase_api_key.strip():
        logger.warning("ESIM_PROVIDER=simbase but SIMBASE_API_KEY empty; using mock")
        return "mock"
    return provider or "mock"


def provision_esim(order_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return QR image URL/data-URI and activation credentials for the order.
    Uses virtual catalog map when present; otherwise global ESIM_PROVIDER.
    """
    # Idempotency: already has LPA/ICCID on the order row
    existing_lpa = str(order_row.get("lpa_string") or "").strip()
    existing_qr = str(order_row.get("qr_code_url") or "").strip()
    if existing_lpa and (existing_qr or order_row.get("activation_code")):
        logger.info(
            "Order %s already has eSIM credentials; skipping re-provision",
            order_row.get("order_number"),
        )
        return {
            "activation_code": str(order_row.get("activation_code") or ""),
            "qr_code_url": existing_qr
            or (
                "https://api.qrserver.com/v1/create-qr-code/"
                f"?size=320x320&data={quote(existing_lpa)}"
            ),
            "lpa_string": existing_lpa,
            "provider": (order_row.get("metadata") or {}).get("fulfillment", {}).get(
                "provider"
            )
            or "existing",
            "iccid": str(order_row.get("iccid") or ""),
            "smdp_address": str(order_row.get("smdp_address") or ""),
        }

    target = resolve_fulfillment_target(order_row)
    try:
        enforce_saudi_access_policy(order_row, target)
    except FulfillmentMapError:
        raise

    if target is not None:
        provider = target.provider
        logger.info(
            "Fulfillment map hit order=%s key=%s provider=%s sku=%s source=%s",
            order_row.get("order_number"),
            target.catalog_key,
            provider,
            target.provider_sku,
            target.source,
        )
    else:
        provider = resolve_provider()

    if provider == "esimaccess":
        if target is None:
            raise FulfillmentMapError(
                "esimaccess selected but no fulfillment map target on order"
            )
        return _esimaccess_provision(order_row, target)
    if provider == "telna":
        if target is None:
            raise FulfillmentMapError(
                "telna selected but no fulfillment map target on order"
            )
        return _telna_provision(order_row, target)
    if provider == "citrus":
        return _citrus_provision(order_row)
    if provider == "simbase":
        raise NotImplementedError(
            "Simbase auto-provision is not wired yet; set ESIM_PROVIDER=citrus or mock"
        )
    return _mock_provision(order_row)
