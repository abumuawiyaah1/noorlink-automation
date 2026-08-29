from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.nav_catalog import INSIGHTS_CATEGORY, OPERATIONS_CATEGORY
from app.admin.roles import ROLE_ADMIN, has_role, session_username
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_business_metrics import build_business_metrics
from app.services.admin_gdpr import AdminGdprError, delete_customer_data, export_customer_data
from app.services.admin_provider_health import build_provider_health, run_provider_probes


class InsightsHubView(BaseView):
    name = "Insights"
    icon = "fa-solid fa-chart-pie"
    category = INSIGHTS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN,))

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/insights", identity="insights-hub", methods=["GET", "POST"])
    async def hub(self, request: Request):
        days = int(request.query_params.get("days", "30"))
        metrics = build_business_metrics(days=days)
        providers = build_provider_health()
        probe_result = None

        if request.method == "POST":
            form = await request.form()
            if str(form.get("action")) == "probe_providers":
                import asyncio

                loop = asyncio.new_event_loop()
                try:
                    probe_result = loop.run_until_complete(run_provider_probes())
                finally:
                    loop.close()

        return await self.templates.TemplateResponse(
            request,
            "insights_hub.html",
            {
                "metrics": metrics,
                "providers": providers,
                "probe_result": probe_result,
                "days": days,
            },
        )


class GdprToolsView(BaseView):
    name = "Privacy tools"
    icon = "fa-solid fa-user-shield"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN,))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/gdpr", identity="gdpr-tools", methods=["GET", "POST"])
    async def tools(self, request: Request):
        if request.method == "POST":
            form = await request.form()
            action = str(form.get("action") or "")
            email = str(form.get("email") or "")
            try:
                if action == "export":
                    data = export_customer_data(
                        email=email,
                        admin_username=session_username(request),
                    )
                    return Response(
                        content=data,
                        media_type="application/json",
                        headers={
                            "Content-Disposition": f"attachment; filename=gdpr-export-{email.split('@')[0]}.json"
                        },
                    )
                if action == "delete":
                    result = delete_customer_data(
                        email=email,
                        admin_username=session_username(request),
                        confirm=str(form.get("confirm") or "").lower() in {"1", "on", "true"},
                    )
                    session_factory = get_session_factory()
                    if session_factory is not None:
                        with session_factory() as session:
                            write_audit_log(
                                session,
                                admin_user_id=request.session.get("admin_user_id"),
                                admin_username=session_username(request),
                                action="gdpr_delete",
                                table_name="gdpr_requests",
                                record_id=email,
                                new_values=result,
                                ip_address=_client_ip(request),
                            )
                    request.session["flash_success"] = f"Redacted data for {email}."
                    return RedirectResponse(request.url_for("admin:gdpr-tools"), status_code=302)
            except AdminGdprError as exc:
                request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:gdpr-tools"), status_code=302)

        return await self.templates.TemplateResponse(
            request,
            "gdpr_tools.html",
            {
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
