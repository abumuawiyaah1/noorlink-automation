from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.roles import ALL_ROLES, has_role, session_role
from app.admin.wizard_catalog import STAFF_WIZARDS, WIZARD_CATEGORY, wizards_for_role


class StaffWizardsHubView(BaseView):
    name = "Quick start"
    icon = "fa-solid fa-compass"
    category = WIZARD_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return session_role(request) in ALL_ROLES

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/wizards", identity="staff-wizards", methods=["GET"])
    async def hub(self, request: Request):
        role = session_role(request)
        visible = wizards_for_role(role) if has_role(request, ALL_ROLES) else []
        return await self.templates.TemplateResponse(
            request,
            "staff_wizards_hub.html",
            {"wizards": visible, "all_wizards": STAFF_WIZARDS},
        )
