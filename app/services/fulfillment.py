"""
Post-payment fulfillment orchestration.

Runs after Stripe marks an order paid: eSIM credentials, travel assistant, delivered status, email.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.email_service import (
    EmailDeliveryError,
    build_fulfillment_email_html,
    send_fulfillment_email,
)
from app.services.esim_provision import provision_esim
from app.services.breakage_allowance import (
    prepare_allowance_record,
    should_create_allowance,
)
from app.services.fulfillment_map import (
    FulfillmentMapError,
    enforce_saudi_access_policy,
    resolve_fulfillment_target,
)
from app.services.travel_assistant_service import enrich_order_with_travel_assistant
from app.services.ops_alerts import notify_fulfillment_failure

logger = logging.getLogger(__name__)


class FulfillmentError(Exception):
    """Fulfillment pipeline failed."""


def _notify_failure(order_row: Dict[str, Any], error: str, *, context: str) -> None:
    try:
        notify_fulfillment_failure(
            order_number=str(order_row.get("order_number") or ""),
            email=str(order_row.get("email") or ""),
            country=str(order_row.get("country") or ""),
            package_name=str(order_row.get("package_name") or "Travel eSIM"),
            error=error,
            context=context,
            order_status=str(order_row.get("status") or "paid"),
        )
    except Exception:
        logger.exception(
            "Ops alert failed for order %s", order_row.get("order_number")
        )


def _validity_days_from_order_row(order_row: Dict[str, Any]) -> Optional[int]:
    metadata = order_row.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("validity_days") or metadata.get("duration_days")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    plan = metadata.get("fulfillment_plan")
    if isinstance(plan, dict) and plan.get("validity_days") is not None:
        try:
            return int(plan["validity_days"])
        except (TypeError, ValueError):
            pass
    return None


def _maybe_create_breakage_allowance(
    order_row: Dict[str, Any],
    *,
    esim: Dict[str, Any],
) -> None:
    """Create virtual-bundle ledger row when country policy is weconnect_breakage."""
    data_gb = order_row.get("data_total_gb")
    metadata = order_row.get("metadata") or {}
    validity_days = _validity_days_from_order_row(order_row)
    wants_topup = bool(metadata.get("wants_topup") or metadata.get("wantsTopUp"))

    if not should_create_allowance(
        country=str(order_row.get("country") or ""),
        data_gb=float(data_gb) if data_gb is not None else None,
        validity_days=int(validity_days) if validity_days is not None else None,
        wants_topup=wants_topup,
    ):
        return

    if db.get_breakage_allowance_by_order_id(str(order_row["id"])):
        return

    retail_usd = float(order_row.get("amount_cents") or 0) / 100.0
    record = prepare_allowance_record(
        order_id=str(order_row["id"]),
        order_number=str(order_row["order_number"]),
        country=str(order_row.get("country") or ""),
        data_gb=float(data_gb),
        validity_days=int(validity_days),
        retail_usd=retail_usd,
        plan_key=str(metadata.get("plan_key") or "traveler"),
        provider_profile_id=esim.get("iccid"),
    )
    try:
        db.create_breakage_allowance(record)
        logger.info(
            "Breakage allowance created for %s (%s MB)",
            order_row["order_number"],
            record["allowance_mb"],
        )
    except db.SupabaseRepositoryError as exc:
        # Non-fatal until migration applied on production Supabase
        logger.warning(
            "Breakage allowance not persisted for %s: %s",
            order_row["order_number"],
            exc,
        )


def fulfill_paid_order(order_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full post-paid loop for a single order row (status should be paid or pending).
    """
    order_number = order_row["order_number"]
    if order_row.get("status") == "delivered":
        logger.info("Order %s already delivered; skipping fulfillment", order_number)
        return order_row

    # Restriction: Saudi must be mapped to eSIM Access before we spend wallet
    try:
        target = resolve_fulfillment_target(order_row)
        enforce_saudi_access_policy(order_row, target)
    except FulfillmentMapError as exc:
        logger.error("Fulfillment map policy blocked %s: %s", order_number, exc)
        db.merge_order_metadata(
            order_number,
            {"fulfillment": {"error": str(exc), "blocked": True}},
        )
        _notify_failure(order_row, str(exc), context="fulfillment_map_blocked")
        raise FulfillmentError(str(exc)) from exc

    try:
        esim = provision_esim(order_row)
    except FulfillmentMapError as exc:
        _notify_failure(order_row, str(exc), context="provision_map")
        raise FulfillmentError(str(exc)) from exc
    except Exception as exc:
        # Surface provider wallet / API failures as fulfillment errors
        name = type(exc).__name__
        if "Insufficient" in name or "EsimAccess" in name or "Citrus" in name:
            logger.error("Provider fulfillment failed for %s: %s", order_number, exc)
            db.merge_order_metadata(
                order_number,
                {"fulfillment": {"error": str(exc), "provider_error": name}},
            )
            _notify_failure(order_row, str(exc), context=f"provider:{name}")
            raise FulfillmentError(str(exc)) from exc
        raise
    travel_guide = enrich_order_with_travel_assistant(order_row)

    _maybe_create_breakage_allowance(order_row, esim=esim)

    metadata_patch = {
        "fulfillment": {
            "provider": esim.get("provider"),
            "lpa_string": esim.get("lpa_string"),
            "travel_assistant_included": True,
            "iccid": esim.get("iccid"),
            "provider_order_id": esim.get("provider_order_id"),
            "provider_sku": esim.get("provider_sku"),
            "catalog_key": esim.get("catalog_key"),
            "esim_tran_no": esim.get("esim_tran_no"),
        },
        "travel_assistant": travel_guide,
    }

    if esim.get("iccid"):
        try:
            db.attach_simbase_profile(
                order_number,
                iccid=str(esim["iccid"]),
                smdp_address=str(esim.get("smdp_address") or ""),
                activation_code=str(esim.get("activation_code") or ""),
                lpa_string=str(esim.get("lpa_string") or ""),
                plan_name=order_row.get("package_name"),
            )
        except db.SupabaseRepositoryError:
            logger.exception(
                "Failed to persist provider profile fields for %s", order_number
            )

    delivered_row = db.mark_order_delivered(
        order_number,
        qr_code_url=esim["qr_code_url"],
        activation_code=esim["activation_code"],
        metadata_patch=metadata_patch,
    )

    settings = get_settings()
    flag = delivered_row.get("flag_emoji")
    country = delivered_row.get("country") or "your destination"
    subject = f"{country} eSIM delivered — {order_number}"

    html_body = build_fulfillment_email_html(
        order_number=order_number,
        country=country,
        package_name=delivered_row.get("package_name") or "Travel eSIM",
        flag_emoji=flag,
        qr_code_url=esim["qr_code_url"],
        activation_code=esim["activation_code"],
        travel_guide=travel_guide,
        app_url=settings.app_url,
    )

    try:
        send_fulfillment_email(
            to_email=str(delivered_row["email"]),
            subject=subject,
            html_body=html_body,
        )
    except EmailDeliveryError as exc:
        logger.error(
            "Order %s delivered in DB but email failed: %s",
            order_number,
            exc,
        )
        db.merge_order_metadata(
            order_number,
            {"fulfillment": {**metadata_patch.get("fulfillment", {}), "email_error": str(exc)}},
        )
        _notify_failure(order_row, str(exc), context="fulfillment_email")
        raise FulfillmentError(f"Email failed for {order_number}") from exc

    db.merge_order_metadata(
        order_number,
        {"fulfillment": {**metadata_patch.get("fulfillment", {}), "email_sent": True}},
    )

    logger.info("Fulfillment complete for order %s", order_number)
    return delivered_row


def process_paid_order(
    *,
    order_number: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
    stripe_payment_intent_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Mark paid (from webhook) then run fulfillment. Returns final order row.
    """
    paid_row = db.mark_order_paid(
        order_number=order_number,
        stripe_checkout_session_id=stripe_checkout_session_id,
        stripe_payment_intent_id=stripe_payment_intent_id,
    )
    if not paid_row:
        logger.warning(
            "No order found for payment (order_number=%s, session=%s)",
            order_number,
            stripe_checkout_session_id,
        )
        return None

    metadata = paid_row.get("metadata") or {}
    promo = metadata.get("promo") if isinstance(metadata, dict) else None
    if isinstance(promo, dict) and promo.get("code"):
        db.increment_promo_redemption(str(promo["code"]))

    try:
        return fulfill_paid_order(paid_row)
    except FulfillmentError:
        raise
    except db.SupabaseRepositoryError as exc:
        raise FulfillmentError(str(exc)) from exc
