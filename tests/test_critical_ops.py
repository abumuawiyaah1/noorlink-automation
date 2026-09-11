"""Tests for critical ops logging and emergency assist."""

from unittest.mock import patch

from app.services.critical_ops import (
    is_critical_row,
    list_critical_events,
    report_critical_event,
)
from app.services.emergency_assist import emergency_assist, match_emergency_playbooks


def test_is_critical_row_by_severity_and_type():
    assert is_critical_row({"severity": "critical", "event_type": "other"})
    assert is_critical_row({"severity": "error", "event_type": "other"})
    assert is_critical_row({"severity": "info", "event_type": "checkout_failed"})
    assert is_critical_row({"severity": "warning", "event_type": "security_login_failed"})
    assert not is_critical_row({"severity": "info", "event_type": "fulfillment_success"})


@patch("app.services.critical_ops.notify_critical_ops")
@patch("app.services.critical_ops.log_ops_event")
def test_report_critical_event_logs_and_notifies(mock_log, mock_notify):
    report_critical_event(
        event_type="checkout_failed",
        source="test",
        message="Stripe down",
        order_number="NL-1",
        title="Checkout failed",
    )
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["severity"] == "critical"
    mock_notify.assert_called_once()


@patch("app.services.critical_ops.list_ops_events")
def test_list_critical_events_filters(mock_list):
    mock_list.return_value = [
        {"severity": "info", "event_type": "fulfillment_success"},
        {"severity": "critical", "event_type": "checkout_failed", "message": "x"},
        {"severity": "error", "event_type": "fulfillment_failed"},
    ]
    rows = list_critical_events(limit=10)
    assert len(rows) == 2
    assert rows[0]["event_type"] == "checkout_failed"


def test_emergency_assist_checkout_question():
    result = emergency_assist(question="Checkout is failing for customers", role="admin")
    assert result["answer"]
    assert result["playbooks"] or "Critical logs" in result["answer"]
    matched = match_emergency_playbooks(question="customer paid but no QR email", role="admin")
    assert matched
    assert any("fulfill" in p.id or "esim" in p.title.lower() or "qr" in " ".join(p.tags) for p in matched)
