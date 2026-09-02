"""Tests for shared admin report analytics."""

from types import SimpleNamespace

from app.services.admin_report_core import analyze_orders, compare_periods, traffic_label
from app.services.order_attribution import clean_attribution_payload, stripe_checkout_customer_patch


def _order(**kwargs):
    defaults = {
        "package_name": "Traveler 10GB",
        "country": "Saudi Arabia",
        "amount_cents": 2499,
        "email": "buyer@example.com",
        "metadata_": {
            "fulfillment_plan": {"wholesale_cents": 1150},
            "affiliate": {"code": "MASJID1"},
            "customer": {"billing_country": "US"},
            "attribution": {"utm_source": "facebook", "utm_medium": "paid"},
        },
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_traffic_label_prefers_utm_over_affiliate():
    assert traffic_label(_order()).startswith("UTM:")


def test_analyze_orders_includes_customer_country_and_margin_leaders():
    stats = analyze_orders([_order(), _order(email="other@example.com", amount_cents=999)])
    assert stats["top_customer_countries"][0][0] == "US"
    assert stats["margin_leaders"]
    assert stats["aov_cents"] > 0


def test_compare_periods_delta():
    current = analyze_orders([_order()])
    previous = analyze_orders([])
    deltas = compare_periods(current, previous)
    assert deltas["revenue_delta_pct"] == 100.0


def test_clean_attribution_payload_trims_values():
    payload = clean_attribution_payload(
        {"utm_source": "  facebook ", "utm_medium": "paid", "landing_path": "/destinations"}
    )
    assert payload == {
        "utm_source": "facebook",
        "utm_medium": "paid",
        "landing_path": "/destinations",
    }


def test_stripe_checkout_customer_patch_reads_billing_country():
    session = SimpleNamespace(
        customer_details={"address": {"country": "us"}},
        payment_method_types=["card", "apple_pay"],
    )
    patch = stripe_checkout_customer_patch(session)
    assert patch["customer"]["billing_country"] == "US"
    assert patch["customer"]["payment_method_types"] == ["card", "apple_pay"]
