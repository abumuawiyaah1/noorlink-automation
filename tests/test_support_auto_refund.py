"""Tests for 48h unanswered strict auto-refund."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.support_auto_refund import (
    AUTO_REFUND_MAX_USAGE_PCT,
    AutoRefundSkip,
    evaluate_strict_auto_refund,
    process_ticket_auto_refund,
    ticket_has_human_reply,
)


def test_strict_policy_blocks_high_usage():
    row = {
        "status": "delivered",
        "amount_cents": 2000,
        "data_used_gb": 3,
        "data_total_gb": 5,
        "stripe_payment_intent_id": "pi_test",
    }
    with pytest.raises(AutoRefundSkip, match="used"):
        evaluate_strict_auto_refund(row)


def test_strict_policy_blocks_high_amount():
    row = {
        "status": "delivered",
        "amount_cents": 9900,
        "data_used_gb": 0,
        "data_total_gb": 5,
        "stripe_payment_intent_id": "pi_test",
    }
    with pytest.raises(AutoRefundSkip, match="exceeds"):
        evaluate_strict_auto_refund(row)


def test_strict_policy_allows_low_usage():
    row = {
        "status": "delivered",
        "amount_cents": 2000,
        "data_used_gb": 0.2,
        "data_total_gb": 5,
        "stripe_payment_intent_id": "pi_test",
    }
    evaluate_strict_auto_refund(row)
    assert AUTO_REFUND_MAX_USAGE_PCT == 20


@patch("app.services.support_auto_refund.get_session_factory")
def test_human_reply_detected(mock_factory):
    human = MagicMock()
    human.admin_username = "support1"
    auto = MagicMock()
    auto.admin_username = "auto"

    session = MagicMock()
    session.scalars.return_value.all.return_value = [auto, human]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    factory.return_value.__exit__.return_value = None
    mock_factory.return_value = factory

    assert ticket_has_human_reply(uuid4()) is True


@patch("app.services.support_auto_refund.notify_staff_governance")
@patch("app.services.support_auto_refund.log_ops_event")
@patch("app.services.support_auto_refund.send_staff_reply")
@patch("app.services.support_auto_refund.process_order_refund")
@patch("app.services.support_auto_refund.db.get_order_row_by_order_number")
@patch("app.services.support_auto_refund.db.lookup_order")
@patch("app.services.support_auto_refund.ticket_has_human_reply", return_value=False)
@patch("app.services.support_auto_refund.get_session_factory")
def test_process_ticket_auto_refund_happy(
    mock_factory,
    mock_human,
    mock_lookup,
    mock_row,
    mock_refund,
    mock_reply,
    mock_log,
    mock_notify,
):
    ticket = MagicMock()
    ticket.id = uuid4()
    ticket.ticket_number = "TCK-ABCDEF12"
    ticket.email = "a@example.com"
    ticket.name = "Alex"
    ticket.order_number = "NL-ABCDEF12"
    ticket.subject = "Refund"
    ticket.message = "Please refund"
    ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=50)

    mock_lookup.return_value = MagicMock(order_number="NL-ABCDEF12")
    mock_row.return_value = {
        "order_number": "NL-ABCDEF12",
        "status": "delivered",
        "amount_cents": 1500,
        "data_used_gb": 0,
        "data_total_gb": 5,
        "stripe_payment_intent_id": "pi_x",
    }
    mock_refund.return_value = {
        "order_number": "NL-ABCDEF12",
        "refund_id": "re_123",
        "amount_cents": 1500,
        "status": "refunded",
    }

    fresh = MagicMock()
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = fresh
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    factory.return_value.__exit__.return_value = None
    mock_factory.return_value = factory

    result = process_ticket_auto_refund(ticket)
    assert result["refund_id"] == "re_123"
    mock_refund.assert_called_once()
    mock_reply.assert_called_once()
    assert fresh.status == "closed"


@patch("app.services.support_auto_refund.ticket_has_human_reply", return_value=True)
def test_skip_when_staff_replied(mock_human):
    ticket = MagicMock()
    ticket.id = uuid4()
    ticket.ticket_number = "TCK-X"
    with pytest.raises(AutoRefundSkip, match="Staff already replied"):
        process_ticket_auto_refund(ticket)
