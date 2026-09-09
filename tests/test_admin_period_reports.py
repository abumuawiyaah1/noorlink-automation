"""Tests for weekly and monthly admin reports."""

from datetime import datetime, timezone
from unittest.mock import patch

from app.services.admin_monthly_summary import build_monthly_summary_html, should_send_monthly_report
from app.services.admin_weekly_summary import build_weekly_summary_html, should_send_weekly_report


@patch("app.services.admin_weekly_summary.paid_orders_between", return_value=[])
@patch("app.services.admin_weekly_summary.notifications_for_role", return_value=[])
@patch("app.services.admin_weekly_summary.newsletter_signups_between", return_value=2)
@patch("app.services.admin_weekly_summary.refunded_count_between", return_value=0)
@patch("app.services.admin_weekly_summary.affiliate_liability_cents", return_value=800)
def test_weekly_html_has_scorecard_sections(*_mocks):
    monday_six = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
    html = build_weekly_summary_html(now_utc=monday_six)
    assert "weekly scorecard" in html.lower()
    assert "Week at a glance" in html
    assert "Top packages" in html
    assert "Channel mix" in html
    assert "Margin watchlist" in html


@patch("app.services.admin_monthly_summary.paid_orders_between", return_value=[])
@patch("app.services.admin_monthly_summary.notifications_for_role", return_value=[])
@patch("app.services.admin_monthly_summary.newsletter_signups_between", return_value=5)
@patch("app.services.admin_monthly_summary.refunded_count_between", return_value=1)
@patch("app.services.admin_monthly_summary.affiliate_liability_cents", return_value=800)
def test_monthly_html_has_strategy_sections(*_mocks):
    first_six = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    html = build_monthly_summary_html(now_utc=first_six)
    assert "monthly review" in html.lower()
    assert "Strategic focus" in html
    assert "Acquisition channels" in html


def test_weekly_schedule_is_monday_after_six_or_tuesday_catchup():
    monday_five = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)
    monday_late = datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc)
    tuesday = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    wednesday = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
    assert should_send_weekly_report(monday_five) is False
    assert should_send_weekly_report(monday_late) is True
    assert should_send_weekly_report(tuesday) is True
    assert should_send_weekly_report(wednesday) is False


def test_monthly_schedule_is_first_after_six_or_second_catchup():
    first_five = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    first_late = datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)
    second = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    third = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
    assert should_send_monthly_report(first_five) is False
    assert should_send_monthly_report(first_late) is True
    assert should_send_monthly_report(second) is True
    assert should_send_monthly_report(third) is False
