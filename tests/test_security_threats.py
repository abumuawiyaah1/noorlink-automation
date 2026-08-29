"""Tests for external security threat tracking."""

from unittest.mock import MagicMock, patch

from app.services.security_threats import log_security_event, security_threats_summary


@patch("app.services.security_threats.log_ops_event")
def test_log_security_event_prefix(mock_log):
    log_security_event(
        threat_type="webhook_rejected",
        source="stripe",
        message="bad signature",
        ip_address="203.0.113.1",
    )
    assert mock_log.call_args.kwargs["event_type"] == "security_webhook_rejected"
    assert mock_log.call_args.kwargs["details"]["ip"] == "203.0.113.1"


@patch("app.services.security_threats.list_ops_events")
def test_security_summary_flags_repeated_logins(mock_list):
    mock_list.return_value = [
        {
            "created_at": "2026-08-28T12:00:00+00:00",
            "event_type": "security_admin_login_failed",
            "severity": "warning",
            "message": "Failed login",
            "source": "admin_auth",
            "details": {"ip": "198.51.100.9"},
        },
        {
            "created_at": "2026-08-28T12:01:00+00:00",
            "event_type": "security_admin_login_failed",
            "severity": "warning",
            "message": "Failed login",
            "source": "admin_auth",
            "details": {"ip": "198.51.100.9"},
        },
        {
            "created_at": "2026-08-28T12:02:00+00:00",
            "event_type": "security_admin_login_failed",
            "severity": "warning",
            "message": "Failed login",
            "source": "admin_auth",
            "details": {"ip": "198.51.100.9"},
        },
    ]
    summary = security_threats_summary(hours=24)
    assert summary["needs_attention"] is True
    assert summary["repeated_login_ips"][0]["ip"] == "198.51.100.9"
    assert summary["repeated_login_ips"][0]["count"] == 3


@patch("app.services.ops_alerts.notify_security_threat")
@patch("app.services.security_threats.log_ops_event")
@patch("app.services.security_threats._login_alert_sent_recently", return_value=False)
@patch("app.services.security_threats._login_failures_for_ip", return_value=5)
def test_maybe_alert_repeated_admin_login(mock_count, mock_sent, mock_log, mock_notify):
    from app.services.security_threats import maybe_alert_repeated_admin_login

    maybe_alert_repeated_admin_login(ip_address="198.51.100.9", username="admin")
    mock_notify.assert_called_once()
    assert mock_log.call_count == 1


@patch("app.services.security_threats._login_alert_sent_recently", return_value=False)
@patch("app.services.security_threats._login_failures_for_ip", return_value=2)
def test_maybe_alert_skips_below_threshold(mock_count, mock_sent):
    from app.services.security_threats import maybe_alert_repeated_admin_login

    with patch("app.services.ops_alerts.notify_security_threat") as mock_notify:
        maybe_alert_repeated_admin_login(ip_address="198.51.100.9")
        mock_notify.assert_not_called()
