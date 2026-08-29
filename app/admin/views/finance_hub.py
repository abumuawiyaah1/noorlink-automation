from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.nav_catalog import FINANCE_CATEGORY
from app.admin.roles import ROLE_ADMIN, ROLE_FINANCE, ROLE_SUPPORT, has_role, session_role, session_username
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_document_vault import can_view_documents
from app.services.admin_finance import (
    build_finance_snapshot,
    build_finance_snapshot_support,
    export_commissions_csv,
    export_orders_csv,
)
from app.services.admin_monthly_summary import send_monthly_summary_email
from app.services.stripe_mode import stripe_mode_info


class FinanceHubView(BaseView):
    name = "Finance"
    icon = "fa-solid fa-chart-line"
    category = FINANCE_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT, ROLE_FINANCE))

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/finance", identity="finance-hub", methods=["GET", "POST"])
    async def hub(self, request: Request):
        days = int(request.query_params.get("days", "30"))
        read_only = not has_role(request, (ROLE_ADMIN,))
        summary = build_finance_snapshot_support(days=days) if read_only else build_finance_snapshot(days=days)

        if request.method == "POST" and not read_only:
            form = await request.form()
            if str(form.get("action")) == "send_summary":
                result = send_monthly_summary_email(days=days)
                if result.get("sent"):
                    request.session["flash_success"] = f"Summary emailed to {result['sent']} recipient(s)."
                else:
                    request.session["flash_error"] = result.get("error") or "Could not send summary."

        return await self.templates.TemplateResponse(
            request,
            "finance_hub.html",
            {
                "summary": summary,
                "days": days,
                "read_only": read_only,
                "show_documents": can_view_documents(session_role(request)),
                "stripe_mode": stripe_mode_info(),
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )

    @expose("/finance/export/orders.csv", identity="finance-export-orders", methods=["GET"])
    async def export_orders(self, request: Request):
        if not has_role(request, (ROLE_ADMIN,)):
            return RedirectResponse("/admin", status_code=302)
        days = int(request.query_params.get("days", "90"))
        return Response(
            content=export_orders_csv(days=days),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=noorlink-orders.csv"},
        )

    @expose("/finance/export/commissions.csv", identity="finance-export-commissions", methods=["GET"])
    async def export_commissions(self, request: Request):
        if not has_role(request, (ROLE_ADMIN,)):
            return RedirectResponse("/admin", status_code=302)
        return Response(
            content=export_commissions_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=noorlink-commissions.csv"},
        )
