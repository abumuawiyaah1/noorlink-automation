from __future__ import annotations

from datetime import date, timedelta

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import PROMO_MANAGER_ROLES, ROLE_ADMIN, has_role, session_username
from app.admin.views.base import _client_ip
from app.admin.wizard_catalog import WIZARD_CATEGORY
from app.db.engine import get_session_factory
from app.services.admin_promo_wizard import AdminPromoError, create_promo_from_wizard
from app.services.promo_codes import HIGH_DISCOUNT_APPROVAL_THRESHOLD


class PromoWizardView(BaseView):
    name = "Promo code wizard"
    icon = "fa-solid fa-tag"
    category = WIZARD_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, PROMO_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/promo-wizard", identity="promo-wizard", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        editor_is_admin = has_role(request, (ROLE_ADMIN,))
        form_values: dict[str, str] = {}
        default_start = date.today().isoformat()
        default_end = (date.today() + timedelta(days=30)).isoformat()

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            try:
                result = create_promo_from_wizard(
                    form=form_values,
                    editor_is_admin=editor_is_admin,
                    editor_username=session_username(request),
                )
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="create_promo_wizard",
                            table_name="promo_codes",
                            record_id=result["code"],
                            new_values=result,
                            ip_address=_client_ip(request),
                        )
                if result["admin_approved"]:
                    request.session["flash_success"] = (
                        f"Promo code {result['code']} is live and ready to use at checkout."
                    )
                else:
                    request.session["flash_success"] = (
                        f"Promo code {result['code']} saved. "
                        f"Codes above {HIGH_DISCOUNT_APPROVAL_THRESHOLD}% need admin approval "
                        "before customers can use them."
                    )
                return RedirectResponse(request.url_for("admin:promo-wizard"), status_code=302)
            except AdminPromoError as exc:
                request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "promo_wizard.html",
            {
                "form_values": form_values,
                "editor_is_admin": editor_is_admin,
                "default_start": default_start,
                "default_end": default_end,
                "approval_threshold": HIGH_DISCOUNT_APPROVAL_THRESHOLD,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
