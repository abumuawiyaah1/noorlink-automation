from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.roles import CATALOG_MANAGER_ROLES, ROLE_ADMIN, has_role
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.services.admin_diagnostics import (
    get_analytics_summary,
    get_email_diagnostics,
    search_provider_catalog,
)


class SystemDiagnosticsView(BaseView):
    name = "Diagnostics"
    icon = "fa-solid fa-stethoscope"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN,))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/diagnostics", identity="diagnostics", methods=["GET", "POST"])
    async def panel(self, request: Request):
        probe = request.query_params.get("probe") == "1"
        if request.method == "POST":
            form = await request.form()
            if str(form.get("action")) == "probe_email":
                probe = True

        email = get_email_diagnostics(probe=probe)
        analytics = get_analytics_summary()
        return await self.templates.TemplateResponse(
            request,
            "system_diagnostics.html",
            {"email": email, "analytics": analytics},
        )


class ProviderCatalogBrowserView(BaseView):
    name = "Provider SKUs"
    icon = "fa-solid fa-warehouse"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, CATALOG_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/provider-catalog", identity="provider-catalog", methods=["GET"])
    async def browse(self, request: Request):
        query = request.query_params.get("q", "")
        provider = request.query_params.get("provider", "")
        products = search_provider_catalog(query=query, provider=provider or None)
        return await self.templates.TemplateResponse(
            request,
            "provider_catalog_browser.html",
            {"products": products, "query": query, "provider": provider},
        )
