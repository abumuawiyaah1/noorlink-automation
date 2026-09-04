"""Branded QR + one-tap install link helpers."""

from __future__ import annotations

from unittest.mock import patch

from app.services.email_service import build_fulfillment_email_html
from app.utils.qr_generator import (
    android_tap_link,
    branded_qr_image_url,
    build_install_artifacts,
    generate_branded_qr_png_bytes,
    ios_tap_link,
    matching_id_from_lpa,
)


LPA = "LPA:1$smdp.example.com$MATCHING123"


def test_matching_id_and_tap_links():
    assert matching_id_from_lpa(LPA) == "MATCHING123"
    assert ios_tap_link(LPA).startswith(
        "https://esimsetup.apple.com/esim_qrcode_provisioning?carddata="
    )
    assert "MATCHING123" in ios_tap_link(LPA)
    assert android_tap_link(LPA).startswith(
        "https://esimsetup.android.com/esim_qrcode_provisioning?carddata="
    )


def test_branded_qr_url_includes_logo_and_teal():
    url = branded_qr_image_url(LPA, logo_url="https://noorlink.co/images/logo.png")
    assert url.startswith("https://quickchart.io/qr?")
    assert "centerImageUrl=" in url
    assert "ecLevel=H" in url
    assert "0F3D3E" in url
    assert "noorlink.co" in url


def test_build_install_artifacts_bundle():
    arts = build_install_artifacts(LPA)
    assert arts["lpa_string"] == LPA
    assert arts["activation_code"] == "MATCHING123"
    assert arts["ios_tap_link"]
    assert arts["android_tap_link"]
    assert "quickchart.io" in arts["qr_code_url"]


@patch("app.utils.qr_generator._load_logo_image", return_value=None)
def test_generate_branded_qr_png_without_logo(_mock_logo):
    png = generate_branded_qr_png_bytes(LPA)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_fulfillment_email_includes_tap_links_and_branded_qr():
    html_body = build_fulfillment_email_html(
        order_number="NL-INSTALL1",
        country="France",
        package_name="Europe 10GB",
        flag_emoji="🇫🇷",
        qr_code_url="https://example.com/old-provider.png",
        activation_code="MATCHING123",
        travel_guide={"highlights": [], "itinerary": [], "maps": []},
        app_url="https://noorlink.co",
        lpa_string=LPA,
    )
    assert "Install on iPhone" in html_body
    assert "Install on Android" in html_body
    assert "quickchart.io" in html_body
    assert "esimsetup.apple.com" in html_body
    assert "esimsetup.android.com" in html_body
    assert LPA in html_body
    assert "example.com/old-provider" not in html_body
