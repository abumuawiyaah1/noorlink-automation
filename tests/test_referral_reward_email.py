"""Referral reward email HTML smoke test."""

from unittest.mock import patch

from app.services.email_service import send_referral_reward_email


def test_send_referral_reward_email_builds_html():
    with patch("app.services.email_service.send_email", return_value="msg_123") as send:
        msg_id = send_referral_reward_email(
            to_email="buyer@example.com",
            reward_code="REWARD-NL-ABC-1234",
            friend_order_number="NL-TEST1234",
        )
    assert msg_id == "msg_123"
    send.assert_called_once()
    html_body = send.call_args.kwargs["html_body"]
    assert "REWARD-NL-ABC-1234" in html_body
    assert "Browse destinations" in html_body
    assert "/destinations" in html_body
