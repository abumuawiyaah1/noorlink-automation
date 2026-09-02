"""Tests for the daily admin business brief."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from app.services.admin_report_core import analyze_orders, is_report_send_hour as should_send_daily_report, yesterday_window
from app.services.admin_daily_summary import (
    build_daily_summary_html,
    send_daily_summary_email,
)


def _order(
    *,
    package_name: str = "Traveler 10GB",
    country: str = "Saudi Arabia",
    amount_cents: int = 2499,
    metadata: dict | None = None,
):
    return SimpleNamespace(
        package_name=package_name,
        country=country,
        amount_cents=amount_cents,
        metadata_=metadata or {
            "fulfillment_plan": {"wholesale_cents": 1150},
            "affiliate": {"code": "MASJID1"},
        },
    )


def test_should_send_daily_report_only_at_six_am_new_york():
    edt_six = datetime(2026, 9, 1, 10, 15, tzinfo=timezone.utc)
    edt_seven = datetime(2026, 9, 1, 11, 15, tzinfo=timezone.utc)
    assert should_send_daily_report(edt_six) is True
    assert should_send_daily_report(edt_seven) is False


def test_analyze_orders_groups_packages_destinations_and_sources():
    stats = analyze_orders(
        [
            _order(),
            _order(
                package_name="Starter 3GB",
                country="France",
                amount_cents=999,
                metadata={"fulfillment_plan": {"wholesale_cents": 450}, "promo": {"code": "INSIDER"}},
            ),
        ]
    )
    assert stats["order_count"] == 2
    assert stats["revenue_cents"] == 3498
    assert stats["top_packages"][0]["name"] == "Traveler 10GB"
    assert stats["top_destinations"][0][0] == "Saudi Arabia"
    assert any(label.startswith("Affiliate:") for label, _ in stats["top_sources"])
    assert any(label.startswith("Promo:") for label, _ in stats["top_sources"])


@patch("app.services.admin_daily_summary.notifications_for_role", return_value=[])
@patch("app.services.admin_daily_summary._paid_orders_between", return_value=[_order()])
def test_build_daily_summary_html_includes_requested_sections(mock_orders, _mock_alerts):
    ny_six = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    html = build_daily_summary_html(now_utc=ny_six)
    assert "Yesterday" in html
    assert "Top packages" in html
    assert "Top destinations" in html
    assert "Traffic source" in html
    assert "Needs attention" in html
    assert "Today's focus" in html
    assert "7-day" not in html.lower()


@patch("app.services.admin_daily_summary.send_email")
@patch("app.services.admin_daily_summary._mark_sent")
@patch("app.services.admin_daily_summary._already_sent_for_ny_date", return_value=False)
@patch("app.services.admin_daily_summary.admin_report_recipient_emails", return_value=["ops@noorlink.co"])
@patch("app.services.admin_daily_summary._paid_orders_between", return_value=[_order()])
@patch("app.services.admin_daily_summary.notifications_for_role", return_value=[])
def test_send_daily_summary_email_sends_once_in_window(
    _alerts,
    _orders,
    _recipients,
    _already_sent,
    mock_mark,
    mock_send,
):
    ny_six = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    result = send_daily_summary_email(now_utc=ny_six)
    assert result["sent"] == 1
    assert result["subject"].startswith("NoorLink daily —")
    mock_send.assert_called_once()
    mock_mark.assert_called_once()


@patch("app.services.admin_daily_summary.admin_report_recipient_emails", return_value=["ops@noorlink.co"])
def test_send_daily_summary_email_skips_outside_window(_recipients):
    ny_ten = datetime(2026, 9, 2, 14, 0, tzinfo=timezone.utc)
    result = send_daily_summary_email(now_utc=ny_ten)
    assert result["sent"] == 0
    assert "Outside 6:00 New York" in result["skipped"]


def test_yesterday_window_uses_new_york_calendar_day():
    ny_six = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    window = yesterday_window(ny_six)
    assert window.start_utc.astimezone(ZoneInfo("America/New_York")).day == 1
    assert window.end_utc.astimezone(ZoneInfo("America/New_York")).day == 2
