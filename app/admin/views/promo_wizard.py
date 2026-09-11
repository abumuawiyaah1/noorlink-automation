from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose
from sqlalchemy import select

from app.admin.audit import write_audit_log
from app.admin.roles import PROMO_MANAGER_ROLES, ROLE_ADMIN, has_role, session_username
from app.admin.views.base import _client_ip
from app.admin.wizard_catalog import WIZARD_CATEGORY
from app.db.engine import get_session_factory
from app.db.models import PromoCode
from app.services.admin_promo_wizard import AdminPromoError, create_promo_from_wizard
from app.services.email_service import EmailDeliveryError, send_promo_share_email
from app.services.promo_codes import HIGH_DISCOUNT_APPROVAL_THRESHOLD, normalize_code
from app.services.promo_share import share_context_for_code, whatsapp_share_url


def _load_share_context(code: str) -> Optional[Dict[str, Any]]:
    normalized = normalize_code(code)
    if not normalized:
        return None
    factory = get_session_factory()
    if factory is None:
        return share_context_for_code(code=normalized)
    with factory() as session:
        promo = session.scalar(select(PromoCode).where(PromoCode.code == normalized))
        if promo is None:
            return None
        return share_context_for_code(
            code=promo.code,
            percent_off=promo.percent_off,
            amount_off_cents=promo.amount_off_cents,
            admin_approved=bool(promo.admin_approved),
        )


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
        share: Optional[Dict[str, Any]] = None

        if request.method == "POST":
            form = await request.form()
            form_values = {key: str(form.get(key) or "") for key in form.keys()}
            action = str(form.get("action") or "create").strip().lower()

            if action == "load_share":
                code = normalize_code(str(form.get("share_code") or ""))
                share = _load_share_context(code)
                if share is None:
                    request.session["flash_error"] = f"Promo code not found: {code or '—'}"
                else:
                    return RedirectResponse(
                        f"{request.url_for('admin:promo-wizard')}?share={quote(share['code'])}",
                        status_code=302,
                    )

            elif action == "share_email":
                code = normalize_code(str(form.get("code") or ""))
                to_email = str(form.get("to_email") or "").strip()
                link_key = str(form.get("link_key") or "destinations").strip()
                share = _load_share_context(code)
                if share is None:
                    request.session["flash_error"] = "Promo code not found."
                elif not to_email or "@" not in to_email:
                    request.session["flash_error"] = "Enter a valid email address."
                    return RedirectResponse(
                        f"{request.url_for('admin:promo-wizard')}?share={quote(code)}",
                        status_code=302,
                    )
                else:
                    links = {row["key"]: row["url"] for row in share["links"]}
                    share_url = links.get(link_key) or share["primary_url"]
                    try:
                        send_promo_share_email(
                            to_email=to_email,
                            code=share["code"],
                            share_url=share_url,
                            percent_off=share.get("percent_off"),
                            amount_off_cents=share.get("amount_off_cents"),
                        )
                        session_factory = get_session_factory()
                        if session_factory is not None:
                            with session_factory() as session:
                                write_audit_log(
                                    session,
                                    admin_user_id=request.session.get("admin_user_id"),
                                    admin_username=session_username(request),
                                    action="share_promo_email",
                                    table_name="promo_codes",
                                    record_id=share["code"],
                                    new_values={"to_email": to_email, "share_url": share_url},
                                    ip_address=_client_ip(request),
                                )
                        request.session["flash_success"] = (
                            f"Offer email for {share['code']} sent to {to_email}."
                        )
                    except EmailDeliveryError as exc:
                        request.session["flash_error"] = str(exc)
                    return RedirectResponse(
                        f"{request.url_for('admin:promo-wizard')}?share={quote(code)}",
                        status_code=302,
                    )

            else:
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
                            f"Promo code {result['code']} is live. "
                            "Copy a ready link below, or send it by email / WhatsApp."
                        )
                    else:
                        request.session["flash_success"] = (
                            f"Promo code {result['code']} saved. "
                            f"Codes above {HIGH_DISCOUNT_APPROVAL_THRESHOLD}% need admin approval "
                            "before customers can use them — you can still prepare share links."
                        )
                    return RedirectResponse(
                        f"{request.url_for('admin:promo-wizard')}?share={quote(result['code'])}",
                        status_code=302,
                    )
                except AdminPromoError as exc:
                    request.session["flash_error"] = str(exc)

        share_code = normalize_code(request.query_params.get("share") or "")
        if share_code:
            share = _load_share_context(share_code)
            if share is None and request.method == "GET":
                request.session["flash_error"] = f"Promo code not found: {share_code}"

        # Optional WhatsApp phone from query (for button refresh)
        if share is not None:
            wa_phone = str(request.query_params.get("wa") or "").strip()
            if wa_phone:
                share = {
                    **share,
                    "whatsapp_url": whatsapp_share_url(
                        message=share["message"],
                        phone=wa_phone,
                    ),
                    "wa_phone": wa_phone,
                }

        return await self.templates.TemplateResponse(
            request,
            "promo_wizard.html",
            {
                "form_values": form_values,
                "editor_is_admin": editor_is_admin,
                "default_start": default_start,
                "default_end": default_end,
                "approval_threshold": HIGH_DISCOUNT_APPROVAL_THRESHOLD,
                "share": share,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
