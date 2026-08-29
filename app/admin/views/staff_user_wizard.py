from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import ROLE_ADMIN, has_role, session_role, session_username
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_owner_guard import creatable_roles_for
from app.services.admin_staff_user import AdminStaffUserError, create_staff_user_from_wizard
from app.services.ops_alerts import notify_staff_governance


class StaffUserWizardView(BaseView):
    name = "Add staff"
    icon = "fa-solid fa-user-plus"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN,))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/staff-user", identity="staff-user", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        form_values: dict[str, str] = {}
        actor_role = session_role(request)
        actor_username = session_username(request)
        roles = creatable_roles_for(actor_role)

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            try:
                result = create_staff_user_from_wizard(
                    form=form_values,
                    actor_role=actor_role,
                    actor_username=actor_username,
                )
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=actor_username,
                            action="create_staff_user",
                            table_name="admin_users",
                            record_id=result["username"],
                            new_values={"username": result["username"], "role": result["role"]},
                            ip_address=_client_ip(request),
                        )
                notify_staff_governance(
                    title="New staff login created",
                    summary=f"{actor_username} created staff user {result['username']} ({result['role']}).",
                    details={
                        "created": result["username"],
                        "role": result["role"],
                        "by": actor_username,
                        "actor_role": actor_role,
                    },
                )
                request.session["flash_success"] = (
                    f"Created staff login '{result['username']}' with role {result['role']}."
                )
                return RedirectResponse(request.url_for("admin:staff-user"), status_code=302)
            except AdminStaffUserError as exc:
                request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "staff_user_wizard.html",
            {
                "form_values": form_values,
                "roles": roles,
                "actor_role": actor_role,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
