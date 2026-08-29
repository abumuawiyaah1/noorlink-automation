from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.roles import ROLE_ADMIN, has_role, session_username
from app.admin.tools_catalog import OPERATIONS_CATEGORY
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_affiliate_payout import (
    AdminAffiliatePayoutError,
    list_payout_candidates,
    record_affiliate_payout,
)
from app.services.affiliate_payout_requests import (
    AffiliatePayoutRequestError,
    acknowledge_payout_request,
    list_open_payout_requests,
)


class AffiliatePayoutWizardView(BaseView):
    name = "Affiliate payout"
    icon = "fa-solid fa-money-bill-transfer"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN,))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/affiliate-payout", identity="affiliate-payout", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        form_values: dict[str, str] = {}
        candidates = list_payout_candidates()
        open_requests = list_open_payout_requests()

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            action = (form_values.get("action") or "record").strip().lower()

            if action == "acknowledge":
                try:
                    acknowledge_payout_request(
                        request_id=form_values.get("request_id", ""),
                        attended_by=session_username(request) or "admin",
                    )
                    request.session["flash_success"] = (
                        "Marked as attended — 72h auto-approve will not run. "
                        "Send funds, then record payout below."
                    )
                except AffiliatePayoutRequestError as exc:
                    request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:affiliate-payout"), status_code=302)

            try:
                result = record_affiliate_payout(
                    affiliate_id=form_values.get("affiliate_id", ""),
                    method=form_values.get("method", "manual"),
                    reference=form_values.get("reference", ""),
                    notes=form_values.get("notes", ""),
                )
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="affiliate_payout_wizard",
                            table_name="affiliate_payouts",
                            record_id=result["payout_id"],
                            new_values=result,
                            ip_address=_client_ip(request),
                        )
                request.session["flash_success"] = (
                    f"Recorded ${result['amount_cents'] / 100:.2f} payout for "
                    f"{result['affiliate_code']} ({result['commission_count']} commissions)."
                )
                return RedirectResponse(request.url_for("admin:affiliate-payout"), status_code=302)
            except AdminAffiliatePayoutError as exc:
                request.session["flash_error"] = str(exc)
            candidates = list_payout_candidates()
            open_requests = list_open_payout_requests()

        return await self.templates.TemplateResponse(
            request,
            "affiliate_payout_wizard.html",
            {
                "candidates": candidates,
                "open_requests": open_requests,
                "form_values": form_values,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
