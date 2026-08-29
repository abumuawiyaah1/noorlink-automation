from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role, session_username
from app.admin.views.base import _client_ip
from app.admin.wizard_catalog import WIZARD_CATEGORY
from app.db.engine import get_session_factory
from app.services.admin_support_wizard import (
    AdminSupportWizardError,
    SUPPORT_TOPIC_OPTIONS,
    create_customer_help_ticket,
)


class HelpCustomerWizardView(BaseView):
    name = "Help customer wizard"
    icon = "fa-solid fa-life-ring"
    category = WIZARD_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/help-customer", identity="help-customer", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        form_values: dict[str, str] = {}

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            try:
                result = create_customer_help_ticket(form=form_values)
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="help_customer_wizard",
                            table_name="support_tickets",
                            record_id=result["ticket_number"],
                            new_values=result,
                            ip_address=_client_ip(request),
                        )
                request.session["flash_success"] = (
                    f"Ticket {result['ticket_number']} created — confirmation sent to "
                    f"{result['email']}."
                )
                return RedirectResponse(
                    f"/admin/support-inbox/{result['ticket_number']}",
                    status_code=302,
                )
            except AdminSupportWizardError as exc:
                request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "help_customer_wizard.html",
            {
                "topics": SUPPORT_TOPIC_OPTIONS,
                "form_values": form_values,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
