from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.nav_catalog import WIZARD_CATEGORY
from app.admin.roles import ALL_ROLES, session_role, session_username
from app.admin.wizard_catalog import wizards_for_role
from app.services.admin_do_next import do_next_for_user


class HomeHubView(BaseView):
    name = "Do next"
    icon = "fa-solid fa-house"
    category = WIZARD_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return session_role(request) in ALL_ROLES

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/home", identity="home-hub", methods=["GET"])
    async def home(self, request: Request):
        role = session_role(request)
        username = session_username(request)
        do_next = do_next_for_user(role=role, username=username, limit=6)
        wizards = wizards_for_role(role)[:4]
        return await self.templates.TemplateResponse(
            request,
            "home_hub.html",
            {
                "do_next": do_next,
                "wizards": wizards,
                "display_name": request.session.get("admin_display_name")
                or username
                or "there",
                "role": role,
            },
        )
