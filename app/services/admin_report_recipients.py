"""Shared recipient list for automated admin business reports."""

from __future__ import annotations

from typing import List

from sqlalchemy import select

from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import AdminUser


def admin_report_recipient_emails() -> List[str]:
    """Ops inbox plus every active admin with a notify email."""
    settings = get_settings()
    emails: List[str] = []
    ops = (settings.ops_alert_email or "").strip().lower()
    if ops and "@" in ops:
        emails.append(ops)

    factory = get_session_factory()
    if factory is not None:
        with factory() as session:
            rows = session.scalars(
                select(AdminUser)
                .where(AdminUser.is_active.is_(True))
                .where(AdminUser.role == "admin")
            ).all()
            for user in rows:
                notify = (user.notify_email or "").strip().lower()
                if notify and "@" in notify and notify not in emails:
                    emails.append(notify)
    return emails
