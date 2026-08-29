"""Tests for next-wave recommendations 7–16."""

from unittest.mock import patch

import pytest
from app.services.admin_help_playbooks import search_playbooks
from app.services.admin_promo_insights import build_promo_performance
from app.services.affiliate_portal import AffiliatePortalError, request_affiliate_payout
from app.services.api_rate_limit import check_rate_limit, reset_rate_limit_for_tests
from app.services.resend_events import handle_resend_email_event
from app.services.stripe_mode import stripe_mode_info
from app.services.support_language import detect_ticket_language, language_label


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_rate_limit_for_tests()
    yield
    reset_rate_limit_for_tests()


def test_stripe_mode_test():
    with patch("app.services.stripe_mode.get_settings") as mock_settings:
        mock_settings.return_value.stripe_secret_key = "sk_test_abc"
        info = stripe_mode_info()
    assert info["mode"] == "test"
    assert info["warning"]


def test_stripe_mode_live():
    with patch("app.services.stripe_mode.get_settings") as mock_settings:
        mock_settings.return_value.stripe_secret_key = "sk_live_abc"
        info = stripe_mode_info()
    assert info["mode"] == "live"
    assert info["warning"] is None


@patch("app.services.ops_alerts.notify_email_complaint")
@patch("app.services.resend_events.log_email_delivery")
@patch("app.services.resend_events.db.unsubscribe_newsletter_subscriber", return_value=True)
def test_complaint_triggers_ops_alert(mock_unsub, mock_log, mock_alert):
    handle_resend_email_event(
        event_type="email.complained",
        data={"to": "spam@example.com", "subject": "Insider"},
    )
    mock_alert.assert_called_once()
    assert mock_alert.call_args.kwargs["recipient"] == "spam@example.com"


def test_rate_limit_blocks_after_max():
    for _ in range(5):
        allowed, _ = check_rate_limit("test-key", max_calls=5, window_seconds=60)
        assert allowed
    allowed, retry = check_rate_limit("test-key", max_calls=5, window_seconds=60)
    assert not allowed
    assert retry >= 1


def test_detect_arabic_language():
    assert detect_ticket_language(message="مرحبا أحتاج مساعدة في الطلب") == "ar"


def test_detect_english_default():
    assert detect_ticket_language(message="Hello I need help with my order") == "en"


def test_language_label():
    assert language_label("ar") == "Arabic"


def test_role_filtered_playbooks():
    support = search_playbooks("", role="support")
    marketing = search_playbooks("", role="marketing")
    support_ids = {p.id for p in support}
    marketing_ids = {p.id for p in marketing}
    assert "onboarding-support" in support_ids
    assert "onboarding-marketing" in marketing_ids
    assert "onboarding-marketing" not in support_ids
    assert "affiliate-payout" not in support_ids


def test_promo_attribution_chart_structure():
    with patch("app.services.admin_promo_insights.get_session_factory") as mock_factory:
        mock_factory.return_value = None
        result = build_promo_performance(days=30)
    assert "attribution_chart" in result
    assert "insider_attribution" in result


@patch("app.services.affiliate_portal.get_affiliate_dashboard")
@patch("app.services.ops_alerts.notify_affiliate_payout_request")
@patch("app.services.ops_event_log.log_ops_event")
@patch("app.services.affiliate_payout_requests.create_payout_request")
def test_affiliate_payout_request(mock_create, mock_log, mock_notify, mock_dashboard):
    mock_dashboard.return_value = {
        "code": "PARTNER1",
        "display_name": "Partner",
        "pays_cash": True,
        "ready_for_payout": True,
        "approved_balance_cents": 5000,
        "payout_minimum_cents": 2500,
    }
    mock_create.return_value = {"id": "req-1", "status": "pending", "amount_cents": 5000, "wait_hours": 72}
    with patch("app.services.affiliate_portal._affiliate_row", return_value={"id": "aff-1", "contact_email": "p@x.com"}):
        result = request_affiliate_payout(code="PARTNER1", email="p@x.com")
    assert result["code"] == "PARTNER1"
    assert result["request_id"] == "req-1"
    mock_create.assert_called_once()
    mock_notify.assert_called_once()


@patch("app.services.affiliate_portal.get_affiliate_dashboard")
def test_affiliate_payout_request_below_minimum(mock_dashboard):
    mock_dashboard.return_value = {
        "code": "PARTNER1",
        "pays_cash": True,
        "ready_for_payout": False,
        "approved_balance_cents": 100,
        "payout_minimum_cents": 2500,
    }
    with pytest.raises(AffiliatePortalError):
        request_affiliate_payout(code="PARTNER1", email="p@x.com")


def test_affiliate_auto_payout_strict_rules():
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.db.models import Affiliate, AffiliatePayoutRequest
    from app.services.affiliate_payout_requests import (
        AffiliatePayoutRequestError,
        evaluate_strict_auto_approve,
    )

    aff = Affiliate(
        id=uuid4(),
        code="OK",
        type="influencer",
        status="active",
        payout_email="pay@x.com",
    )
    row = AffiliatePayoutRequest(
        id=uuid4(),
        affiliate_id=aff.id,
        affiliate_code="OK",
        requested_by_email="p@x.com",
        payout_email="pay@x.com",
        amount_cents=10000,
        status="pending",
    )
    evaluate_strict_auto_approve(row, aff)

    row.attended_at = datetime.now(timezone.utc)
    with pytest.raises(AffiliatePayoutRequestError, match="attended"):
        evaluate_strict_auto_approve(row, aff)

    row.attended_at = None
    row.amount_cents = 999999
    with pytest.raises(AffiliatePayoutRequestError, match="cap"):
        evaluate_strict_auto_approve(row, aff)

    row.amount_cents = 10000
    aff.type = "customer"
    with pytest.raises(AffiliatePayoutRequestError, match="cash"):
        evaluate_strict_auto_approve(row, aff)
