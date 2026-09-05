from unittest.mock import patch

from app.services.admin_do_next import (
    do_next_for_user,
    soft_reminders_for_role,
)
from app.services.support_categories import (
    get_reply_template,
    list_all_reply_templates,
)


def test_common_saved_replies_available_on_any_category():
    templates = list_all_reply_templates("install_qr")
    keys = {t["key"] for t in templates}
    assert "install_steps" in keys
    assert "common_qr_missing" in keys
    assert "common_install_before_fly" in keys
    body = get_reply_template("refund", "common_refund_policy")
    assert body is not None
    assert "refund" in body.lower()


@patch("app.services.admin_do_next._count_tickets_assigned_to", return_value=2)
@patch("app.services.admin_do_next.soft_reminders_for_role", return_value=[])
@patch("app.services.admin_do_next.notifications_for_role")
def test_do_next_includes_my_tickets_and_urgent(mock_notifs, _soft, _mine):
    from app.services.admin_notifications import AdminNotification

    mock_notifs.return_value = [
        AdminNotification(
            key="pending-fulfillment",
            title="Orders paid but not fulfilled",
            detail="x",
            count=1,
            severity="urgent",
            link_path="/admin/fulfill-order",
            roles=("admin", "support"),
        )
    ]
    items = do_next_for_user(role="support", username="sara", limit=6)
    keys = [i.key for i in items]
    assert "my-tickets" in keys
    assert items[0].key == "pending-fulfillment"  # urgent first
    assert next(i for i in items if i.key == "my-tickets").count == 2


@patch("app.services.admin_do_next._count_creators_needing_outreach", return_value=3)
@patch("app.services.admin_do_next._count_insider_upcoming", return_value=1)
@patch("app.services.admin_do_next.list_open_payout_requests", return_value=[{}])
def test_soft_reminders_for_admin(mock_payouts, _insider, _creators):
    items = soft_reminders_for_role("admin")
    keys = {i.key for i in items}
    assert "creator-followup" in keys
    assert "insider-upcoming" in keys
    assert "affiliate-payouts" in keys
