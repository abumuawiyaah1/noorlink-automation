"""Admin order actions (resend eSIM email)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.config import get_settings
from app.services.email_service import (
    EmailDeliveryError,
    build_fulfillment_email_html,
    send_fulfillment_email,
)

logger = logging.getLogger(__name__)


class AdminOrderError(Exception):
    """Admin order action failed."""


def resend_order_esim_email(order_row: Dict[str, Any]) -> str:
    """
    Resend QR / activation delivery email for a fulfilled order.
    Returns Resend message id.
    """
    status = str(order_row.get("status") or "").lower()
    if status not in {"delivered", "active"}:
        raise AdminOrderError("Order must be delivered or active to resend the eSIM email.")

    qr_code_url = (order_row.get("qr_code_url") or "").strip()
    activation_code = (order_row.get("activation_code") or "").strip()
    if not qr_code_url or not activation_code:
        raise AdminOrderError("Order has no QR code or activation code yet.")

    order_number = str(order_row.get("order_number") or "")
    metadata = order_row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    travel_guide = metadata.get("travel_assistant") or {}
    if not isinstance(travel_guide, dict):
        travel_guide = {}

    fulfillment = metadata.get("fulfillment") if isinstance(metadata.get("fulfillment"), dict) else {}
    from app.utils.qr_generator import resolve_lpa_from_order_row

    lpa_string = resolve_lpa_from_order_row(order_row)
    ios_tap_link = str(fulfillment.get("ios_tap_link") or "")
    android_tap_link = str(fulfillment.get("android_tap_link") or "")

    gift = metadata.get("gift")
    is_gift = isinstance(gift, dict) and bool(gift.get("is_gift"))
    recipient_email = (
        str(gift.get("recipient_email") or "").strip().lower()
        if is_gift
        else str(order_row.get("email") or "").strip().lower()
    )
    if not recipient_email:
        raise AdminOrderError("No recipient email on this order.")

    settings = get_settings()
    country = order_row.get("country") or "your destination"
    flag = order_row.get("flag_emoji")
    package_name = order_row.get("package_name") or "Travel eSIM"

    subject = (
        f"A gift for you — {country} eSIM"
        if is_gift
        else f"{country} eSIM delivered — {order_number}"
    )

    html_body = build_fulfillment_email_html(
        order_number=order_number,
        country=country,
        package_name=package_name,
        flag_emoji=flag,
        qr_code_url=qr_code_url,
        activation_code=activation_code,
        travel_guide=travel_guide,
        app_url=settings.app_url,
        lpa_string=lpa_string,
        ios_tap_link=ios_tap_link,
        android_tap_link=android_tap_link,
        gift_sender_name=str(gift.get("sender_name") or "A friend") if is_gift else None,
        gift_recipient_name=str(gift.get("recipient_name") or "") if is_gift else None,
        gift_message=str(gift.get("message") or "") if is_gift else None,
    )

    try:
        message_id = send_fulfillment_email(
            to_email=recipient_email,
            subject=subject,
            html_body=html_body,
        )
    except EmailDeliveryError as exc:
        logger.error("Admin resend failed for %s: %s", order_number, exc)
        raise AdminOrderError(str(exc)) from exc

    logger.info("Admin resent eSIM email for %s to %s", order_number, recipient_email)
    return message_id
