"""Tests for finance, refunds, ops event log, GDPR, and customer self-service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.admin_finance import build_finance_snapshot
from app.services.admin_gdpr import AdminGdprError, export_customer_data
from app.services.admin_refunds import (
    AdminRefundError,
    validate_refund_eligibility,
)
from app.services.customer_self_service import (
    CustomerSelfServiceError,
    customer_resend_esim_email,
)
from app.services.ops_event_log import email_analytics_summary, log_ops_event


def test_log_ops_event_does_not_raise():
    with patch("app.services.ops_event_log.db.get_supabase_client") as mock_client:
        mock_client.return_value.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )
        log_ops_event(
            event_type="stripe_webhook",
            source="test",
            message="ok",
            order_number="NL-TEST",
        )


def test_email_analytics_summary_empty():
    with patch("app.services.ops_event_log.db.get_supabase_client") as mock_client:
        mock_client.return_value.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        summary = email_analytics_summary(days=30)
        assert summary["total_logged"] == 0


def test_validate_refund_blocks_high_usage():
    with pytest.raises(AdminRefundError, match="50%"):
        validate_refund_eligibility(
            row={"status": "delivered", "amount_cents": 1000, "data_used_gb": 6, "data_total_gb": 10},
            admin_override=False,
        )


def test_validate_refund_allows_override():
    validate_refund_eligibility(
        row={"status": "delivered", "amount_cents": 1000, "data_used_gb": 6, "data_total_gb": 10},
        admin_override=True,
    )


@patch("app.services.admin_finance.get_session_factory")
def test_finance_snapshot_no_db(mock_factory):
    mock_factory.return_value = None
    assert build_finance_snapshot(days=30)["error"] == "DATABASE_URL not configured"


def test_gdpr_export_invalid_email():
    with pytest.raises(AdminGdprError, match="Valid email"):
        export_customer_data(email="not-an-email", admin_username="admin")


def test_gdpr_delete_requires_confirm():
    with pytest.raises(AdminGdprError, match="confirm"):
        from app.services.admin_gdpr import delete_customer_data

        delete_customer_data(email="jane@example.com", admin_username="admin", confirm=False)


@patch("app.services.customer_self_service.resend_order_esim_email")
@patch("app.services.customer_self_service.db.merge_order_metadata")
@patch("app.services.customer_self_service.db.get_order_row_by_order_number")
@patch("app.services.customer_self_service.db.lookup_order")
def test_customer_resend_cooldown(mock_lookup, mock_get_row, mock_merge, mock_resend):
    mock_lookup.return_value = MagicMock(order_number="NL-ABC123")
    mock_get_row.return_value = {
        "order_number": "NL-ABC123",
        "email": "jane@example.com",
        "metadata": {
            "customer_resend_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        },
    }
    with pytest.raises(CustomerSelfServiceError, match="wait"):
        customer_resend_esim_email(order_number="NL-ABC123", email="jane@example.com")


@patch("app.services.ops_event_log.log_ops_event")
@patch("app.services.ops_event_log.log_email_delivery")
@patch("app.services.customer_self_service.resend_order_esim_email", return_value="msg-1")
@patch("app.services.customer_self_service.db.merge_order_metadata")
@patch("app.services.customer_self_service.db.get_order_row_by_order_number")
@patch("app.services.customer_self_service.db.lookup_order")
def test_customer_resend_success(
    mock_lookup, mock_get_row, mock_merge, mock_resend, mock_email_log, mock_ops_log
):
    mock_lookup.return_value = MagicMock(order_number="NL-ABC123")
    mock_get_row.return_value = {
        "order_number": "NL-ABC123",
        "email": "jane@example.com",
        "metadata": {},
    }
    result = customer_resend_esim_email(order_number="NL-ABC123", email="jane@example.com")
    assert result["success"] is True
    mock_resend.assert_called_once()
