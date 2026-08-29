from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import ROLE_ADMIN, has_role, session_username
from app.admin.views.base import _client_ip
from app.admin.wizard_catalog import WIZARD_CATEGORY
from app.db.engine import get_session_factory
from app.services.admin_complimentary_esim import (
    COMPLIMENTARY_REASONS,
    AdminComplimentaryError,
    grant_complimentary_esim,
    list_grantable_packages,
)


class ComplimentaryEsimView(BaseView):
    name = "Complimentary eSIM"
    icon = "fa-solid fa-gift"
    category = WIZARD_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN,))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/complimentary-esim", identity="complimentary-esim", methods=["GET", "POST"])
    async def grant_form(self, request: Request):
        if not has_role(request, (ROLE_ADMIN,)):
            request.session["flash_error"] = "Only admins can grant complimentary eSIMs."
            return RedirectResponse("/admin", status_code=302)

        if request.method == "POST":
            form = await request.form()
            package_id = str(form.get("package_id") or "").strip()
            recipient_email = str(form.get("recipient_email") or "").strip()
            recipient_name = str(form.get("recipient_name") or "").strip()
            reason = str(form.get("reason") or "staff").strip()
            note = str(form.get("note") or "").strip()

            try:
                result = grant_complimentary_esim(
                    package_id=package_id,
                    recipient_email=recipient_email,
                    recipient_name=recipient_name or None,
                    reason=reason,
                    note=note or None,
                    granted_by=session_username(request),
                )
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="grant_complimentary_esim",
                            table_name="orders",
                            record_id=result["order_number"],
                            new_values={
                                "email": result["email"],
                                "package_name": result["package_name"],
                                "reason": reason,
                                "status": result.get("status"),
                            },
                            ip_address=_client_ip(request),
                        )
                request.session["flash_success"] = (
                    f"Complimentary eSIM granted — order {result['order_number']} "
                    f"emailed to {result['email']}."
                )
                return RedirectResponse(
                    request.url_for("admin:complimentary-esim"),
                    status_code=302,
                )
            except AdminComplimentaryError as exc:
                request.session["flash_error"] = str(exc)

        try:
            packages = list_grantable_packages()
        except AdminComplimentaryError as exc:
            packages = []
            request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "complimentary_esim.html",
            {
                "packages": packages,
                "reasons": COMPLIMENTARY_REASONS,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
