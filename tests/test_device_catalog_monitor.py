from unittest.mock import patch

import pytest

from app.services.device_catalog_monitor import (
    diff_device_catalogs,
    get_top_device_check_misses,
    record_device_check_miss,
    run_device_catalog_monitor,
    should_send_weekly_device_alert,
)


@pytest.fixture
def reference_catalog(tmp_path, monkeypatch):
    ref_file = tmp_path / "esim_device_reference.json"
    ref_file.write_text(
        """
{
  "brands": [
    {
      "id": "apple",
      "name": "Apple",
      "models": [
        {"id": "iphone-17", "name": "iPhone 17"},
        {"id": "iphone-18", "name": "iPhone 18"}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.device_catalog_monitor.REFERENCE_PATH",
        ref_file,
    )
    return ref_file


@patch("app.services.device_catalog_monitor.load_live_catalog")
def test_diff_flags_missing_from_live(mock_live, reference_catalog):
    mock_live.return_value = [
        {
            "id": "apple",
            "name": "Apple",
            "models": [{"id": "iphone-17", "name": "iPhone 17"}],
        }
    ]
    diff = diff_device_catalogs()
    assert diff["missing_from_live"] == ["iPhone 18"]
    assert diff["missing_from_reference"] == []


@patch("app.services.device_catalog_monitor.log_ops_event")
def test_record_device_check_miss_skips_short_queries(mock_log):
    record_device_check_miss("a")
    mock_log.assert_not_called()

    record_device_check_miss("iPhone 18")
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["event_type"] == "device_check_miss"


@patch("app.services.device_catalog_monitor.list_ops_events")
def test_get_top_device_check_misses(mock_list):
    mock_list.return_value = [
        {"message": "iPhone 18", "created_at": "2099-01-01T00:00:00+00:00"},
        {"message": "iPhone 18", "created_at": "2099-01-02T00:00:00+00:00"},
        {"message": "Pixel 10", "created_at": "2099-01-03T00:00:00+00:00"},
    ]
    rows = get_top_device_check_misses(days=7, limit=5)
    assert rows[0]["query"] == "iPhone 18"
    assert rows[0]["count"] == 2


def test_should_send_weekly_device_alert_on_monday():
    from datetime import datetime, timezone

    monday = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    tuesday = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    assert should_send_weekly_device_alert(monday) is True
    assert should_send_weekly_device_alert(tuesday) is False


@patch("app.services.device_catalog_monitor.mark_report_sent")
@patch("app.services.device_catalog_monitor.send_email")
@patch("app.services.device_catalog_monitor.notify_device_catalog_review")
@patch("app.services.device_catalog_monitor.admin_report_recipient_emails", return_value=["ops@noorlink.co"])
@patch("app.services.device_catalog_monitor.report_already_sent", return_value=False)
@patch("app.services.device_catalog_monitor.get_top_device_check_misses")
@patch("app.services.device_catalog_monitor.load_live_catalog")
def test_run_monitor_sends_when_drift(
    mock_live,
    mock_misses,
    mock_already_sent,
    mock_recipients,
    mock_slack,
    mock_email,
    mock_mark,
    reference_catalog,
):
    mock_live.return_value = [
        {
            "id": "apple",
            "name": "Apple",
            "models": [{"id": "iphone-17", "name": "iPhone 17"}],
        }
    ]
    mock_misses.return_value = []
    from datetime import datetime, timezone

    monday = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    result = run_device_catalog_monitor(force=False, now_utc=monday)
    assert result["sent"] == 1
    assert result["needs_attention"] is True
    mock_email.assert_called_once()
    mock_slack.assert_called_once()
