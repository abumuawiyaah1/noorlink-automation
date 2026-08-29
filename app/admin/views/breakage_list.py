from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.nav_catalog import OPERATIONS_CATEGORY
from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role
from app.services.admin_breakage import list_breakage_allowances


class BreakageListView(BaseView):
    name = "Breakage allowances"
    icon = "fa-solid fa-shield"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/breakage", identity="breakage-list", methods=["GET"])
    async def list_view(self, request: Request):
        rows = list_breakage_allowances()
        return await self.templates.TemplateResponse(
            request,
            "breakage_list.html",
            {"allowances": rows},
        )
