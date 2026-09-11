from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from sqladmin import BaseView, expose

from app.admin.nav_catalog import HELP_CATEGORY
from app.admin.roles import ALL_ROLES, session_role
from app.services.emergency_assist import emergency_assist, emergency_desk_context


class EmergencyDeskView(BaseView):
    name = "Emergency help"
    icon = "fa-solid fa-kit-medical"
    category = HELP_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return session_role(request) in ALL_ROLES

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/emergency/ask", identity="emergency-ask", methods=["POST"])
    async def ask(self, request: Request):
        if not self.is_accessible(request):
            return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
        role = session_role(request)
        try:
            body = await request.json()
        except Exception:
            form = await request.form()
            body = {"question": str(form.get("question") or "")}
        question = str((body or {}).get("question") or "").strip()
        if not question:
            return JSONResponse({"ok": False, "error": "Ask what is going wrong."}, status_code=400)
        result = emergency_assist(question=question, role=role)
        return JSONResponse({"ok": True, **result})

    @expose("/emergency", identity="emergency-desk", methods=["GET"])
    async def desk(self, request: Request):
        role = session_role(request)
        ctx = emergency_desk_context(role=role)
        return await self.templates.TemplateResponse(
            request,
            "emergency_desk.html",
            {
                **ctx,
                "display_name": request.session.get("admin_display_name")
                or request.session.get("admin_username")
                or "there",
            },
        )
