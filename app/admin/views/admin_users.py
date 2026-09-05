from __future__ import annotations

from typing import Any

from wtforms import SelectField
from starlette.requests import Request

from app.admin.roles import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_OWNER,
    is_owner,
    session_role,
    session_username,
)
from app.admin.views.base import AuditedModelView
from app.db.models import AdminAuditLog, AdminUser
from app.services.admin_owner_guard import OwnerGuardError, apply_owner_defaults, validate_staff_update
from app.services.ops_alerts import notify_staff_governance


class AdminUserAdmin(AuditedModelView, model=AdminUser):
    name = "Admin User"
    name_plural = "Admin Users"
    icon = "fa-solid fa-user-shield"
    allowed_roles = (ROLE_ADMIN, ROLE_OWNER)

    can_create = False
    list_template = "sqladmin/admin_user_list.html"

    column_list = [
        AdminUser.username,
        AdminUser.display_name,
        AdminUser.notify_email,
        AdminUser.role,
        AdminUser.is_active,
        AdminUser.is_protected,
        AdminUser.last_login_at,
        AdminUser.created_at,
    ]
    column_searchable_list = [AdminUser.username, AdminUser.display_name]
    column_filters = [AdminUser.role, AdminUser.is_active]
    column_default_sort = [(AdminUser.username, False)]

    form_columns = [
        AdminUser.username,
        AdminUser.display_name,
        AdminUser.notify_email,
        AdminUser.role,
        AdminUser.is_active,
        AdminUser.is_protected,
    ]
    form_args = {
        "role": {
            "choices": [(r, r) for r in sorted(ALL_ROLES)],
        },
    }
    form_overrides = {"role": SelectField}

    can_delete = False

    async def on_model_change(self, data: dict, model: AdminUser, is_created: bool, request: Request) -> None:
        actor_role = session_role(request)
        actor_username = session_username(request)

        new_role = str(data.get("role") or model.role)
        new_active = data.get("is_active", model.is_active)
        if isinstance(new_active, str):
            new_active = new_active.lower() in {"1", "true", "on", "yes"}

        # Non-owners cannot flip protected flag or mutate owner rows
        if not is_owner(request):
            data["is_protected"] = model.is_protected
            if model.role == ROLE_OWNER:
                data["role"] = ROLE_OWNER
                data["is_active"] = model.is_active
                new_role = ROLE_OWNER
                new_active = model.is_active

        try:
            validate_staff_update(
                actor_role=actor_role,
                actor_username=actor_username,
                target=model,
                new_role=new_role,
                new_is_active=bool(new_active),
            )
        except OwnerGuardError as exc:
            raise ValueError(str(exc)) from exc

        if new_role == ROLE_OWNER:
            data["is_protected"] = True

        # Stash for audit alert after save
        request.state.nl_staff_change = {
            "username": model.username,
            "old_role": model.role,
            "new_role": new_role,
            "old_active": bool(model.is_active),
            "new_active": bool(new_active),
            "actor": actor_username,
            "actor_role": actor_role,
        }

        apply_owner_defaults(model)
        await super().on_model_change(data, model, is_created, request)

    async def after_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        change = getattr(request.state, "nl_staff_change", None)
        if change and (
            change["old_role"] != change["new_role"]
            or change["old_active"] != change["new_active"]
        ):
            notify_staff_governance(
                title="Staff account changed",
                summary=f"{change['actor']} updated staff user {change['username']}.",
                details={
                    "target": change["username"],
                    "old_role": change["old_role"],
                    "new_role": change["new_role"],
                    "old_active": change["old_active"],
                    "new_active": change["new_active"],
                    "actor_role": change["actor_role"],
                },
            )
        if hasattr(super(), "after_model_change"):
            await super().after_model_change(data, model, is_created, request)


class AdminAuditLogAdmin(AuditedModelView, model=AdminAuditLog):
    name = "Audit Log"
    name_plural = "Audit Log"
    icon = "fa-solid fa-clipboard-list"
    allowed_roles = (ROLE_ADMIN, ROLE_OWNER)

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        AdminAuditLog.created_at,
        AdminAuditLog.admin_username,
        AdminAuditLog.action,
        AdminAuditLog.table_name,
        AdminAuditLog.record_id,
        AdminAuditLog.ip_address,
    ]
    column_searchable_list = [
        AdminAuditLog.admin_username,
        AdminAuditLog.action,
        AdminAuditLog.table_name,
        AdminAuditLog.record_id,
    ]
    column_default_sort = [(AdminAuditLog.created_at, True)]

    column_details_list = [
        AdminAuditLog.created_at,
        AdminAuditLog.admin_username,
        AdminAuditLog.action,
        AdminAuditLog.table_name,
        AdminAuditLog.record_id,
        AdminAuditLog.old_values,
        AdminAuditLog.new_values,
        AdminAuditLog.ip_address,
    ]
