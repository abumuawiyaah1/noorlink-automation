"""Tests for admin complimentary eSIM grants."""

from app.services.admin_complimentary_esim import COMPLIMENTARY_REASONS


def test_complimentary_reasons_include_staff():
    assert "staff" in COMPLIMENTARY_REASONS
    assert COMPLIMENTARY_REASONS["staff"] == "Staff member"


def test_complimentary_reasons_cover_partner_and_goodwill():
    assert "partner" in COMPLIMENTARY_REASONS
    assert "goodwill" in COMPLIMENTARY_REASONS
    assert "qa_test" in COMPLIMENTARY_REASONS
