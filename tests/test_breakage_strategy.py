"""Tests for breakage-fulfillment strategy routing."""

from __future__ import annotations

from app.services.breakage_strategy import (
    estimate_breakage_margin,
    fulfillment_mode_for_order,
    is_breakage_eligible,
    is_checkout_blocked,
    resolve_country_policy,
    strategy_summary,
)


def test_saudi_is_access_fixed():
    policy = resolve_country_policy("saudi-arabia")
    assert policy.policy == "access_fixed"
    assert not is_breakage_eligible("saudi-arabia")


def test_turkey_is_breakage_eligible():
    policy = resolve_country_policy("turkey")
    assert policy.policy == "weconnect_breakage"
    assert is_breakage_eligible("turkey")
    assert policy.margin_10gb_100pct > 15


def test_jamaica_is_telna_fixed():
    policy = resolve_country_policy("jamaica")
    assert policy.policy == "telna_fixed"
    assert not is_breakage_eligible("jamaica")


def test_satellite_excluded():
    policy = resolve_country_policy("satellite networks")
    assert policy.policy == "exclude"
    assert is_checkout_blocked("satellite networks")


def test_virtual_bundle_mode_for_turkey_traveler():
    mode = fulfillment_mode_for_order(
        country="turkey",
        data_gb=10,
        validity_days=15,
    )
    assert mode["mode"] == "virtual_bundle"
    assert mode["provider_preference"] == ["weconnect"]
    assert mode["allowance_mb"] == 10240


def test_topup_mode_prefers_weconnect():
    mode = fulfillment_mode_for_order(
        country="france",
        data_gb=10,
        validity_days=15,
        wants_topup=True,
    )
    assert mode["mode"] == "payg_topup"
    assert "weconnect" in mode["provider_preference"]


def test_breakage_margin_improves_at_lower_usage():
    full = estimate_breakage_margin(
        country="turkey",
        data_gb=10,
        retail_usd=29.99,
        usage_pct=1.0,
    )
    half = estimate_breakage_margin(
        country="turkey",
        data_gb=10,
        retail_usd=29.99,
        usage_pct=0.5,
    )
    assert half["margin_usd"] > full["margin_usd"]


def test_strategy_summary_has_policy_counts():
    summary = strategy_summary()
    assert summary["country_count"] == 180
    assert summary["policy_counts"]["weconnect_breakage"] >= 80
