from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import PROMO_MANAGER_ROLES, has_role, session_username
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_newsletter import (
    AdminNewsletterError,
    admin_unsubscribe,
    export_subscribers_csv,
    list_subscriber_rows,
    subscriber_stats,
)


class NewsletterAdminView(BaseView):
    name = "Newsletter"
    icon = "fa-solid fa-users"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, PROMO_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/newsletter", identity="newsletter-admin", methods=["GET", "POST"])
    async def admin(self, request: Request):
        active_only = request.query_params.get("active") != "0"

        if request.method == "POST":
            form = await request.form()
            action = str(form.get("action") or "")
            if action == "unsubscribe":
                email = str(form.get("email") or "")
                try:
                    if admin_unsubscribe(email):
                        session_factory = get_session_factory()
                        if session_factory is not None:
                            with session_factory() as session:
                                write_audit_log(
                                    session,
                                    admin_user_id=request.session.get("admin_user_id"),
                                    admin_username=session_username(request),
                                    action="newsletter_unsubscribe",
                                    table_name="newsletter_subscribers",
                                    record_id=email,
                                    ip_address=_client_ip(request),
                                )
                        request.session["flash_success"] = f"Unsubscribed {email}."
                    else:
                        request.session["flash_error"] = f"No subscriber found for {email}."
                except AdminNewsletterError as exc:
                    request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:newsletter-admin"), status_code=302)

        subscribers = list_subscriber_rows(active_only=active_only)
        stats = subscriber_stats()
        return await self.templates.TemplateResponse(
            request,
            "newsletter_admin.html",
            {
                "subscribers": subscribers,
                "stats": stats,
                "active_only": active_only,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )

    @expose("/newsletter/export.csv", identity="newsletter-export", methods=["GET"])
    async def export_csv(self, request: Request):
        if not has_role(request, PROMO_MANAGER_ROLES):
            return RedirectResponse("/admin", status_code=302)
        active_only = request.query_params.get("active", "1") != "0"
        csv_text = export_subscribers_csv(active_only=active_only)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=noorlink-subscribers.csv"},
        )
