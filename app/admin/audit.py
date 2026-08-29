"""Audit logging for admin actions."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import AdminAuditLog

logger = logging.getLogger(__name__)


def write_audit_log(
    session: Session,
    *,
    admin_user_id: Optional[str],
    admin_username: str,
    action: str,
    table_name: str,
    record_id: Optional[str] = None,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    try:
        entry = AdminAuditLog(
            admin_user_id=admin_user_id,
            admin_username=admin_username,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
        )
        session.add(entry)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to write admin audit log for %s.%s", table_name, action)
