"""PayPal local-currency charge helpers (CAD/EUR/GBP/MXN)."""

from __future__ import annotations

from app.api.paypal_checkout import build_paypal_charge, verify_paypal_capture_amount
from app.services.fx_rates import resolve_paypal_charge_currency


def test_resolve_paypal_charge_currency():
    assert resolve_paypal_charge_currency("eur") == "EUR"
    assert resolve_paypal_charge_currency("GBP") == "GBP"
    assert resolve_paypal_charge_currency("cad") == "CAD"
    assert resolve_paypal_charge_currency("MXN") == "MXN"
    assert resolve_paypal_charge_currency("SAR") == "USD"
    assert resolve_paypal_charge_currency(None) == "USD"


def test_build_paypal_charge_eur():
    charge = build_paypal_charge(amount_usd=20.0, preferred_currency="EUR")
    assert charge["settlement_currency"] == "USD"
    assert charge["settlement_amount"] == 20.0
    assert charge["presentment_currency"] == "EUR"
    assert charge["presentment_amount"] > 0
    assert charge["presentment_amount"] != 20.0


def test_build_paypal_charge_unsupported_falls_back_usd():
    charge = build_paypal_charge(amount_usd=20.0, preferred_currency="SAR")
    assert charge["presentment_currency"] == "USD"
    assert charge["presentment_amount"] == 20.0


def test_verify_presentment_match():
    assert (
        verify_paypal_capture_amount(
            expected_presentment_amount=27.2,
            expected_presentment_currency="CAD",
            received_value="27.20",
            received_currency="CAD",
            settlement_amount_usd=20.0,
        )
        is True
    )


def test_verify_presentment_mismatch_blocks():
    assert (
        verify_paypal_capture_amount(
            expected_presentment_amount=27.2,
            expected_presentment_currency="CAD",
            received_value="1.00",
            received_currency="CAD",
            settlement_amount_usd=20.0,
        )
        is False
    )


def test_verify_usd_legacy():
    assert (
        verify_paypal_capture_amount(
            expected_presentment_amount=None,
            expected_presentment_currency=None,
            received_value="20.00",
            received_currency="USD",
            settlement_amount_usd=20.0,
        )
        is True
    )
