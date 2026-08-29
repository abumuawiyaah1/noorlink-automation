"""Gift checkout validation tests."""

import pytest
from fastapi import HTTPException

from app.services.gift_orders import build_gift_metadata, validate_gift_checkout
from app.api.schemas import CheckoutSessionRequest, GiftCheckoutDetails


def test_validate_gift_requires_recipient():
    body = CheckoutSessionRequest(
        country="Turkey",
        price=8.95,
        email="buyer@example.com",
        packageId="pkg-1",
        isGift=True,
    )
    with pytest.raises(HTTPException) as exc:
        validate_gift_checkout(body)
    assert exc.value.status_code == 400


def test_validate_gift_blocks_same_email():
    body = CheckoutSessionRequest(
        country="Turkey",
        price=8.95,
        email="same@example.com",
        packageId="pkg-1",
        isGift=True,
        gift=GiftCheckoutDetails(
            recipientEmail="same@example.com",
            recipientName="Friend",
        ),
    )
    with pytest.raises(HTTPException) as exc:
        validate_gift_checkout(body)
    assert "different" in str(exc.value.detail).lower()


def test_build_gift_metadata_trims_message():
    body = CheckoutSessionRequest(
        country="Turkey",
        price=8.95,
        email="buyer@example.com",
        packageId="pkg-1",
        isGift=True,
        gift=GiftCheckoutDetails(
            recipientEmail="friend@example.com",
            recipientName="Amina",
            giftMessage="  Safe travels!  ",
            senderName="Yusuf",
        ),
    )
    meta = build_gift_metadata(body)
    assert meta is not None
    assert meta["is_gift"] is True
    assert meta["recipient_email"] == "friend@example.com"
    assert meta["message"] == "Safe travels!"
    assert meta["sender_name"] == "Yusuf"
