"""eSIM data top-up (Citrus wallet fund + eSIM Access package stack + Stripe)."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.api import supabase_repository as db
from app.services.esim_usage_sync import resolve_order_provider, sync_order_usage_blocking

logger = logging.getLogger(__name__)

TOPUP_AMOUNTS_USD = [5.0, 10.0, 15.0, 20.0, 30.0]
MIN_TOPUP_USD = 5.0
MAX_TOPUP_USD = 100.0
TOPUP_MARKUP = 1.35  # retail = wholesale * markup
ACCESS_MAX_TOPUPS = 9
BYTES_PER_GB = 1073741824


class TopUpError(Exception):
    """Top-up action failed."""


def topup_retail_cents(wholesale_usd: float) -> int:
    retail = round(float(wholesale_usd) * TOPUP_MARKUP, 2)
    return int(round(retail * 100))


def _metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    meta = row.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _fulfillment(row: Dict[str, Any]) -> Dict[str, Any]:
    meta = _metadata(row)
    fulfillment = meta.get("fulfillment")
    return fulfillment if isinstance(fulfillment, dict) else {}


def _topup_history(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = _metadata(row)
    topups = meta.get("topups")
    if isinstance(topups, dict) and isinstance(topups.get("history"), list):
        return [h for h in topups["history"] if isinstance(h, dict)]
    if isinstance(topups, list):
        return [h for h in topups if isinstance(h, dict)]
    return []


def _esim_tran_no(row: Dict[str, Any]) -> str:
    fulfillment = _fulfillment(row)
    for key in ("esim_tran_no", "esimTranNo", "esim_tranNo"):
        value = fulfillment.get(key)
        if value:
            return str(value).strip()
    meta = _metadata(row)
    for key in ("esim_tran_no", "esimTranNo"):
        value = meta.get(key)
        if value:
            return str(value).strip()
    return ""


def _original_slug(row: Dict[str, Any]) -> str:
    fulfillment = _fulfillment(row)
    for key in ("provider_slug", "slug", "package_slug"):
        value = fulfillment.get(key)
        if value:
            return str(value).strip()
    return ""


def _original_package_code(row: Dict[str, Any]) -> str:
    fulfillment = _fulfillment(row)
    for key in ("provider_sku", "package_code", "packageCode"):
        value = fulfillment.get(key)
        if value:
            return str(value).strip()
    return ""


def _original_period_num(row: Dict[str, Any]) -> Optional[int]:
    fulfillment = _fulfillment(row)
    raw = fulfillment.get("period_num") or fulfillment.get("periodNum")
    try:
        value = int(raw)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _format_data_label(volume_bytes: Optional[int], *, daypass: bool) -> Optional[str]:
    if daypass:
        return "Daily / FUP"
    if volume_bytes is None:
        return None
    try:
        gb = float(volume_bytes) / BYTES_PER_GB
    except (TypeError, ValueError):
        return None
    if gb <= 0:
        return None
    if abs(gb - round(gb)) < 0.05:
        return f"{int(round(gb))} GB"
    return f"{gb:.1f} GB"


def _is_daypass_package(pkg: Dict[str, Any]) -> bool:
    data_type = pkg.get("dataType") if pkg.get("dataType") is not None else pkg.get("data_type")
    try:
        if int(data_type) == 2:
            return True
    except (TypeError, ValueError):
        pass
    slug = str(pkg.get("slug") or "")
    name = str(pkg.get("name") or "")
    support = pkg.get("supportTopUpType")
    try:
        if int(support) == 3:
            return True
    except (TypeError, ValueError):
        pass
    return bool(re.search(r"daily|day.?pass|fup|unlimited", f"{slug} {name}", re.I))


def _package_duration_days(pkg: Dict[str, Any]) -> Optional[int]:
    duration = pkg.get("duration")
    unit = str(pkg.get("durationUnit") or pkg.get("duration_unit") or "DAY").upper()
    try:
        value = int(duration)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if unit.startswith("HOUR"):
        return max(1, int(round(value / 24)))
    return value


def _make_offer_id(slug: str, package_code: str, period_num: Optional[int]) -> str:
    raw = f"{slug}|{package_code}|{period_num or ''}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    base = (slug or package_code or "pkg").replace(" ", "_")[:40]
    if period_num:
        return f"{base}-p{period_num}-{digest}"
    return f"{base}-{digest}"


def normalize_access_topup_package(
    pkg: Dict[str, Any],
    *,
    period_num: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(pkg, dict):
        return None
    slug = str(pkg.get("slug") or "").strip()
    package_code = str(pkg.get("packageCode") or pkg.get("package_code") or "").strip()
    if not slug and not package_code:
        return None

    # supportTopUpType 1 = non-reloadable (when describing a base plan).
    # Listed TOPUP packages are already top-up SKUs; keep them unless explicitly blocked.
    support = pkg.get("supportTopUpType")
    try:
        if support is not None and int(support) == 1 and not slug:
            return None
    except (TypeError, ValueError):
        pass

    price_api = pkg.get("price")
    try:
        wholesale_usd = float(price_api) / 10_000.0 if price_api is not None else None
    except (TypeError, ValueError):
        wholesale_usd = None
    if wholesale_usd is None or wholesale_usd <= 0:
        return None

    daypass = _is_daypass_package(pkg)
    duration_days = _package_duration_days(pkg)
    effective_period = period_num
    if daypass and effective_period is None:
        effective_period = duration_days
    if daypass and (effective_period is None or effective_period <= 0):
        return None

    # Daypass wholesale scales with period when price is per-day base.
    wholesale_for_offer = wholesale_usd
    if daypass and effective_period and duration_days and duration_days > 0:
        # Access daypass list price is typically for the package's listed duration.
        wholesale_for_offer = round(wholesale_usd * (effective_period / duration_days), 4)

    volume = pkg.get("volume")
    try:
        volume_bytes = int(volume) if volume is not None else None
    except (TypeError, ValueError):
        volume_bytes = None

    data_label = _format_data_label(volume_bytes, daypass=daypass)
    name = str(pkg.get("name") or "").strip() or (slug or package_code)
    if daypass and effective_period:
        display_name = f"{name} · +{effective_period} day{'s' if effective_period != 1 else ''}"
    elif data_label and duration_days:
        display_name = f"{data_label} / {duration_days} days"
    else:
        display_name = name

    retail_cents = topup_retail_cents(wholesale_for_offer)
    offer_id = _make_offer_id(slug, package_code, effective_period if daypass else None)

    return {
        "offer_id": offer_id,
        "slug": slug or None,
        "package_code": package_code or None,
        "name": display_name,
        "data_label": data_label,
        "days": effective_period if daypass else duration_days,
        "period_num": effective_period if daypass else None,
        "daypass": daypass,
        "wholesale_usd": wholesale_for_offer,
        "retail_usd": retail_cents / 100.0,
        "retail_cents": retail_cents,
    }


def _daypass_period_choices(row: Dict[str, Any], pkg: Dict[str, Any]) -> List[int]:
    choices: List[int] = []
    original = _original_period_num(row)
    duration = _package_duration_days(pkg)
    for value in (original, duration, 7, 10, 14):
        if value and int(value) > 0 and int(value) not in choices:
            choices.append(int(value))
    return choices[:4] or [7]


async def list_access_topup_offers(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    iccid = str(row.get("iccid") or "").strip()
    if not iccid:
        return []

    from app.services.esim_access import EsimAccessClient, EsimAccessError

    packages: List[Dict[str, Any]] = []
    try:
        async with EsimAccessClient() as client:
            packages = await client.list_packages(package_type="TOPUP", iccid=iccid)
            if not packages:
                slug = _original_slug(row)
                code = _original_package_code(row)
                if slug:
                    packages = await client.list_packages(package_type="TOPUP", slug=slug)
                if not packages and code:
                    packages = await client.list_packages(package_type="TOPUP", package_code=code)
                if not packages and slug:
                    # Last resort: allow topping up with the same base slug.
                    packages = await client.list_packages(slug=slug)
                    packages = [p for p in packages if isinstance(p, dict)]
    except EsimAccessError as exc:
        logger.warning("Access top-up package list failed for %s: %s", row.get("order_number"), exc)
        return []

    offers: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        if _is_daypass_package(pkg):
            for period in _daypass_period_choices(row, pkg):
                offer = normalize_access_topup_package(pkg, period_num=period)
                if offer and offer["offer_id"] not in seen:
                    seen.add(offer["offer_id"])
                    offers.append(offer)
        else:
            offer = normalize_access_topup_package(pkg)
            if offer and offer["offer_id"] not in seen:
                seen.add(offer["offer_id"])
                offers.append(offer)

    offers.sort(key=lambda o: (float(o.get("retail_usd") or 0), str(o.get("name") or "")))
    return offers


def find_access_offer(
    offers: List[Dict[str, Any]],
    *,
    offer_id: Optional[str] = None,
    slug: Optional[str] = None,
    package_code: Optional[str] = None,
    period_num: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if offer_id:
        for offer in offers:
            if offer.get("offer_id") == offer_id:
                return offer
    for offer in offers:
        if slug and offer.get("slug") != slug:
            continue
        if package_code and offer.get("package_code") != package_code:
            continue
        if period_num is not None and offer.get("period_num") != period_num:
            continue
        if slug or package_code:
            return offer
    return None


def normalize_zesimo_topup_package(pkg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map a Zesimo TopupPackage into the shared customer offer shape."""
    if not isinstance(pkg, dict):
        return None

    behaviour = str(pkg.get("topup_behaviour") or "").strip().lower()
    # Self-serve: only accumulating top-ups (never wipe remaining data).
    if behaviour and behaviour != "accumulates":
        return None

    package_id = pkg.get("id")
    try:
        package_id_int = int(package_id) if package_id is not None else None
    except (TypeError, ValueError):
        package_id_int = None
    package_code = str(pkg.get("package_code") or package_id or "").strip()
    if package_id_int is None and not package_code:
        return None

    try:
        wholesale_usd = float(pkg.get("reseller_price"))
    except (TypeError, ValueError):
        wholesale_usd = None
    if wholesale_usd is None or wholesale_usd <= 0:
        return None

    data_gb = pkg.get("data_gb")
    try:
        data_gb_f = float(data_gb) if data_gb is not None else None
    except (TypeError, ValueError):
        data_gb_f = None
    duration_days = None
    try:
        if pkg.get("duration_days") is not None:
            duration_days = int(pkg.get("duration_days"))
    except (TypeError, ValueError):
        duration_days = None

    name = str(pkg.get("name") or "").strip() or f"Package {package_code}"
    if data_gb_f and duration_days:
        data_label = f"{data_gb_f:g} GB"
        display_name = f"{data_label} / {duration_days} days"
    elif data_gb_f:
        data_label = f"{data_gb_f:g} GB"
        display_name = f"{name} · {data_label}"
    else:
        data_label = None
        display_name = name

    retail_cents = topup_retail_cents(wholesale_usd)
    offer_key = str(package_id_int or package_code)
    offer_id = _make_offer_id("zesimo", offer_key, None)

    return {
        "offer_id": offer_id,
        "slug": None,
        "package_code": package_code or None,
        "package_id": package_id_int,
        "name": display_name,
        "data_label": data_label,
        "days": duration_days,
        "period_num": None,
        "daypass": False,
        "wholesale_usd": wholesale_usd,
        "retail_usd": retail_cents / 100.0,
        "retail_cents": retail_cents,
        "topup_behaviour": behaviour or "accumulates",
    }


async def _resolve_zesimo_esim_id(row: Dict[str, Any], client: Any) -> Optional[int]:
    from app.services.zesimo import (
        first_esim_from_order_payload,
        resolve_zesimo_esim_id,
        ZesimoError,
    )

    fulfillment = _fulfillment(row)
    raw = fulfillment.get("raw") if isinstance(fulfillment.get("raw"), dict) else {}
    raw_esim = raw.get("esim") if isinstance(raw.get("esim"), dict) else {}

    esim_id = resolve_zesimo_esim_id(
        fulfillment.get("esim_tran_no"),
        fulfillment.get("provider_esim_id"),
        fulfillment.get("esim_id"),
        raw_esim.get("id"),
        raw_esim.get("esim_tran_no"),
    )

    if esim_id is None:
        iccid = str(row.get("iccid") or "").strip()
        if iccid:
            try:
                matches = await client.list_esims(iccid=iccid)
            except ZesimoError as exc:
                logger.warning("Zesimo list_esims failed for %s: %s", row.get("order_number"), exc)
                matches = []
            for match in matches:
                esim_id = resolve_zesimo_esim_id(match.get("id"), match.get("esim_tran_no"))
                if esim_id is not None:
                    break

    if esim_id is None:
        order_id = str(fulfillment.get("provider_order_id") or "").strip()
        if order_id:
            try:
                payload = await client.get_order(order_id)
                esim = first_esim_from_order_payload(payload)
                esim_id = resolve_zesimo_esim_id(esim.get("id"), esim.get("esim_tran_no"))
            except (ZesimoError, Exception) as exc:
                logger.warning(
                    "Zesimo get_order for esim id failed for %s: %s",
                    row.get("order_number"),
                    exc,
                )

    if esim_id is None:
        return None

    # Persist discovered id for later top-ups / usage sync.
    order_number = str(row.get("order_number") or "")
    if order_number and str(fulfillment.get("esim_tran_no") or "") != str(esim_id):
        db.merge_order_metadata(
            order_number,
            {"fulfillment": {**fulfillment, "esim_tran_no": str(esim_id)}},
        )
    return esim_id


async def list_zesimo_topup_offers(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    from app.services.zesimo import ZesimoClient, ZesimoError

    try:
        async with ZesimoClient() as client:
            esim_id = await _resolve_zesimo_esim_id(row, client)
            if esim_id is None:
                return []
            packages = await client.list_topup_packages(esim_id)
    except ZesimoError as exc:
        logger.warning("Zesimo top-up package list failed for %s: %s", row.get("order_number"), exc)
        return []

    offers: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for pkg in packages:
        offer = normalize_zesimo_topup_package(pkg)
        if offer and offer["offer_id"] not in seen:
            seen.add(offer["offer_id"])
            offers.append(offer)
    offers.sort(key=lambda o: (float(o.get("retail_usd") or 0), str(o.get("name") or "")))
    return offers


def topup_capabilities(row: Dict[str, Any]) -> Dict[str, Any]:
    provider = resolve_order_provider(row)
    iccid = str(row.get("iccid") or "").strip()
    status = str(row.get("status") or "").lower()
    meta = _metadata(row)
    snapshot = meta.get("usage_snapshot") if isinstance(meta.get("usage_snapshot"), dict) else None
    topup_supported = False
    reason = None
    mode = None

    if status in {"refunded", "failed", "pending"}:
        reason = "Order is not active."
    elif not iccid:
        reason = "No ICCID on this order yet."
    elif provider == "citrus":
        topup_supported = status in {"delivered", "active", "suspended"}
        mode = "wallet" if topup_supported else None
    elif provider == "esimaccess":
        if status not in {"delivered", "active"}:
            reason = "Top-up is available after this eSIM is issued and active."
        elif len(_topup_history(row)) >= ACCESS_MAX_TOPUPS:
            reason = "This eSIM has reached the maximum number of top-ups."
        else:
            topup_supported = True
            mode = "access_package"
    elif provider == "zesimo":
        if status not in {"delivered", "active"}:
            reason = "Top-up is available after this eSIM is issued and active."
        else:
            topup_supported = True
            mode = "zesimo_package"
    elif provider == "telna":
        reason = "Telna top-up is not wired yet — contact support."
    else:
        reason = f"Top-up not available for provider '{provider or 'unknown'}'."

    if isinstance(snapshot, dict) and snapshot.get("topup_supported") is False and provider == "citrus":
        topup_supported = True
        mode = "wallet"

    return {
        "supported": topup_supported,
        "provider": provider,
        "mode": mode,
        "iccid": iccid or None,
        "amounts_usd": TOPUP_AMOUNTS_USD if (topup_supported and mode == "wallet") else [],
        "packages": [],
        "min_usd": MIN_TOPUP_USD if (topup_supported and mode == "wallet") else None,
        "max_usd": MAX_TOPUP_USD if (topup_supported and mode == "wallet") else None,
        "reason": reason,
    }


async def topup_capabilities_async(row: Dict[str, Any]) -> Dict[str, Any]:
    caps = topup_capabilities(row)
    mode = caps.get("mode")
    if not caps.get("supported") or mode not in {"access_package", "zesimo_package"}:
        return caps

    if mode == "zesimo_package":
        offers = await list_zesimo_topup_offers(row)
        empty_reason = (
            "No accumulating top-up packages are available for this eSIM right now. "
            "Contact support if you need more data."
        )
    else:
        offers = await list_access_topup_offers(row)
        empty_reason = (
            "No reloadable top-up packages are available for this eSIM right now. "
            "Contact support if you need more data."
        )

    if not offers:
        caps["supported"] = False
        caps["packages"] = []
        caps["reason"] = empty_reason
        return caps

    caps["packages"] = offers
    caps["reason"] = None
    return caps


def _append_topup_history(
    row: Dict[str, Any],
    entry: Dict[str, Any],
) -> None:
    order_number = str(row.get("order_number") or "")
    history = _topup_history(row)
    history.append(entry)
    fulfillment = _fulfillment(row)
    fulfillment = {
        **fulfillment,
        "last_topup_at": entry.get("at"),
        "last_topup_usd": entry.get("fund_usd") or entry.get("wholesale_usd"),
        "last_topup_retail_usd": entry.get("retail_usd"),
    }
    db.merge_order_metadata(
        order_number,
        {
            "topups": {"history": history},
            "fulfillment": fulfillment,
        },
    )


async def fund_citrus_topup(
    row: Dict[str, Any],
    fund_usd: float,
    *,
    source: str = "admin",
    actor: Optional[str] = None,
    stripe_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move wholesale USD onto a Citrus SIM wallet."""
    order_number = str(row.get("order_number") or "")
    iccid = str(row.get("iccid") or "").strip()
    provider = resolve_order_provider(row)

    if provider != "citrus":
        raise TopUpError("Only Citrus PAYG eSIMs support wallet top-up.")
    if not iccid:
        raise TopUpError("Order has no ICCID.")
    if fund_usd < MIN_TOPUP_USD or fund_usd > MAX_TOPUP_USD:
        raise TopUpError(f"Top-up must be between ${MIN_TOPUP_USD} and ${MAX_TOPUP_USD}.")

    from app.services.citrus import CitrusClient, CitrusError

    async with CitrusClient() as client:
        try:
            result = await client.fund_esim(iccid, float(fund_usd))
        except CitrusError as exc:
            raise TopUpError(str(exc)) from exc

        if str(row.get("status") or "") == "suspended":
            try:
                await client.enable_esim(iccid)
                db.get_supabase_client().table("orders").update({"status": "active"}).eq(
                    "order_number", order_number
                ).execute()
            except Exception:
                logger.warning("Could not re-enable Citrus eSIM after top-up for %s", order_number)

    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "provider": "citrus",
        "mode": "wallet",
        "fund_usd": float(fund_usd),
        "source": source,
        "actor": actor,
        "stripe_session_id": stripe_session_id,
        "provider_result": result if isinstance(result, dict) else {"raw": result},
    }
    _append_topup_history(row, entry)

    refreshed = db.get_order_row_by_order_number(order_number) or row
    try:
        sync_order_usage_blocking(refreshed, source="topup")
    except Exception:
        logger.warning("Post top-up usage sync failed for %s", order_number)

    logger.info(
        "Top-up $%s on %s iccid=%s source=%s actor=%s",
        fund_usd,
        order_number,
        iccid,
        source,
        actor,
    )
    return {"ok": True, "order_number": order_number, "fund_usd": fund_usd, "entry": entry}


def fund_citrus_topup_blocking(
    row: Dict[str, Any],
    fund_usd: float,
    **kwargs: Any,
) -> Dict[str, Any]:
    import asyncio

    return asyncio.run(fund_citrus_topup(row, fund_usd, **kwargs))


async def apply_access_topup(
    row: Dict[str, Any],
    offer: Dict[str, Any],
    *,
    source: str = "stripe_checkout",
    actor: Optional[str] = None,
    stripe_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Stack an Access package onto an existing ICCID."""
    order_number = str(row.get("order_number") or "")
    iccid = str(row.get("iccid") or "").strip()
    provider = resolve_order_provider(row)

    if provider != "esimaccess":
        raise TopUpError("Only eSIM Access plans support package top-up.")
    if not iccid:
        raise TopUpError("Order has no ICCID.")
    if len(_topup_history(row)) >= ACCESS_MAX_TOPUPS:
        raise TopUpError("This eSIM has reached the maximum number of top-ups.")

    slug = str(offer.get("slug") or "").strip()
    package_code = str(offer.get("package_code") or "").strip()
    period_num = offer.get("period_num")
    daypass = bool(offer.get("daypass"))
    if daypass and not package_code and not slug:
        raise TopUpError("Daypass top-up is missing package identity.")
    if not daypass and not slug and not package_code:
        raise TopUpError("Top-up package is missing slug/package code.")

    from app.services.esim_access import EsimAccessClient, EsimAccessError, usd_to_api_price

    transaction_id = f"TU-{order_number}-{int(datetime.now(timezone.utc).timestamp())}"
    wholesale_usd = float(offer.get("wholesale_usd") or 0)
    amount_api = usd_to_api_price(wholesale_usd) if wholesale_usd > 0 else None
    esim_tran_no = _esim_tran_no(row)

    async with EsimAccessClient() as client:
        try:
            if daypass:
                result = await client.topup_esim(
                    transaction_id=transaction_id,
                    iccid=iccid,
                    esim_tran_no=esim_tran_no,
                    package_code=package_code or slug,
                    period_num=int(period_num) if period_num else None,
                    amount_api=amount_api,
                )
            else:
                result = await client.topup_esim(
                    transaction_id=transaction_id,
                    iccid=iccid,
                    esim_tran_no=esim_tran_no,
                    slug=slug or None,
                    package_code=package_code if not slug else "",
                    amount_api=amount_api,
                )
        except EsimAccessError as exc:
            raise TopUpError(str(exc)) from exc

    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "provider": "esimaccess",
        "mode": "access_package",
        "offer_id": offer.get("offer_id"),
        "slug": slug or None,
        "package_code": package_code or None,
        "period_num": period_num,
        "wholesale_usd": wholesale_usd,
        "retail_usd": float(offer.get("retail_usd") or 0) or None,
        "source": source,
        "actor": actor,
        "stripe_session_id": stripe_session_id,
        "transaction_id": transaction_id,
        "provider_result": result if isinstance(result, dict) else {"raw": result},
    }
    _append_topup_history(row, entry)

    refreshed = db.get_order_row_by_order_number(order_number) or row
    try:
        sync_order_usage_blocking(refreshed, source="topup")
    except Exception:
        logger.warning("Post Access top-up usage sync failed for %s", order_number)

    logger.info(
        "Access top-up on %s iccid=%s slug=%s period=%s source=%s",
        order_number,
        iccid,
        slug or package_code,
        period_num,
        source,
    )
    return {"ok": True, "order_number": order_number, "offer": offer, "entry": entry}


async def apply_zesimo_topup(
    row: Dict[str, Any],
    offer: Dict[str, Any],
    *,
    source: str = "stripe_checkout",
    actor: Optional[str] = None,
    stripe_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Activate a Zesimo accumulating top-up package on an existing eSIM."""
    from app.services.zesimo import ZesimoClient, ZesimoError

    order_number = str(row.get("order_number") or "")
    iccid = str(row.get("iccid") or "").strip()
    provider = resolve_order_provider(row)

    if provider != "zesimo":
        raise TopUpError("Only Zesimo plans support this package top-up.")
    if not iccid:
        raise TopUpError("Order has no ICCID.")

    package_id = offer.get("package_id")
    package_code = str(offer.get("package_code") or "").strip()
    try:
        package_id_int = int(package_id) if package_id is not None else None
    except (TypeError, ValueError):
        package_id_int = None
    if package_id_int is None and not package_code:
        raise TopUpError("Top-up package is missing package id.")

    wholesale_usd = float(offer.get("wholesale_usd") or 0)

    async with ZesimoClient() as client:
        esim_id = await _resolve_zesimo_esim_id(row, client)
        if esim_id is None:
            raise TopUpError("Could not find this eSIM at Zesimo for top-up.")
        try:
            result = await client.topup_esim(
                esim_id,
                package_id=package_id_int,
                package_code=package_code if package_id_int is None else "",
                replace_existing_plan=False,
            )
        except ZesimoError as exc:
            raise TopUpError(str(exc)) from exc

    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "provider": "zesimo",
        "mode": "zesimo_package",
        "offer_id": offer.get("offer_id"),
        "package_id": package_id_int,
        "package_code": package_code or None,
        "wholesale_usd": wholesale_usd,
        "retail_usd": float(offer.get("retail_usd") or 0) or None,
        "source": source,
        "actor": actor,
        "stripe_session_id": stripe_session_id,
        "esim_id": esim_id,
        "provider_result": result if isinstance(result, dict) else {"raw": result},
    }
    _append_topup_history(row, entry)

    refreshed = db.get_order_row_by_order_number(order_number) or row
    try:
        sync_order_usage_blocking(refreshed, source="topup")
    except Exception:
        logger.warning("Post Zesimo top-up usage sync failed for %s", order_number)

    logger.info(
        "Zesimo top-up on %s iccid=%s esim_id=%s package=%s source=%s",
        order_number,
        iccid,
        esim_id,
        package_id_int or package_code,
        source,
    )
    return {"ok": True, "order_number": order_number, "offer": offer, "entry": entry}


async def resolve_topup_checkout_quote(
    row: Dict[str, Any],
    *,
    fund_usd: Optional[float] = None,
    offer_id: Optional[str] = None,
    package_slug: Optional[str] = None,
    package_code: Optional[str] = None,
    period_num: Optional[int] = None,
) -> Dict[str, Any]:
    """Validate a top-up selection and return Stripe/PayPal charge details."""
    caps = await topup_capabilities_async(row)
    if not caps.get("supported"):
        raise TopUpError(str(caps.get("reason") or "Top-up not available for this eSIM."))

    iccid = str(row.get("iccid") or "").strip()
    if not iccid:
        raise TopUpError("This order has no ICCID yet.")

    order_number = str(row.get("order_number") or "")
    mode = caps.get("mode")

    if mode in {"access_package", "zesimo_package"}:
        offers = list(caps.get("packages") or [])
        if not offers:
            offers = (
                await list_zesimo_topup_offers(row)
                if mode == "zesimo_package"
                else await list_access_topup_offers(row)
            )
        offer = find_access_offer(
            offers,
            offer_id=offer_id,
            slug=package_slug,
            package_code=package_code,
            period_num=period_num,
        )
        if not offer:
            raise TopUpError("Choose a top-up package from the available options.")
        return {
            "mode": mode,
            "topup_provider": "zesimo" if mode == "zesimo_package" else "esimaccess",
            "iccid": iccid,
            "order_number": order_number,
            "offer": offer,
            "offer_id": offer.get("offer_id"),
            "package_slug": offer.get("slug"),
            "package_code": offer.get("package_code") or (
                str(offer.get("package_id")) if offer.get("package_id") is not None else None
            ),
            "period_num": offer.get("period_num"),
            "wholesale_usd": float(offer.get("wholesale_usd") or 0) or None,
            "fund_usd": None,
            "retail_cents": int(offer["retail_cents"]),
            "retail_usd": float(offer["retail_usd"]),
            "display_name": f"eSIM top-up · {order_number} · {offer['name']}",
        }

    if fund_usd is None:
        raise TopUpError("Choose a top-up amount.")

    amount = float(fund_usd)
    allowed = [float(a) for a in (caps.get("amounts_usd") or [])]
    min_usd = float(caps.get("min_usd") or MIN_TOPUP_USD)
    max_usd = float(caps.get("max_usd") or MAX_TOPUP_USD)
    if amount < min_usd or amount > max_usd:
        raise TopUpError(f"Choose a top-up between ${min_usd:.0f} and ${max_usd:.0f}.")
    if allowed and not any(abs(amount - a) < 0.01 for a in allowed):
        raise TopUpError(f"Choose one of: {', '.join(f'${a:.0f}' for a in allowed)}.")

    retail_cents = topup_retail_cents(amount)
    return {
        "mode": mode or "wallet",
        "topup_provider": "citrus",
        "iccid": iccid,
        "order_number": order_number,
        "offer": None,
        "offer_id": None,
        "package_slug": None,
        "package_code": None,
        "period_num": None,
        "wholesale_usd": amount,
        "fund_usd": amount,
        "retail_cents": retail_cents,
        "retail_usd": retail_cents / 100.0,
        "display_name": f"Data top-up · {order_number} · ${amount:.0f} data",
    }


async def process_topup_checkout(
    *,
    order_number: str,
    fund_usd: Optional[float] = None,
    offer_id: Optional[str] = None,
    package_slug: Optional[str] = None,
    package_code: Optional[str] = None,
    period_num: Optional[int] = None,
    topup_provider: Optional[str] = None,
    retail_cents: Optional[int] = None,
    stripe_session_id: Optional[str] = None,
    buyer_email: Optional[str] = None,
) -> Dict[str, Any]:
    row = db.get_order_row_by_order_number(order_number)
    if not row:
        raise TopUpError(f"Order {order_number} not found.")

    caps = topup_capabilities(row)
    if not caps.get("supported"):
        raise TopUpError(str(caps.get("reason") or "Top-up not supported."))

    provider = str(topup_provider or caps.get("provider") or "")
    mode = caps.get("mode")

    if provider == "zesimo" or mode == "zesimo_package":
        offers = await list_zesimo_topup_offers(row)
        offer = find_access_offer(
            offers,
            offer_id=offer_id,
            slug=package_slug,
            package_code=package_code,
            period_num=period_num,
        )
        if not offer and (package_code or offer_id):
            wholesale = None
            if retail_cents:
                wholesale = round((retail_cents / 100.0) / TOPUP_MARKUP, 4)
            pkg_id = None
            try:
                pkg_id = int(package_code) if package_code else None
            except (TypeError, ValueError):
                pkg_id = None
            offer = {
                "offer_id": offer_id or package_code,
                "package_id": pkg_id,
                "package_code": package_code,
                "wholesale_usd": wholesale or 0,
                "retail_usd": (retail_cents / 100.0) if retail_cents else None,
            }
        if not offer:
            raise TopUpError("Top-up package is no longer available.")
        return await apply_zesimo_topup(
            row,
            offer,
            source="stripe_checkout",
            actor=buyer_email,
            stripe_session_id=stripe_session_id,
        )

    if provider == "esimaccess" or mode == "access_package":
        offers = await list_access_topup_offers(row)
        offer = find_access_offer(
            offers,
            offer_id=offer_id,
            slug=package_slug,
            package_code=package_code,
            period_num=period_num,
        )
        if not offer and package_slug:
            # Webhook metadata may be enough even if live list briefly empty.
            wholesale = None
            if retail_cents:
                wholesale = round((retail_cents / 100.0) / TOPUP_MARKUP, 4)
            offer = {
                "offer_id": offer_id or package_slug,
                "slug": package_slug,
                "package_code": package_code,
                "period_num": period_num,
                "daypass": period_num is not None,
                "wholesale_usd": wholesale or 0,
                "retail_usd": (retail_cents / 100.0) if retail_cents else None,
            }
        if not offer:
            raise TopUpError("Top-up package is no longer available.")
        return await apply_access_topup(
            row,
            offer,
            source="stripe_checkout",
            actor=buyer_email,
            stripe_session_id=stripe_session_id,
        )

    if fund_usd is None:
        raise TopUpError("Top-up amount missing.")
    return await fund_citrus_topup(
        row,
        float(fund_usd),
        source="stripe_checkout",
        actor=buyer_email,
        stripe_session_id=stripe_session_id,
    )
