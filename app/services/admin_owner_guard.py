"""Owner / break-glass guards — prevent a rogue admin from locking out the business owner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import func, select

from app.admin.passwords import MIN_PASSWORD_LENGTH, hash_password
from app.admin.roles import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_OWNER,
    STAFF_CREATABLE_BY_ADMIN,
    STAFF_CREATABLE_BY_OWNER,
)
from app.db.engine import get_session_factory
from app.db.models import AdminUser


class OwnerGuardError(Exception):
    """Staff governance rule blocked an action."""


PRIVILEGED_ROLES = {ROLE_OWNER, ROLE_ADMIN}


def is_owner_role(role: str) -> bool:
    return role == ROLE_OWNER


def is_privileged_role(role: str) -> bool:
    return role in PRIVILEGED_ROLES


def creatable_roles_for(actor_role: str) -> List[str]:
    if actor_role == ROLE_OWNER:
        return sorted(STAFF_CREATABLE_BY_OWNER)
    if actor_role == ROLE_ADMIN:
        return sorted(STAFF_CREATABLE_BY_ADMIN)
    return []


def count_active_owners() -> int:
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(AdminUser)
                .where(AdminUser.role == ROLE_OWNER)
                .where(AdminUser.is_active.is_(True))
            )
            or 0
        )


def validate_staff_create(*, actor_role: str, new_role: str) -> None:
    allowed = set(creatable_roles_for(actor_role))
    if new_role not in allowed:
        if new_role in PRIVILEGED_ROLES and actor_role != ROLE_OWNER:
            raise OwnerGuardError(
                "Only the business owner can create admin or owner accounts."
            )
        raise OwnerGuardError(
            f"Your role ({actor_role}) cannot create users with role '{new_role}'."
        )
    if new_role == ROLE_OWNER and actor_role != ROLE_OWNER:
        raise OwnerGuardError("Only an owner can create another owner account.")


def validate_staff_update(
    *,
    actor_role: str,
    actor_username: str,
    target: AdminUser,
    new_role: Optional[str] = None,
    new_is_active: Optional[bool] = None,
) -> None:
    """Enforce owner protection on Admin Users edits."""
    target_role = target.role
    target_protected = bool(target.is_protected) or target_role == ROLE_OWNER

    role_changing = new_role is not None and new_role != target_role
    active_changing = new_is_active is not None and bool(new_is_active) != bool(target.is_active)

    if not role_changing and not active_changing:
        return

    # Owners are never editable by non-owners
    if target_role == ROLE_OWNER and actor_role != ROLE_OWNER:
        raise OwnerGuardError("Owner accounts can only be changed by an owner (or break-glass recovery).")

    if target_protected and actor_role != ROLE_OWNER:
        raise OwnerGuardError("This account is protected. Only an owner can change it.")

    # Regular admins cannot touch other admins' privilege or active state
    if target_role == ROLE_ADMIN and actor_role != ROLE_OWNER:
        if role_changing or active_changing:
            raise OwnerGuardError(
                "Only the business owner can change or deactivate admin accounts."
            )

    if role_changing:
        assert new_role is not None
        if new_role not in ALL_ROLES:
            raise OwnerGuardError(f"Invalid role: {new_role}")
        if new_role in PRIVILEGED_ROLES and actor_role != ROLE_OWNER:
            raise OwnerGuardError("Only the business owner can promote someone to admin or owner.")
        if target_role == ROLE_OWNER and new_role != ROLE_OWNER:
            # Demoting an owner
            if actor_role != ROLE_OWNER:
                raise OwnerGuardError("Only an owner can demote an owner.")
            remaining = count_active_owners()
            # If this owner is active, demoting would remove one active owner
            if target.is_active and remaining <= 1:
                raise OwnerGuardError(
                    "Cannot demote the last active owner. Use break-glass recovery if locked out."
                )

    if active_changing and new_is_active is False:
        if target_role == ROLE_OWNER:
            if actor_role != ROLE_OWNER:
                raise OwnerGuardError("Only an owner can deactivate an owner account.")
            if count_active_owners() <= 1:
                raise OwnerGuardError(
                    "Cannot deactivate the last active owner. Use break-glass recovery if needed."
                )
        if target.username == actor_username and target_role == ROLE_OWNER:
            # Allow self-deactivate only if another owner exists (already checked count)
            pass


def apply_owner_defaults(user: AdminUser) -> None:
    if user.role == ROLE_OWNER:
        user.is_protected = True


def create_staff_user_secure(
    *,
    form: Dict[str, Any],
    actor_role: str,
    actor_username: str,
) -> Dict[str, Any]:
    username = str(form.get("username") or "").strip().lower()
    password = str(form.get("password") or "")
    display_name = str(form.get("display_name") or "").strip()
    role = str(form.get("role") or "support").strip().lower()
    notify_email = str(form.get("notify_email") or "").strip().lower() or None

    if len(username) < 3:
        raise OwnerGuardError("Username must be at least 3 characters.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise OwnerGuardError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if role not in ALL_ROLES:
        raise OwnerGuardError(f"Role must be one of: {', '.join(sorted(ALL_ROLES))}.")

    validate_staff_create(actor_role=actor_role, new_role=role)

    factory = get_session_factory()
    if factory is None:
        raise OwnerGuardError("DATABASE_URL is required.")

    password_hash = hash_password(password)
    now = datetime.now(timezone.utc)

    with factory() as session:
        existing = session.scalar(select(AdminUser).where(AdminUser.username == username))
        if existing is not None:
            raise OwnerGuardError(f"Username '{username}' already exists.")

        user = AdminUser(
            id=uuid4(),
            username=username,
            password_hash=password_hash,
            display_name=display_name or username,
            notify_email=notify_email,
            role=role,
            is_active=True,
            is_protected=(role == ROLE_OWNER),
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.commit()

    return {
        "username": username,
        "role": role,
        "display_name": display_name or username,
        "created_by": actor_username,
    }


def recover_or_create_owner(
    *,
    username: str,
    password: str,
    display_name: str = "",
    deactivate_username: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Break-glass: create/reactivate an owner via CLI (Railway), optionally disable a rogue account.
    Never callable from the web UI.
    """
    username = username.strip().lower()
    if len(username) < 3:
        raise OwnerGuardError("Username must be at least 3 characters.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise OwnerGuardError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    factory = get_session_factory()
    if factory is None:
        raise OwnerGuardError("DATABASE_URL is required.")

    password_hash = hash_password(password)
    now = datetime.now(timezone.utc)
    actions: List[str] = []

    with factory() as session:
        if deactivate_username:
            rogue = session.scalar(
                select(AdminUser).where(AdminUser.username == deactivate_username.strip().lower())
            )
            if rogue is None:
                raise OwnerGuardError(f"Rogue username '{deactivate_username}' not found.")
            if rogue.username == username:
                raise OwnerGuardError("Cannot deactivate the same account you are recovering.")
            rogue.is_active = False
            rogue.updated_at = now
            actions.append(f"deactivated:{rogue.username}")

        user = session.scalar(select(AdminUser).where(AdminUser.username == username))
        if user is None:
            user = AdminUser(
                id=uuid4(),
                username=username,
                password_hash=password_hash,
                display_name=display_name or username,
                role=ROLE_OWNER,
                is_active=True,
                is_protected=True,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            actions.append(f"created_owner:{username}")
        else:
            user.password_hash = password_hash
            user.role = ROLE_OWNER
            user.is_active = True
            user.is_protected = True
            user.display_name = display_name or user.display_name or username
            user.updated_at = now
            actions.append(f"restored_owner:{username}")

        session.commit()

    return {"username": username, "role": ROLE_OWNER, "actions": actions}
