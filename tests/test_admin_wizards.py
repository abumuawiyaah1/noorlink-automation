"""Tests for staff wizard hub and helpers."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.admin.wizard_catalog import STAFF_WIZARDS, wizards_for_role
from app.services.admin_promo_wizard import AdminPromoError, parse_promo_wizard_form
from app.services.admin_support_wizard import (
    AdminSupportWizardError,
    create_customer_help_ticket,
    parse_help_customer_form,
)


def test_wizards_for_admin_sees_all():
    assert len(wizards_for_role("admin")) == len(STAFF_WIZARDS)


def test_wizards_for_support_only_help():
    keys = {wizard.key for wizard in wizards_for_role("support")}
    assert keys == {"help-customer", "fulfill-order", "order-insight"}


def test_wizards_for_marketing_promo_only():
    keys = {wizard.key for wizard in wizards_for_role("marketing")}
    assert keys == {"new-promo", "insider-wizard", "newsletter-admin"}


def test_wizards_for_catalog_plan_and_promo():
    keys = {wizard.key for wizard in wizards_for_role("catalog")}
    assert keys == {"new-promo", "new-custom-plan", "insider-wizard", "newsletter-admin"}


def test_parse_promo_wizard_percent():
    parsed = parse_promo_wizard_form(
        {
            "code": " spring10 ",
            "label": "Spring",
            "discount_type": "percent",
            "percent_off": "15",
            "starts_at": "2026-03-01",
            "ends_at": "2026-04-01",
        }
    )
    assert parsed["code"] == "SPRING10"
    assert parsed["percent_off"] == 15
    assert parsed["amount_off_cents"] is None
    assert parsed["starts_at"].date() == date(2026, 3, 1)


def test_parse_promo_wizard_amount():
    parsed = parse_promo_wizard_form(
        {
            "code": "FIVEOFF",
            "discount_type": "amount",
            "amount_off_cents": "500",
            "starts_at": "2026-03-01",
            "ends_at": "2026-04-01",
        }
    )
    assert parsed["amount_off_cents"] == 500
    assert parsed["percent_off"] is None


def test_parse_help_customer_requires_email():
    with pytest.raises(AdminSupportWizardError, match="valid customer email"):
        parse_help_customer_form({"name": "Jane", "email": "bad", "message": "Help"})


@patch("app.services.admin_support_wizard.dispatch_ticket_created_notifications")
@patch("app.services.admin_support_wizard.create_ticket_from_contact")
def test_create_customer_help_ticket(mock_create, mock_notify):
    mock_create.return_value = {"ticket_number": "TCK-ABC12345", "category": "order_help"}
    result = create_customer_help_ticket(
        form={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "order_number": "nl-xyz",
            "subject": "Order help",
            "message": "Need my QR code again.",
        }
    )
    assert result["ticket_number"] == "TCK-ABC12345"
    assert result["email"] == "jane@example.com"
    mock_create.assert_called_once()
    mock_notify.assert_called_once()


def test_parse_promo_wizard_missing_dates():
    with pytest.raises(AdminPromoError, match="dates are required"):
        parse_promo_wizard_form({"code": "NOPE", "discount_type": "percent", "percent_off": "10"})
