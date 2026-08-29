from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.roles import CATALOG_MANAGER_ROLES, has_role
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.services.admin_catalog_overview import build_catalog_overview


class CatalogOverviewView(BaseView):
    name = "Catalog overview"
    icon = "fa-solid fa-layer-group"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, CATALOG_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/catalog-overview", identity="catalog-overview", methods=["GET"])
    async def overview(self, request: Request):
        country = request.query_params.get("country", "")
        data = build_catalog_overview(country_filter=country)
        return await self.templates.TemplateResponse(
            request,
            "catalog_overview.html",
            {"data": data, "country_filter": country},
        )
