"""Tests for admin promo code helpers."""

from datetime import datetime, timezone

import pytest

from app.services.admin_promo_codes import (
    AdminPromoError,
    apply_promo_approval_rules,
    days_remaining,
    extend_promo_end,
    promo_status_label,
    validate_promo_payload,
)
from app.services.promo_codes import PromoCodeError, requires_admin_approval, validate_promo_row


def test_validate_percent_promo():
    data = validate_promo_payload(
        {
            "code": " summer10 ",
            "label": "Summer",
            "percent_off": 10,
            "amount_off_cents": None,
            "starts_at": "2026-01-01T00:00:00+00:00",
            "ends_at": "2026-12-31T23:59:59+00:00",
            "min_order_cents": 0,
        },
        is_create=True,
    )
    assert data["code"] == "SUMMER10"
    assert data["percent_off"] == 10
    assert data["amount_off_cents"] is None


def test_validate_rejects_both_discount_types():
    with pytest.raises(AdminPromoError, match="either percent"):
        validate_promo_payload(
            {
                "code": "BAD",
                "percent_off": 10,
                "amount_off_cents": 500,
                "starts_at": "2026-01-01T00:00:00+00:00",
                "ends_at": "2026-12-31T23:59:59+00:00",
            },
            is_create=True,
        )


def test_promo_status_active():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    label = promo_status_label(
        is_active=True,
        starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        now=now,
    )
    assert label == "Active"


def test_extend_promo_end_adds_days():
    class Promo:
        def __init__(self):
            self.ends_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            self.is_active = False

    promo = Promo()
    new_end = extend_promo_end(promo, days=7)
    assert promo.is_active is True
    assert new_end > datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_days_remaining():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert days_remaining(datetime(2026, 6, 8, tzinfo=timezone.utc), now=now) == 7


def test_apply_approval_rules_auto_approves_low_discount():
    validated = {"percent_off": 15}
    apply_promo_approval_rules(
        validated,
        is_create=True,
        editor_is_admin=False,
        editor_username="marketing",
    )
    assert validated["admin_approved"] is True


def test_apply_approval_rules_pending_for_high_discount_non_admin():
    validated = {"percent_off": 30}
    apply_promo_approval_rules(
        validated,
        is_create=True,
        editor_is_admin=False,
        editor_username="marketing",
    )
    assert validated["admin_approved"] is False


def test_apply_approval_rules_admin_auto_approves_high_discount():
    validated = {"percent_off": 30}
    apply_promo_approval_rules(
        validated,
        is_create=True,
        editor_is_admin=True,
        editor_username="admin",
    )
    assert validated["admin_approved"] is True
    assert validated["admin_approved_by"] == "admin"


def test_validate_promo_row_rejects_unapproved_high_discount():
    row = {
        "code": "BIG30",
        "percent_off": 30,
        "is_active": True,
        "admin_approved": False,
        "starts_at": "2026-01-01T00:00:00+00:00",
        "ends_at": "2026-12-31T23:59:59+00:00",
        "redemption_count": 0,
        "min_order_cents": 0,
    }
    with pytest.raises(PromoCodeError, match="pending admin approval"):
        validate_promo_row(row, subtotal_cents=2000)
