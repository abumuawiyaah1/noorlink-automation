"""Tests for support ticket categories and notifications."""

from app.services.support_categories import (
    get_category_config,
    get_reply_template,
    normalize_support_category,
)


def test_normalize_support_category_from_form_subject():
    assert normalize_support_category("Install / QR code") == "install_qr"
    assert normalize_support_category("Checkout / payment") == "checkout_payment"
    assert normalize_support_category("Refund") == "refund"
    assert normalize_support_category("Something else") == "other"


def test_category_has_reply_templates():
    config = get_category_config("install_qr")
    assert config["reply_eyebrow"] == "Install help"
    assert len(config["templates"]) >= 1


def test_get_reply_template_by_key():
    body = get_reply_template("install_qr", "install_steps")
    assert body is not None
    assert "Wi" in body or "Wi‑Fi" in body
