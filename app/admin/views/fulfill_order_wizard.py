from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role, session_username
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_operations import AdminOperationsError, manual_fulfill_order


class FulfillOrderWizardView(BaseView):
    name = "Fulfill order"
    icon = "fa-solid fa-bolt"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/fulfill-order", identity="fulfill-order", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        form_values: dict[str, str] = {}
        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            paid_only = str(form.get("paid_only") or "").lower() in {"1", "on", "true", "yes"}
            try:
                result = manual_fulfill_order(
                    order_number=form_values.get("order_number", ""),
                    paid_only=paid_only,
                )
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="manual_fulfill_order",
                            table_name="orders",
                            record_id=result["order_number"],
                            new_values=result,
                            ip_address=_client_ip(request),
                        )
                request.session["flash_success"] = (
                    f"Order {result['order_number']} fulfilled — status is now {result['status']}."
                )
                return RedirectResponse(request.url_for("admin:fulfill-order"), status_code=302)
            except AdminOperationsError as exc:
                request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "fulfill_order_wizard.html",
            {
                "form_values": form_values,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
