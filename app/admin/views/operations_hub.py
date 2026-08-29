from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.nav_catalog import OPERATIONS_CATEGORY
from app.admin.roles import ALL_ROLES, ROLE_ADMIN, has_role, session_role, session_username
from app.admin.tools_catalog import tools_for_role
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_operations import get_operations_summary, run_admin_cron_tasks
from app.services.admin_scripts import ADMIN_SCRIPTS, AdminScriptError, run_admin_script
from app.services.admin_security import build_security_overview


class OperationsHubView(BaseView):
    name = "Operations"
    icon = "fa-solid fa-heart-pulse"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        role = session_role(request)
        return role in ALL_ROLES and bool(tools_for_role(role))

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/operations", identity="operations-hub", methods=["GET", "POST"])
    async def hub(self, request: Request):
        cron_result = None
        script_result = None
        script_key = None
        is_admin = has_role(request, (ROLE_ADMIN,))

        if request.method == "POST" and is_admin:
            form = await request.form()
            action = form.get("action")
            if action == "run_cron":
                cron_result = run_admin_cron_tasks()
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="run_cron_tasks",
                            table_name="system",
                            record_id="cron",
                            new_values={"success": cron_result.get("success")},
                            ip_address=_client_ip(request),
                        )
                if cron_result.get("success"):
                    request.session["flash_success"] = "Background tasks completed."
                else:
                    request.session["flash_error"] = "Some background tasks failed — see details below."
            elif action == "run_script":
                script_key = str(form.get("script_key") or "")
                try:
                    script_result = run_admin_script(script_key)
                    session_factory = get_session_factory()
                    if session_factory is not None:
                        with session_factory() as session:
                            write_audit_log(
                                session,
                                admin_user_id=request.session.get("admin_user_id"),
                                admin_username=session_username(request),
                                action="run_admin_script",
                                table_name="system",
                                record_id=script_key,
                                new_values={"ok": script_result.get("ok", True)},
                                ip_address=_client_ip(request),
                            )
                    request.session["flash_success"] = f"Script '{script_key}' completed."
                except AdminScriptError as exc:
                    request.session["flash_error"] = str(exc)

        summary = get_operations_summary()
        role = session_role(request)
        visible_tools = [t for t in tools_for_role(role) if t.key != "operations-hub"]
        security = build_security_overview(client_ip=_client_ip(request)) if is_admin else None

        return await self.templates.TemplateResponse(
            request,
            "operations_hub.html",
            {
                "summary": summary,
                "tools": visible_tools,
                "cron_result": cron_result,
                "script_result": script_result,
                "script_key": script_key,
                "admin_scripts": ADMIN_SCRIPTS if is_admin else [],
                "security": security,
                "can_run_cron": is_admin,
                "is_admin": is_admin,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
