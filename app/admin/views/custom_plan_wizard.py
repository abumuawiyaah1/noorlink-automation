from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import CATALOG_MANAGER_ROLES, ROLE_ADMIN, has_role, session_username
from app.admin.views.base import _client_ip
from app.admin.wizard_catalog import WIZARD_CATEGORY
from app.db.engine import get_session_factory
from app.services.admin_catalog import (
    AdminCatalogError,
    create_custom_plan_from_wizard,
    list_fulfillment_provider_options,
)


class CustomPlanWizardView(BaseView):
    name = "New custom plan"
    icon = "fa-solid fa-wand-magic-sparkles"
    category = WIZARD_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, CATALOG_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/new-custom-plan", identity="new-custom-plan", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        if not has_role(request, CATALOG_MANAGER_ROLES):
            request.session["flash_error"] = "You do not have permission to create catalog plans."
            return RedirectResponse("/admin", status_code=302)

        editor_is_admin = has_role(request, (ROLE_ADMIN,))
        form_values: dict[str, str] = {}

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            try:
                result = create_custom_plan_from_wizard(
                    form=form_values,
                    editor_is_admin=editor_is_admin,
                    editor_username=session_username(request),
                )
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="create_custom_plan_wizard",
                            table_name="esim_packages",
                            record_id=result["slug"],
                            new_values={
                                "name": result["name"],
                                "catalog_key": result["catalog_key"],
                                "provider": result["provider"],
                                "sale_status": result["sale_status"],
                            },
                            ip_address=_client_ip(request),
                        )

                if result["admin_approved"] and result["route_approved"]:
                    msg = (
                        f"Created {result['name']} ({result['slug']}) with route "
                        f"{result['catalog_key']} — {result['sale_status']}."
                    )
                else:
                    msg = (
                        f"Created {result['name']} ({result['slug']}). "
                        "Pending admin approval before it can go on sale."
                    )
                request.session["flash_success"] = msg
                return RedirectResponse(
                    request.url_for("admin:new-custom-plan"),
                    status_code=302,
                )
            except AdminCatalogError as exc:
                request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "custom_plan_wizard.html",
            {
                "providers": list_fulfillment_provider_options(),
                "editor_is_admin": editor_is_admin,
                "form_values": form_values,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
