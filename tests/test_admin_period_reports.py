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


def test_weekly_schedule_is_monday_six_am_new_york():
    monday = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
    tuesday = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    assert should_send_weekly_report(monday) is True
    assert should_send_weekly_report(tuesday) is False


def test_monthly_schedule_is_first_six_am_new_york():
    first = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    second = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    assert should_send_monthly_report(first) is True
    assert should_send_monthly_report(second) is False
