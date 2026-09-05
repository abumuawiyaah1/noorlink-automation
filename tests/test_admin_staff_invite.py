from unittest.mock import patch

import pytest

from app.services.admin_staff_user import (
    AdminStaffUserError,
    ROLE_BLURBS,
    admin_login_url,
    send_staff_welcome_email,
)


def test_admin_login_url_production():
    with patch("app.services.admin_staff_user.get_settings") as mock_settings:
        mock_settings.return_value.admin_public_url = ""
        mock_settings.return_value.environment = "production"
        mock_settings.return_value.app_url = "https://noorlink.co"
        assert admin_login_url() == "https://api.noorlink.co/admin"


def test_role_blurbs_cover_common_roles():
    assert "marketing" in ROLE_BLURBS
    assert "support" in ROLE_BLURBS


@patch("app.services.admin_staff_user.send_email", return_value="msg_123")
@patch("app.services.admin_staff_user.get_settings")
def test_send_staff_welcome_email(mock_settings, mock_send):
    mock_settings.return_value.admin_public_url = ""
    mock_settings.return_value.environment = "production"
    mock_settings.return_value.app_url = "https://noorlink.co"
    mock_settings.return_value.email_logo_url = "https://noorlink.co/images/logo.png"

    msg_id = send_staff_welcome_email(
        to_email="teammate@example.com",
        username="sara",
        password="securepassword12",
        role="marketing",
        display_name="Sara",
    )
    assert msg_id == "msg_123"
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to_email"] == "teammate@example.com"
    assert "sara" in kwargs["text_body"]
    assert "securepassword12" in kwargs["text_body"]
    assert "api.noorlink.co/admin" in kwargs["text_body"]


def test_welcome_email_requires_address():
    with pytest.raises(AdminStaffUserError, match="work email"):
        send_staff_welcome_email(
            to_email="",
            username="sara",
            password="securepassword12",
            role="support",
            display_name="Sara",
        )
