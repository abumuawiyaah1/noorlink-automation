"""
eSIM provisioning adapter.

Providers:
  - mock (default / development)
  - citrus (Citrus Mobile reseller API)
  - esimaccess (eSIM Access / Redtea — Saudi fixed GB)
  - telna (Telna Connect Flex — Caribbean + non-cutover regionals)
  - zesimo (Zesimo reseller — 24-SKU winner cutover)
  - weconnect (WeConnect / Droam Platform API — breakage PAYG)
  - simbase (reserved; not wired for auto-provision yet)

Routing:
  1. plan_fulfillment_map (or static SA seeds) when matched
  2. else global ESIM_PROVIDER
  Saudi enforcement: fixed GB → esimaccess; unlimited 7d/10d may use zesimo
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
    from app.utils.qr_generator import matching_id_from_lpa

    return matching_id_from_lpa(lpa_string)


def _smdp_from_lpa(lpa_string: str) -> str:
    from app.utils.qr_generator import smdp_from_lpa

    return smdp_from_lpa(lpa_string)


def _with_branded_install(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace provider QR chrome with NoorLink-branded QR + one-tap install links.
    Keeps the same LPA payload so the eSIM still installs.
    """
    from app.utils.qr_generator import build_install_artifacts

    lpa = str(result.get("lpa_string") or "").strip()
    if not lpa:
        return result

    settings = get_settings()
    logo = (settings.email_logo_url or "").strip() or None
    artifacts = build_install_artifacts(lpa, logo_url=logo)
    enriched = dict(result)
    enriched["lpa_string"] = artifacts["lpa_string"]
    enriched["qr_code_url"] = artifacts["qr_code_url"]
    enriched["ios_tap_link"] = artifacts["ios_tap_link"]
    enriched["android_tap_link"] = artifacts["android_tap_link"]
    if not str(enriched.get("activation_code") or "").strip():
        enriched["activation_code"] = artifacts["activation_code"]
    if not str(enriched.get("smdp_address") or "").strip():
        enriched["smdp_address"] = artifacts["smdp_address"]
    return enriched


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
    metadata = order_row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    wants_topup = bool(metadata.get("wants_topup") or metadata.get("wantsTopUp"))
    plan_meta = metadata.get("fulfillment_plan") or {}
    if not isinstance(plan_meta, dict):
        plan_meta = {}

    async with CitrusClient() as client:
        payload = await client.provision_esim(
            end_user_reference=order_number,
            label=label[:120] if label else order_number,
        )

        iccid = str(payload.get("iccid") or "").strip()
        # Optional fund when customer asked for top-up-capable SIM.
        if wants_topup and iccid:
            fund_usd = None
            if plan_meta.get("wholesale_cents") is not None:
                fund_usd = float(plan_meta["wholesale_cents"]) / 100.0
            elif order_row.get("price") is not None:
                # Conservative starter fund: 50% of retail, min $5
                fund_usd = max(5.0, round(float(order_row["price"]) * 0.5, 2))
            if fund_usd and fund_usd > 0:
                try:
                    fund_result = await client.fund_esim(iccid, fund_usd)
                    payload = {**payload, "fund": fund_result, "funded_usd": fund_usd}
                except Exception as exc:
                    logger.warning(
                        "Citrus fund_esim failed for %s iccid=%s: %s",
                        order_number,
                        iccid,
                        exc,
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
        "Provisioned Citrus eSIM for order %s iccid=%s topup=%s",
        order_number,
        iccid or "(none)",
        wants_topup,
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


async def _weconnect_provision_async(
    order_row: Dict[str, Any],
    target: FulfillmentTarget,
) -> Dict[str, Any]:
    """
    Purchase a store Prepaid/Daypass eSIM via WeConnect wallet, then read LPA.

    target.provider_sku must be the WeConnect plan UUID.
    """
    from app.services.weconnect import (
        WeConnectClient,
        extract_iccid,
        extract_lpa,
        page_items,
    )

    order_number = str(order_row["order_number"])
    plan_uuid = (target.provider_sku or target.provider_slug or "").strip()
    if not plan_uuid:
        raise RuntimeError("WeConnect map missing provider_sku (plan UUID)")

    async with WeConnectClient() as client:
        existing = await client.list_sims(page=1, page_size=100)
        known = {
            iccid
            for row in page_items(existing, "sim_cards", "sims")
            if (iccid := extract_iccid(row))
        }

        order_payload = await client.purchase_esim_from_wallet(plan_uuid)
        sim = await client.wait_for_purchased_esim(
            known_iccids=known,
            timeout_seconds=120.0,
            poll_interval=2.0,
        )

        if not extract_lpa(sim):
            iccid = extract_iccid(sim)
            if iccid:
                try:
                    await client.activate_sim(iccid)
                except Exception as exc:
                    logger.warning(
                        "WeConnect activate_sim failed order=%s iccid=%s: %s",
                        order_number,
                        iccid,
                        exc,
                    )
                refreshed = await client.find_sim_by_iccid(iccid)
                if refreshed:
                    sim = refreshed

        profile = client.normalize_profile(sim)

    lpa_string = str(profile.get("lpa_string") or "").strip()
    if not lpa_string:
        raise RuntimeError("WeConnect purchase completed but eSIM LPA is missing")

    qr_code = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=320x320&data={quote(lpa_string)}"
    )
    activation_code = _activation_code_from_lpa(lpa_string)
    smdp = _smdp_from_lpa(lpa_string)
    iccid = str(profile.get("iccid") or "").strip()
    provider_order_id = ""
    if isinstance(order_payload, dict):
        order_obj = (order_payload.get("data") or {}).get("order") or {}
        if isinstance(order_obj, dict):
            provider_order_id = str(order_obj.get("uuid") or "")

    logger.info(
        "Provisioned WeConnect eSIM for order %s iccid=%s plan=%s",
        order_number,
        iccid or "(none)",
        plan_uuid,
    )
    return {
        "activation_code": activation_code,
        "qr_code_url": qr_code,
        "lpa_string": lpa_string,
        "provider": "weconnect",
        "iccid": iccid,
        "smdp_address": smdp,
        "provider_order_id": provider_order_id,
        "provider_sku": plan_uuid,
        "catalog_key": target.catalog_key,
        "raw": {"order": order_payload, "sim": sim},
    }


def _weconnect_provision(
    order_row: Dict[str, Any], target: FulfillmentTarget
) -> Dict[str, Any]:
    return _run_async(_weconnect_provision_async(order_row, target))


async def _zesimo_provision_async(
    order_row: Dict[str, Any],
    target: FulfillmentTarget,
) -> Dict[str, Any]:
    from app.services.zesimo import (
        ZesimoClient,
        ZesimoError,
        first_esim_from_order_payload,
    )

    order_number = str(order_row["order_number"])
    package_raw = (target.provider_sku or target.provider_slug or "").strip()
    if not package_raw:
        raise RuntimeError("Zesimo map missing provider_sku (package id)")
    try:
        package_id = int(package_raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Zesimo provider_sku must be numeric package id, got {package_raw!r}"
        ) from exc

    async with ZesimoClient() as client:
        try:
            payload = await client.place_order(
                package_id=package_id,
                quantity=1,
                idempotency_key=order_number,
            )
        except ZesimoError:
            raise

        esim = first_esim_from_order_payload(payload)
        lpa_string = str(esim.get("activation_code") or "").strip()
        iccid = str(esim.get("iccid") or "").strip()
        provider_order_id = ""
        order_obj = payload.get("order") if isinstance(payload, dict) else None
        if isinstance(order_obj, dict):
            provider_order_id = str(order_obj.get("id") or "")

        # Rare: activation_code still null — poll GET /orders/{id}
        if (not lpa_string) and provider_order_id:
            for _ in range(6):
                await asyncio.sleep(1.5)
                refreshed = await client.get_order(provider_order_id)
                try:
                    esim = first_esim_from_order_payload(refreshed)
                except ZesimoError:
                    continue
                lpa_string = str(esim.get("activation_code") or "").strip()
                iccid = str(esim.get("iccid") or iccid).strip()
                if lpa_string:
                    payload = refreshed
                    break

    if not lpa_string:
        raise RuntimeError("Zesimo order missing activation_code / LPA")

    qr_code = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=320x320&data={quote(lpa_string)}"
    )
    activation_code = _activation_code_from_lpa(lpa_string)
    smdp = _smdp_from_lpa(lpa_string)

    logger.info(
        "Provisioned Zesimo eSIM for order %s provider_order=%s iccid=%s sku=%s",
        order_number,
        provider_order_id or "(none)",
        iccid or "(none)",
        package_id,
    )
    return {
        "activation_code": activation_code,
        "qr_code_url": qr_code,
        "lpa_string": lpa_string,
        "provider": "zesimo",
        "iccid": iccid,
        "smdp_address": smdp,
        "provider_order_id": provider_order_id,
        "provider_sku": str(package_id),
        "catalog_key": target.catalog_key,
        "raw": {"order": payload, "esim": esim},
    }


def _zesimo_provision(
    order_row: Dict[str, Any], target: FulfillmentTarget
) -> Dict[str, Any]:
    return _run_async(_zesimo_provision_async(order_row, target))


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
    if provider == "zesimo" and not settings.zesimo_api_key.strip():
        logger.warning("ESIM_PROVIDER=zesimo but ZESIMO_API_KEY empty; using mock")
        return "mock"
    if provider == "weconnect" and (
        not settings.weconnect_email.strip() or not settings.weconnect_password.strip()
    ):
        logger.warning(
            "ESIM_PROVIDER=weconnect but WECONNECT_EMAIL/PASSWORD empty; using mock"
        )
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
    from app.utils.qr_generator import resolve_lpa_from_order_row

    existing_lpa = resolve_lpa_from_order_row(order_row)
    existing_qr = str(order_row.get("qr_code_url") or "").strip()
    if existing_lpa and (existing_qr or order_row.get("activation_code")):
        logger.info(
            "Order %s already has eSIM credentials; skipping re-provision",
            order_row.get("order_number"),
        )
        return _with_branded_install(
            {
                "activation_code": str(order_row.get("activation_code") or ""),
                "qr_code_url": existing_qr,
                "lpa_string": existing_lpa,
                "provider": (order_row.get("metadata") or {}).get("fulfillment", {}).get(
                    "provider"
                )
                or "existing",
                "iccid": str(order_row.get("iccid") or ""),
                "smdp_address": str(order_row.get("smdp_address") or ""),
            }
        )

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
        return _with_branded_install(_esimaccess_provision(order_row, target))
    if provider == "telna":
        if target is None:
            raise FulfillmentMapError(
                "telna selected but no fulfillment map target on order"
            )
        return _with_branded_install(_telna_provision(order_row, target))
    if provider == "zesimo":
        if target is None:
            raise FulfillmentMapError(
                "zesimo selected but no fulfillment map target on order "
                "(provider_sku must be Zesimo package id)"
            )
        return _with_branded_install(_zesimo_provision(order_row, target))
    if provider == "weconnect":
        if target is None:
            raise FulfillmentMapError(
                "weconnect selected but no fulfillment map target on order "
                "(provider_sku must be WeConnect plan UUID)"
            )
        return _with_branded_install(_weconnect_provision(order_row, target))
    if provider == "citrus":
        return _with_branded_install(_citrus_provision(order_row))
    if provider == "simbase":
        raise NotImplementedError(
            "Simbase auto-provision is not wired yet; set ESIM_PROVIDER=citrus or mock"
        )
    return _with_branded_install(_mock_provision(order_row))
