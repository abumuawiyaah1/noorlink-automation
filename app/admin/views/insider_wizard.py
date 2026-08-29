from __future__ import annotations

from datetime import date, timedelta

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import PROMO_MANAGER_ROLES, has_role, session_username
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_insider_wizard import (
    AdminInsiderError,
    create_insider_issue_from_wizard,
    send_insider_test_email,
)


class InsiderWizardView(BaseView):
    name = "Insider wizard"
    icon = "fa-solid fa-paper-plane"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, PROMO_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/insider-wizard", identity="insider-wizard", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        form_values: dict[str, str] = {}
        default_send = (date.today() + timedelta(days=1)).isoformat()

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            action = form_values.get("action", "create")
            try:
                if action == "test":
                    message_id = send_insider_test_email(
                        form=form_values,
                        to_email=form_values.get("test_email", ""),
                    )
                    request.session["flash_success"] = f"Test email sent (id: {message_id})."
                else:
                    result = create_insider_issue_from_wizard(form=form_values)
                    session_factory = get_session_factory()
                    if session_factory is not None:
                        with session_factory() as session:
                            write_audit_log(
                                session,
                                admin_user_id=request.session.get("admin_user_id"),
                                admin_username=session_username(request),
                                action="create_insider_wizard",
                                table_name="insider_issues",
                                record_id=result["slug"],
                                new_values=result,
                                ip_address=_client_ip(request),
                            )
                    request.session["flash_success"] = (
                        f"Insider issue '{result['slug']}' scheduled for {result['send_at']}."
                    )
                return RedirectResponse(request.url_for("admin:insider-wizard"), status_code=302)
            except AdminInsiderError as exc:
                request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "insider_wizard.html",
            {
                "form_values": form_values,
                "default_send": default_send,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
