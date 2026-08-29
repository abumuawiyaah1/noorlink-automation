from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role, session_username
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_operations import AdminOperationsError, list_suspended_orders, reactivate_suspended_order


class SuspendedOrdersView(BaseView):
    name = "Suspended orders"
    icon = "fa-solid fa-pause-circle"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/suspended-orders", identity="suspended-orders", methods=["GET", "POST"])
    async def list_view(self, request: Request):
        if request.method == "POST":
            form = await request.form()
            order_number = str(form.get("order_number") or "")
            try:
                result = reactivate_suspended_order(order_number=order_number)
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="reactivate_order",
                            table_name="orders",
                            record_id=result["order_number"],
                            new_values=result,
                            ip_address=_client_ip(request),
                        )
                request.session["flash_success"] = f"Order {result['order_number']} reactivated."
            except AdminOperationsError as exc:
                request.session["flash_error"] = str(exc)
            return RedirectResponse(request.url_for("admin:suspended-orders"), status_code=302)

        orders = list_suspended_orders()
        return await self.templates.TemplateResponse(
            request,
            "suspended_orders.html",
            {
                "orders": orders,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
