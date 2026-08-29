"""Create staff admin users from the dashboard (with owner guards)."""

from __future__ import annotations

from typing import Any, Dict

from app.services.admin_owner_guard import OwnerGuardError, create_staff_user_secure


class AdminStaffUserError(Exception):
    """Staff user wizard failed."""


def create_staff_user_from_wizard(
    *,
    form: Dict[str, Any],
    actor_role: str = "admin",
    actor_username: str = "system",
) -> Dict[str, Any]:
    try:
        return create_staff_user_secure(
            form=form,
            actor_role=actor_role,
            actor_username=actor_username,
        )
    except OwnerGuardError as exc:
        raise AdminStaffUserError(str(exc)) from exc
