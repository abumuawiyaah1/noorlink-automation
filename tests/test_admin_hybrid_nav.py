"""Tests for notifications, help, security, and admin scripts."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.admin_help_playbooks import (
    filter_playbooks,
    list_help_areas,
    load_doc_markdown,
    markdown_to_safe_html,
    popular_tags,
    search_docs,
    search_playbooks,
    PLAYBOOKS,
)
from app.services.admin_notifications import notifications_for_role
from app.services.admin_scripts import AdminScriptError, run_admin_script
from app.services.admin_security import build_security_overview


def test_search_playbooks_webhook():
    results = search_playbooks("webhook")
    assert results
    assert any("paid" in p.title.lower() or "esim" in p.title.lower() for p in results)


def test_search_playbooks_empty_returns_all():
    assert len(search_playbooks("", role="admin")) == len(PLAYBOOKS)


def test_filter_playbooks_by_area_and_tag():
    marketing = filter_playbooks(role="admin", area="marketing")
    assert marketing
    assert all(p.area == "marketing" for p in marketing)
    assert any(p.id == "creator-outreach-email" for p in marketing)

    tagged = filter_playbooks(role="admin", tag="outreach")
    assert any(p.id == "creator-outreach-email" for p in tagged)

    areas = list_help_areas()
    assert {a["key"] for a in areas} >= {"support", "marketing", "getting-started"}
    assert "promo" in popular_tags(role="admin")


def test_load_telna_doc():
    content = load_doc_markdown("telna-runbook")
    if content:
        assert "Telna" in content


@patch("app.services.admin_notifications.security_threats_summary")
@patch("app.services.admin_notifications.sla_summary")
@patch("app.services.admin_notifications.get_operations_summary")
@patch("app.services.admin_notifications._count_open_unassigned_tickets", return_value=0)
@patch("app.services.admin_notifications._count_pending_promos", return_value=0)
@patch("app.services.admin_notifications._count_pending_catalog", return_value=0)
def test_notifications_support_role(
    mock_cat, mock_promo, mock_tickets, mock_summary, mock_sla, mock_threats
):
    mock_sla.return_value = {"waiting_over_24h": 0, "unassigned_over_24h": 0}
    mock_threats.return_value = {"needs_attention": False, "total": 0, "urgent_count": 0}
    mock_summary.return_value = {
        "pending_fulfillment": 2,
        "suspended_count": 0,
        "due_insider_issues": 0,
    }
    items = notifications_for_role("support")
    keys = {i.key for i in items}
    assert "pending-fulfillment" in keys
    assert "promo-approval" not in keys


@patch("app.services.admin_security.get_session_factory")
@patch("app.services.admin_security.get_engine")
def test_security_overview_has_checklist(mock_engine, mock_factory):
    mock_engine.return_value = MagicMock()
    mock_factory.return_value = None
    with patch("app.services.admin_security.security_threats_summary") as mock_threats:
        mock_threats.return_value = {"needs_attention": False, "total": 0, "recent": []}
        overview = build_security_overview(client_ip="127.0.0.1")
    assert len(overview["checklist"]) >= 5
    assert overview["client_ip"] == "127.0.0.1"
    assert "threats" in overview


def test_log_security_event():
    from app.services.security_threats import log_security_event

    with patch("app.services.security_threats.log_ops_event") as mock_log:
        log_security_event(
            threat_type="admin_login_failed",
            source="test",
            message="failed",
            ip_address="1.2.3.4",
        )
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["event_type"] == "security_admin_login_failed"


def test_search_docs_dashboard_guide():
    hits = search_docs("finance", role="support")
    slugs = {h.slug for h in hits}
    assert "admin-dashboard" in slugs


def test_search_docs_dev_admin_only():
    hits = search_docs("migration", role="admin")
    assert any(h.slug == "developer-codebase" for h in hits)
    support_hits = search_docs("migration", role="support")
    assert not any(h.slug == "developer-codebase" for h in support_hits)


def test_load_dev_doc_blocked_for_support():
    assert load_doc_markdown("developer-codebase", role="support") is None
    assert load_doc_markdown("developer-codebase", role="admin") is not None


def test_markdown_render_escapes_html():
    html_out = markdown_to_safe_html("## Title\n\n<script>alert(1)</script>")
    assert "<script>" not in html_out
    assert "<h2>Title</h2>" in html_out


def test_run_unknown_script():
    with pytest.raises(AdminScriptError, match="Unknown script"):
        run_admin_script("not-a-real-script")


@patch("app.services.admin_scripts.get_engine")
@patch("app.services.admin_scripts.db.get_supabase_client")
def test_health_check_script(mock_supabase, mock_engine):
    mock_engine.return_value = MagicMock()
    mock_supabase.return_value = MagicMock()
    result = run_admin_script("health_check")
    assert result["ok"] is True
