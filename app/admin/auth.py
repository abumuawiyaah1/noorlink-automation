"""Session authentication for SQLAdmin."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.admin.passwords import verify_password
from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import AdminUser

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


class NoorLinkAdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username") or "").strip().lower()
        password = str(form.get("password") or "")

        if not username or not password:
            return False

        session_factory = get_session_factory()
        if session_factory is None:
            logger.error("Admin login attempted without DATABASE_URL configured")
            return False

        with session_factory() as session:
            user = session.execute(
                select(AdminUser).where(
                    AdminUser.username == username,
                    AdminUser.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if user is None or not verify_password(password, user.password_hash):
                from app.services.security_threats import log_security_event

                log_security_event(
                    threat_type="admin_login_failed",
                    source="admin_auth",
                    message=f"Failed admin login for {username or 'unknown'}",
                    severity="warning",
                    ip_address=_client_ip(request),
                    details={"username": username or None},
                )
                logger.warning("Failed admin login for username=%s ip=%s", username, _client_ip(request))
                return False

            user.last_login_at = datetime.now(timezone.utc)
            session.commit()

            request.session.update(
                {
                    "admin_user_id": str(user.id),
                    "admin_username": user.username,
                    "admin_role": user.role,
                    "admin_display_name": user.display_name or user.username,
                    "admin_session_started": datetime.now(timezone.utc).isoformat(),
                }
            )
            logger.info("Admin login success username=%s role=%s", user.username, user.role)
            return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        admin_user_id = request.session.get("admin_user_id")
        admin_username = request.session.get("admin_username")
        admin_role = request.session.get("admin_role")
        if not admin_user_id or not admin_username or not admin_role:
            return False
        return True
