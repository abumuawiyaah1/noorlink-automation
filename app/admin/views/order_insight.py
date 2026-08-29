from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.services.admin_order_context import AdminOrderContextError, build_order_context


class OrderInsightView(BaseView):
    name = "Order insight"
    icon = "fa-solid fa-magnifying-glass"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/order-insight", identity="order-insight", methods=["GET", "POST"])
    async def lookup(self, request: Request):
        order_number = ""
        context = None
        error = None

        if request.method == "POST":
            form = await request.form()
            order_number = str(form.get("order_number") or "").strip()
        else:
            order_number = request.query_params.get("order", "").strip()

        if order_number:
            try:
                context = build_order_context(order_number=order_number)
            except AdminOrderContextError as exc:
                error = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "order_insight.html",
            {"order_number": order_number, "context": context, "error": error},
        )
