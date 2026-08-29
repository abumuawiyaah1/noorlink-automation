"""Tests for recommendations 5–12 implementations."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.admin_finance import build_finance_snapshot_support
from app.services.affiliate_portal import AffiliatePortalError, get_affiliate_dashboard
from app.services.admin_promo_insights import build_insider_performance, build_promo_performance


@patch("app.services.admin_finance.build_finance_snapshot")
def test_support_finance_read_only(mock_full):
    mock_full.return_value = {
        "period_days": 30,
        "order_count": 5,
        "revenue_cents": 10000,
        "refunded_count": 1,
        "pending_fulfillment": 0,
        "by_status": {"delivered": 5},
        "margin_cents": 3000,
        "affiliate_liability_cents": 500,
    }
    snap = build_finance_snapshot_support(days=30)
    assert snap["read_only"] is True
    assert "margin_cents" not in snap
    assert snap["revenue_cents"] == 10000


@patch("app.services.affiliate_portal._affiliate_row")
def test_affiliate_dashboard_email_mismatch(mock_row):
    mock_row.return_value = {
        "id": "1",
        "code": "PARTNER1",
        "type": "influencer",
        "status": "active",
        "contact_email": "real@partner.com",
    }
    with pytest.raises(AffiliatePortalError, match="does not match"):
        get_affiliate_dashboard(code="PARTNER1", email="wrong@example.com")


@patch("app.services.admin_promo_insights.get_session_factory")
def test_promo_performance_empty(mock_factory):
    mock_factory.return_value = None
    result = build_promo_performance(days=30)
    assert "top_redeemed" in result


def test_insider_performance_structure():
    with patch("app.services.admin_promo_insights.email_analytics_summary") as mock_ea:
        mock_ea.return_value = {"insider_sends": {"aug-2026": 3}}
        with patch("app.api.supabase_repository.get_supabase_client") as mock_client:
            mock_client.return_value.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )
            result = build_insider_performance()
    assert result["by_issue"]["aug-2026"] == 3
