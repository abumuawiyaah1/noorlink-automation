"""Gift checkout validation and metadata helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.api.schemas import CheckoutSessionRequest


def validate_gift_checkout(body: CheckoutSessionRequest) -> None:
    if not body.is_gift:
        return
    if not body.gift:
        raise HTTPException(status_code=400, detail="Gift recipient details are required.")
    buyer = str(body.email).strip().lower()
    recipient = str(body.gift.recipient_email).strip().lower()
    if buyer == recipient:
        raise HTTPException(
            status_code=400,
            detail="Recipient email must be different from your email.",
        )


def build_gift_metadata(body: CheckoutSessionRequest) -> Optional[Dict[str, Any]]:
    if not body.is_gift or not body.gift:
        return None
    sender = (body.gift.sender_name or "").strip()
    if not sender:
        sender = str(body.email).split("@")[0].replace(".", " ").title()
    message = (body.gift.gift_message or "").strip()
    return {
        "is_gift": True,
        "recipient_email": str(body.gift.recipient_email).strip().lower(),
        "recipient_name": body.gift.recipient_name.strip(),
        "message": message[:280],
        "sender_name": sender[:80],
        "buyer_email": str(body.email).strip().lower(),
    }
