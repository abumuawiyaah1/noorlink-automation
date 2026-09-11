"""Tests for promo share link helpers."""

from __future__ import annotations

from app.services.promo_share import (
    build_promo_share_links,
    build_promo_share_message,
    discount_phrase,
    share_context_for_code,
    whatsapp_share_url,
)


def test_build_promo_share_links_include_code():
    links = build_promo_share_links(code="friend10", app_url="https://noorlink.co")
    assert len(links) >= 3
    assert all("promo=FRIEND10" in row["url"] for row in links)
    assert links[0]["url"].startswith("https://noorlink.co/destinations?")


def test_discount_phrase():
    assert discount_phrase(percent_off=10, amount_off_cents=None) == "10% off"
    assert discount_phrase(percent_off=None, amount_off_cents=500) == "$5 off"


def test_whatsapp_share_url():
    url = whatsapp_share_url(message="Hi — use FRIEND10", phone="")
    assert url.startswith("https://wa.me/?text=")
    assert "FRIEND10" in url


def test_share_context_for_code():
    ctx = share_context_for_code(code="summer10", percent_off=10)
    assert ctx["code"] == "SUMMER10"
    assert ctx["discount_phrase"] == "10% off"
    assert ctx["primary_url"].endswith("/destinations?promo=SUMMER10")
    assert "SUMMER10" in build_promo_share_message(
        code="SUMMER10",
        share_url=ctx["primary_url"],
        percent_off=10,
    )
