"""Tests for owner / break-glass protection."""

from unittest.mock import MagicMock, patch

import pytest

from app.admin.roles import ROLE_ADMIN, ROLE_OWNER, ROLE_SUPPORT
from app.services.admin_owner_guard import (
    OwnerGuardError,
    creatable_roles_for,
    validate_staff_create,
    validate_staff_update,
)


def test_admin_cannot_create_admin_or_owner():
    with pytest.raises(OwnerGuardError, match="Only the business owner"):
        validate_staff_create(actor_role=ROLE_ADMIN, new_role=ROLE_ADMIN)
    with pytest.raises(OwnerGuardError, match="Only the business owner"):
        validate_staff_create(actor_role=ROLE_ADMIN, new_role=ROLE_OWNER)


def test_admin_can_create_support():
    validate_staff_create(actor_role=ROLE_ADMIN, new_role=ROLE_SUPPORT)


def test_owner_can_create_admin():
    validate_staff_create(actor_role=ROLE_OWNER, new_role=ROLE_ADMIN)


def test_creatable_roles_filtered():
    admin_roles = set(creatable_roles_for(ROLE_ADMIN))
    assert ROLE_ADMIN not in admin_roles
    assert ROLE_OWNER not in admin_roles
    assert ROLE_SUPPORT in admin_roles
    owner_roles = set(creatable_roles_for(ROLE_OWNER))
    assert ROLE_OWNER in owner_roles
    assert ROLE_ADMIN in owner_roles


def test_admin_cannot_deactivate_owner():
    target = MagicMock()
    target.role = ROLE_OWNER
    target.is_protected = True
    target.is_active = True
    target.username = "boss"
    with pytest.raises(OwnerGuardError, match="Owner accounts"):
        validate_staff_update(
            actor_role=ROLE_ADMIN,
            actor_username="helper",
            target=target,
            new_is_active=False,
        )


def test_admin_cannot_touch_other_admin():
    target = MagicMock()
    target.role = ROLE_ADMIN
    target.is_protected = False
    target.is_active = True
    target.username = "peer"
    with pytest.raises(OwnerGuardError, match="Only the business owner"):
        validate_staff_update(
            actor_role=ROLE_ADMIN,
            actor_username="helper",
            target=target,
            new_is_active=False,
        )


@patch("app.services.admin_owner_guard.count_active_owners", return_value=1)
def test_cannot_demote_last_owner(mock_count):
    target = MagicMock()
    target.role = ROLE_OWNER
    target.is_protected = True
    target.is_active = True
    target.username = "boss"
    with pytest.raises(OwnerGuardError, match="last active owner"):
        validate_staff_update(
            actor_role=ROLE_OWNER,
            actor_username="boss",
            target=target,
            new_role=ROLE_ADMIN,
        )


@patch("app.services.admin_owner_guard.count_active_owners", return_value=2)
def test_owner_can_demote_when_another_exists(mock_count):
    target = MagicMock()
    target.role = ROLE_OWNER
    target.is_protected = True
    target.is_active = True
    target.username = "cofounder"
    validate_staff_update(
        actor_role=ROLE_OWNER,
        actor_username="boss",
        target=target,
        new_role=ROLE_ADMIN,
    )
