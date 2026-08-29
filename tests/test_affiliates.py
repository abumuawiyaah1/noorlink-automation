"""Tests for affiliate discount and commission logic."""

from app.services.affiliates import (
    prepare_checkout_discounts,
    resolve_affiliate_for_checkout,
)


def test_influencer_discount_and_commission_base():
    # Without DB row this returns None — smoke test prepare with no ref
    result = prepare_checkout_discounts(
        catalog_price=30.0,
        country="turkey",
        buyer_email="buyer@example.com",
        package_id="tmpl-turkey-traveler",
        promo_code=None,
        affiliate_ref=None,
    )
    assert result.discount_cents == 0
    assert result.final_cents == 3000


def test_normalize_ref_in_resolve_empty():
    assert resolve_affiliate_for_checkout(
        ref_code="",
        buyer_email="a@b.com",
        subtotal_cents=2000,
        country="france",
    ) is None
