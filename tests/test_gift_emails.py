"""Gift fulfillment email smoke tests."""

from unittest.mock import patch

from app.services.email_service import (
    build_fulfillment_email_html,
    send_gift_checkout_acknowledgment,
    send_gift_sent_confirmation_email,
)


def test_gift_fulfillment_email_includes_message():
    html_body = build_fulfillment_email_html(
        order_number="NL-GIFT123",
        country="Turkey",
        package_name="10GB Turkey",
        flag_emoji="🇹🇷",
        qr_code_url="https://example.com/qr.png",
        activation_code="ABC123",
        travel_guide={"highlights": [], "itinerary": [], "maps": []},
        app_url="https://noorlink.co",
        gift_sender_name="Yusuf",
        gift_recipient_name="Amina",
        gift_message="Install before you fly",
    )
    assert "A gift for you" in html_body
    assert "Yusuf" in html_body
    assert "Install before you fly" in html_body
    assert "al-Haramayn guides" not in html_body


def test_pilgrimage_fulfillment_email_includes_guide_links():
    html_body = build_fulfillment_email_html(
        order_number="NL-UMRAH1",
        country="Saudi Arabia",
        package_name="Connected Pilgrim 10GB",
        flag_emoji="🇸🇦",
        qr_code_url="https://example.com/qr.png",
        activation_code="ABC123",
        travel_guide={"highlights": [], "itinerary": [], "maps": []},
        app_url="https://noorlink.co",
    )
    assert "Complimentary gift with your purchase" in html_body
    assert "al-Haramayn guides" in html_body
    assert "noorlink-gift-duas-al-haramayn.pdf" in html_body
    assert "noorlink-gift-orientation-makkah-madinah.pdf" in html_body
    assert "noorlink-gift-places-of-meaning.pdf" in html_body


def test_send_gift_emails_build():
    with patch("app.services.email_service.send_email", return_value="msg_1") as send:
        send_gift_checkout_acknowledgment(
            to_email="buyer@example.com",
            order_number="NL-1",
            country="Turkey",
            package_name="10GB",
            amount=8.95,
            recipient_name="Amina",
            recipient_email="amina@example.com",
        )
        send_gift_sent_confirmation_email(
            to_email="buyer@example.com",
            order_number="NL-1",
            recipient_name="Amina",
            recipient_email="amina@example.com",
            country="Turkey",
            package_name="10GB",
        )
    assert send.call_count == 2
