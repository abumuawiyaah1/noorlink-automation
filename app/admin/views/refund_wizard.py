from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.nav_catalog import FINANCE_CATEGORY
from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role, session_username
from app.admin.views.base import _client_ip
from app.api import supabase_repository as db
from app.db.engine import get_session_factory
from app.services.admin_refunds import AdminRefundError, REFUND_USAGE_THRESHOLD_PCT, process_order_refund


def _stripe_dashboard_url(payment_intent_id: str) -> str:
    pid = (payment_intent_id or "").strip()
    if not pid:
        return ""
    if pid.startswith("pi_"):
        return f"https://dashboard.stripe.com/payments/{pid}"
    return f"https://dashboard.stripe.com/search?query={pid}"


class RefundWizardView(BaseView):
    name = "Refund order"
    icon = "fa-solid fa-rotate-left"
    category = FINANCE_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/refund-order", identity="refund-order", methods=["GET", "POST"])
    async def wizard(self, request: Request):
        form_values: dict[str, str] = {}
        editor_is_admin = has_role(request, (ROLE_ADMIN,))

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            try:
                result = process_order_refund(
                    order_number=form_values.get("order_number", ""),
                    reason=form_values.get("reason", "customer_request"),
                    admin_username=session_username(request),
                    admin_override=editor_is_admin
                    and str(form.get("admin_override") or "").lower() in {"1", "on", "true"},
                )
                session_factory = get_session_factory()
                if session_factory is not None:
                    with session_factory() as session:
                        write_audit_log(
                            session,
                            admin_user_id=request.session.get("admin_user_id"),
                            admin_username=session_username(request),
                            action="refund_order",
                            table_name="orders",
                            record_id=result["order_number"],
                            new_values=result,
                            ip_address=_client_ip(request),
                        )
                request.session["flash_success"] = (
                    f"Refunded ${result['amount_cents'] / 100:.2f} for {result['order_number']}."
                )
                return RedirectResponse(request.url_for("admin:refund-order"), status_code=302)
            except AdminRefundError as exc:
                request.session["flash_error"] = str(exc)

        order_preview = None
        stripe_url = ""
        lookup = (request.query_params.get("order") or form_values.get("order_number") or "").strip().upper()
        if lookup:
            try:
                row = db.get_order_row_by_order_number(lookup)
            except db.SupabaseRepositoryError:
                row = None
            if row:
                order_preview = {
                    "order_number": row.get("order_number"),
                    "email": row.get("email"),
                    "status": row.get("status"),
                    "amount_cents": row.get("amount_cents"),
                    "data_used_gb": row.get("data_used_gb"),
                    "data_total_gb": row.get("data_total_gb"),
                }
                stripe_url = _stripe_dashboard_url(str(row.get("stripe_payment_intent_id") or ""))

        return await self.templates.TemplateResponse(
            request,
            "refund_wizard.html",
            {
                "form_values": form_values,
                "editor_is_admin": editor_is_admin,
                "usage_threshold": REFUND_USAGE_THRESHOLD_PCT,
                "order_preview": order_preview,
                "stripe_url": stripe_url,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
