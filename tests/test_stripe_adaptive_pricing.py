"""Adaptive Pricing: presentment capture + paid verification before eSIM fulfill."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.stripe_webhook import (
    extract_checkout_presentment,
    verify_stripe_paid_amount_for_order,
)


def _session(**kwargs):
    defaults = {
        "id": "cs_test_1",
        "currency": "usd",
        "amount_total": 1999,
        "payment_status": "paid",
        "presentment_details": None,
        "currency_conversion": None,
        "metadata": {
            "settlement_currency": "USD",
            "settlement_amount_cents": "1999",
        },
        "payment_intent": "pi_test_1",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_extract_presentment_from_session_fields():
    session = _session(
        currency="eur",
        amount_total=1850,
        presentment_details={"presentment_currency": "eur", "presentment_amount": 1850},
    )
    out = extract_checkout_presentment(session)
    assert out["stripe_session_id"] == "cs_test_1"
    assert out["presentment_currency"] == "EUR"
    assert out["presentment_amount_cents"] == 1850
    assert out["session_amount_total_cents"] == 1850
    assert out["settlement_currency"] == "USD"
    assert out["settlement_amount_cents"] == 1999


def test_verify_same_currency_must_match():
    order = {"order_number": "NL-1", "amount_cents": 1999, "currency": "USD"}
    event = SimpleNamespace(
        type="checkout.session.completed",
        data=SimpleNamespace(object=_session(amount_total=1999, currency="usd")),
    )
    assert verify_stripe_paid_amount_for_order(order, event) is True

    event_bad = SimpleNamespace(
        type="checkout.session.completed",
        data=SimpleNamespace(object=_session(amount_total=500, currency="usd")),
    )
    assert verify_stripe_paid_amount_for_order(order, event_bad) is False


def test_verify_adaptive_pricing_presentment_still_fulfills():
    order = {"order_number": "NL-2", "amount_cents": 1999, "currency": "USD"}
    session = _session(
        currency="mxn",
        amount_total=34900,
        payment_status="paid",
        payment_intent="pi_mxn",
    )
    event = SimpleNamespace(
        type="checkout.session.completed",
        data=SimpleNamespace(object=session),
    )
    fake_pi = SimpleNamespace(currency="mxn", amount_received=34900, amount=34900)
    with patch("app.api.stripe_webhook.get_settings") as settings, patch(
        "app.api.stripe_webhook.stripe.PaymentIntent.retrieve",
        return_value=fake_pi,
    ):
        settings.return_value = MagicMock(stripe_secret_key="sk_test")
        assert verify_stripe_paid_amount_for_order(order, event) is True


def test_verify_unpaid_session_blocks():
    order = {"order_number": "NL-3", "amount_cents": 1999, "currency": "USD"}
    event = SimpleNamespace(
        type="checkout.session.completed",
        data=SimpleNamespace(
            object=_session(payment_status="unpaid", amount_total=1999)
        ),
    )
    assert verify_stripe_paid_amount_for_order(order, event) is False
