from __future__ import annotations

import uuid

from sqladmin import action
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.admin.audit import write_audit_log
from app.admin.roles import (
    PROMO_MANAGER_ROLES,
    ROLE_ADMIN,
    ROLE_CATALOG,
    ROLE_MARKETING,
    ROLE_SUPPORT,
    has_role,
    session_username,
)
from app.admin.views.base import AuditedModelView, _client_ip
from app.db.engine import get_session_factory
from app.db.models import InsiderIssue, Order, PromoCode
from app.services.admin_orders import AdminOrderError, resend_order_esim_email
from app.services.admin_promo_codes import (
    AdminPromoError,
    apply_promo_approval_rules,
    approve_high_discount_promo,
    days_remaining,
    extend_promo_end,
    promo_status_label,
    set_promo_active,
    validate_promo_payload,
)
from app.services.promo_codes import HIGH_DISCOUNT_APPROVAL_THRESHOLD, requires_admin_approval


def _order_model_to_row(order: Order) -> dict:
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "email": order.email,
        "country": order.country,
        "flag_emoji": order.flag_emoji,
        "package_name": order.package_name,
        "amount_cents": order.amount_cents,
        "status": order.status,
        "iccid": order.iccid,
        "data_used_gb": float(order.data_used_gb) if order.data_used_gb is not None else None,
        "data_total_gb": float(order.data_total_gb) if order.data_total_gb is not None else None,
        "metadata": order.metadata_ or {},
    }


class OrderAdmin(AuditedModelView, model=Order):
    name = "Order"
    name_plural = "Orders"
    icon = "fa-solid fa-receipt"
    allowed_roles = (ROLE_ADMIN, ROLE_SUPPORT)

    can_create = False
    can_delete = False
    can_edit = False

    column_list = [
        Order.order_number,
        Order.email,
        Order.country,
        Order.package_name,
        Order.amount_cents,
        Order.status,
        Order.data_used_gb,
        Order.iccid,
        Order.paid_at,
        Order.fulfilled_at,
        Order.created_at,
    ]
    column_searchable_list = [Order.order_number, Order.email, Order.country, Order.package_name]
    column_sortable_list = [Order.created_at, Order.paid_at, Order.amount_cents, Order.status]
    column_filters = [Order.status, Order.country]
    column_default_sort = [(Order.created_at, True)]
    column_details_list = [
        Order.order_number,
        Order.email,
        Order.country,
        Order.flag_emoji,
        Order.package_name,
        Order.amount_cents,
        Order.currency,
        Order.status,
        Order.travel_date,
        Order.stripe_checkout_session_id,
        Order.stripe_payment_intent_id,
        Order.qr_code_url,
        Order.activation_code,
        Order.iccid,
        Order.paid_at,
        Order.fulfilled_at,
        Order.refunded_at,
        Order.metadata_,
        Order.created_at,
        Order.updated_at,
    ]

    @action(
        name="resend_esim_email",
        label="Resend eSIM email",
        confirmation_message="Send the QR / activation email again to the customer?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def resend_esim_email(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        session_factory = get_session_factory()
        if session_factory is None:
            request.session["flash_error"] = "Database not configured."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        sent = 0
        errors: list[str] = []
        with session_factory() as session:
            for pk in pks:
                pk = pk.strip()
                if not pk:
                    continue
                order = session.get(Order, uuid.UUID(pk))
                if order is None:
                    errors.append(f"Order {pk} not found")
                    continue
                try:
                    message_id = resend_order_esim_email(order.as_resend_dict())
                    sent += 1
                    write_audit_log(
                        session,
                        admin_user_id=request.session.get("admin_user_id"),
                        admin_username=session_username(request),
                        action="resend_esim_email",
                        table_name="orders",
                        record_id=order.order_number,
                        new_values={"message_id": message_id, "recipient": order.email},
                        ip_address=_client_ip(request),
                    )
                except AdminOrderError as exc:
                    errors.append(f"{order.order_number}: {exc}")

        if sent:
            request.session["flash_success"] = f"Resent eSIM email for {sent} order(s)."
        if errors:
            request.session["flash_error"] = "; ".join(errors[:3])

        referer = request.headers.get("referer")
        if referer:
            return RedirectResponse(referer, status_code=302)
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

    @action(
        name="refresh_usage",
        label="Refresh usage",
        confirmation_message="Pull live activation / data usage from the provider?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def refresh_usage(self, request: Request):
        from app.services.esim_usage_sync import UsageSyncError, sync_order_usage_blocking

        pks = request.query_params.get("pks", "").split(",")
        session_factory = get_session_factory()
        if session_factory is None:
            request.session["flash_error"] = "Database not configured."
            return RedirectResponse(request.headers.get("referer") or "/", status_code=302)

        refreshed = 0
        errors: list[str] = []
        with session_factory() as session:
            for pk in pks:
                pk = pk.strip()
                if not pk:
                    continue
                order = session.get(Order, uuid.UUID(pk))
                if order is None:
                    errors.append(f"Order {pk} not found")
                    continue
                try:
                    sync_order_usage_blocking(_order_model_to_row(order), source="admin")
                    refreshed += 1
                    write_audit_log(
                        session,
                        admin_user_id=request.session.get("admin_user_id"),
                        admin_username=session_username(request),
                        action="refresh_usage",
                        table_name="orders",
                        record_id=order.order_number,
                        ip_address=_client_ip(request),
                    )
                except UsageSyncError as exc:
                    errors.append(f"{order.order_number}: {exc}")

        if refreshed:
            request.session["flash_success"] = f"Refreshed usage for {refreshed} order(s)."
        if errors:
            request.session["flash_error"] = "; ".join(errors[:3])

        referer = request.headers.get("referer")
        return RedirectResponse(referer or request.url_for("admin:list", identity=self.identity), status_code=302)

    async def _fund_topup_action(self, request: Request, fund_usd: float) -> RedirectResponse:
        from app.services.esim_topup import TopUpError, fund_citrus_topup_blocking

        pks = request.query_params.get("pks", "").split(",")
        session_factory = get_session_factory()
        if session_factory is None:
            request.session["flash_error"] = "Database not configured."
            return RedirectResponse(request.headers.get("referer") or "/", status_code=302)

        funded = 0
        errors: list[str] = []
        with session_factory() as session:
            for pk in pks:
                pk = pk.strip()
                if not pk:
                    continue
                order = session.get(Order, uuid.UUID(pk))
                if order is None:
                    continue
                try:
                    fund_citrus_topup_blocking(
                        _order_model_to_row(order),
                        fund_usd,
                        source="admin",
                        actor=session_username(request),
                    )
                    funded += 1
                    write_audit_log(
                        session,
                        admin_user_id=request.session.get("admin_user_id"),
                        admin_username=session_username(request),
                        action="fund_topup",
                        table_name="orders",
                        record_id=order.order_number,
                        new_values={"fund_usd": fund_usd},
                        ip_address=_client_ip(request),
                    )
                except TopUpError as exc:
                    errors.append(f"{order.order_number}: {exc}")

        if funded:
            request.session["flash_success"] = f"Added ${fund_usd:.0f} data to {funded} eSIM(s)."
        if errors:
            request.session["flash_error"] = "; ".join(errors[:3])

        referer = request.headers.get("referer")
        return RedirectResponse(referer or request.url_for("admin:list", identity=self.identity), status_code=302)

    @action(
        name="fund_topup_10",
        label="Fund +$10 data",
        confirmation_message="Add $10 wholesale data to this Citrus eSIM?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def fund_topup_10(self, request: Request):
        return await self._fund_topup_action(request, 10.0)

    @action(
        name="fund_topup_20",
        label="Fund +$20 data",
        confirmation_message="Add $20 wholesale data to this Citrus eSIM?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def fund_topup_20(self, request: Request):
        return await self._fund_topup_action(request, 20.0)

    @action(
        name="view_support_inbox",
        label="Support thread",
        confirmation_message="Open the email thread for this order?",
        add_in_detail=True,
        add_in_list=False,
    )
    async def view_support_inbox(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        session_factory = get_session_factory()
        if session_factory is None:
            return RedirectResponse(request.headers.get("referer") or "/admin", status_code=302)

        with session_factory() as session:
            for pk in pks:
                pk = pk.strip()
                if not pk:
                    continue
                order = session.get(Order, uuid.UUID(pk))
                if order is None:
                    continue
                from app.services.support_messaging import list_tickets_for_order

                tickets = list_tickets_for_order(order.order_number)
                if tickets:
                    return RedirectResponse(
                        f"/admin/support-inbox/{tickets[0].ticket_number}",
                        status_code=302,
                    )

        request.session["flash_error"] = "No support thread linked to this order yet."
        referer = request.headers.get("referer")
        return RedirectResponse(referer or "/admin/order/list", status_code=302)

    @action(
        name="order_insight",
        label="Customer context",
        confirmation_message="Open gift, reminders, and breakage details?",
        add_in_detail=True,
        add_in_list=False,
    )
    async def order_insight(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        session_factory = get_session_factory()
        if session_factory is None:
            return RedirectResponse("/admin", status_code=302)
        with session_factory() as session:
            for pk in pks:
                pk = pk.strip()
                if not pk:
                    continue
                order = session.get(Order, uuid.UUID(pk))
                if order is None:
                    continue
                return RedirectResponse(
                    f"/admin/order-insight?order={order.order_number}",
                    status_code=302,
                )
        return RedirectResponse(request.headers.get("referer") or "/admin", status_code=302)


def _format_promo_status(model: PromoCode, _name) -> str:
    return promo_status_label(
        is_active=model.is_active,
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        percent_off=model.percent_off,
        admin_approved=model.admin_approved,
    )


def _format_promo_ends(model: PromoCode, _name) -> str:
    if not model.is_active:
        return "—"
    remaining = days_remaining(model.ends_at)
    label = promo_status_label(
        is_active=model.is_active,
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        percent_off=model.percent_off,
        admin_approved=model.admin_approved,
    )
    if label == "Expired":
        remaining = 0
    end = model.ends_at.strftime("%Y-%m-%d") if model.ends_at else ""
    return f"{end} ({remaining}d left)"


class PromoCodeAdmin(AuditedModelView, model=PromoCode):
    name = "Promo Code"
    name_plural = "Promo Codes"
    icon = "fa-solid fa-tag"
    category = "Marketing"
    allowed_roles = PROMO_MANAGER_ROLES

    can_delete = False
    page_size = 50

    column_list = [
        PromoCode.code,
        PromoCode.label,
        PromoCode.is_active,
        PromoCode.percent_off,
        PromoCode.admin_approved,
        PromoCode.admin_approved_by,
        PromoCode.starts_at,
        PromoCode.ends_at,
        PromoCode.redemption_count,
    ]
    column_searchable_list = [PromoCode.code, PromoCode.label, PromoCode.insider_issue_slug]
    column_filters = [PromoCode.is_active, PromoCode.admin_approved]
    column_sortable_list = [
        PromoCode.code,
        PromoCode.ends_at,
        PromoCode.starts_at,
        PromoCode.redemption_count,
        PromoCode.percent_off,
    ]
    column_default_sort = [(PromoCode.ends_at, True)]
    column_details_list = [
        PromoCode.code,
        PromoCode.label,
        PromoCode.percent_off,
        PromoCode.amount_off_cents,
        PromoCode.starts_at,
        PromoCode.ends_at,
        PromoCode.is_active,
        PromoCode.admin_approved,
        PromoCode.admin_approved_by,
        PromoCode.admin_approved_at,
        PromoCode.max_redemptions,
        PromoCode.redemption_count,
        PromoCode.min_order_cents,
        PromoCode.insider_issue_slug,
        PromoCode.created_at,
    ]

    form_columns = [
        PromoCode.code,
        PromoCode.label,
        PromoCode.percent_off,
        PromoCode.amount_off_cents,
        PromoCode.starts_at,
        PromoCode.ends_at,
        PromoCode.is_active,
        PromoCode.max_redemptions,
        PromoCode.min_order_cents,
        PromoCode.insider_issue_slug,
    ]
    form_widget_args = {
        "code": {"placeholder": "SUMMER10"},
        "label": {"placeholder": "Summer sale"},
        "percent_off": {"placeholder": "10 — codes above 20% need admin approval"},
        "amount_off_cents": {"placeholder": "500 = $5.00 off — leave blank if using percent"},
        "max_redemptions": {"placeholder": "Empty = unlimited"},
        "min_order_cents": {"placeholder": "0 = no minimum"},
        "insider_issue_slug": {"placeholder": "Optional Insider issue slug"},
    }

    column_labels = {
        PromoCode.is_active: "Status",
        PromoCode.ends_at: "Ends (days left)",
        PromoCode.percent_off: "% off",
        PromoCode.admin_approved: "Approved",
        PromoCode.admin_approved_by: "Approved by",
        PromoCode.amount_off_cents: "Amount off (¢)",
        PromoCode.min_order_cents: "Min order (¢)",
    }

    column_formatters = {
        PromoCode.is_active: _format_promo_status,
        PromoCode.ends_at: _format_promo_ends,
    }

    async def on_model_change(self, data: dict, model: PromoCode, is_created: bool, request: Request) -> None:
        if not has_role(request, PROMO_MANAGER_ROLES):
            raise ValueError("You do not have permission to edit promo codes.")
        try:
            validated = validate_promo_payload(data, is_create=is_created)
        except AdminPromoError as exc:
            raise ValueError(str(exc)) from exc
        apply_promo_approval_rules(
            validated,
            is_create=is_created,
            editor_is_admin=has_role(request, (ROLE_ADMIN,)),
            editor_username=session_username(request),
            existing=None if is_created else model,
        )
        data.clear()
        data.update(validated)
        if is_created and not data.get("id"):
            data["id"] = uuid.uuid4()
        pending_approval = (
            requires_admin_approval(validated.get("percent_off"))
            and not validated.get("admin_approved")
            and not has_role(request, (ROLE_ADMIN,))
        )
        if pending_approval:
            request.session["flash_success"] = (
                f"Promo saved. Codes above {HIGH_DISCOUNT_APPROVAL_THRESHOLD}% "
                "require admin approval before checkout."
            )

    @action(
        name="disable_promos",
        label="Disable",
        confirmation_message="Disable selected promo codes? They will stop working at checkout immediately.",
        add_in_list=True,
    )
    async def disable_promos(self, request: Request):
        return await self._bulk_set_active(request, active=False)

    @action(
        name="enable_promos",
        label="Enable",
        confirmation_message="Re-enable selected promo codes?",
        add_in_list=True,
    )
    async def enable_promos(self, request: Request):
        return await self._bulk_set_active(request, active=True)

    @action(
        name="approve_high_discount",
        label="Approve (>20%)",
        confirmation_message="Approve selected high-discount promo codes for checkout use?",
        add_in_list=True,
    )
    async def approve_high_discount(self, request: Request):
        if not has_role(request, (ROLE_ADMIN,)):
            request.session["flash_error"] = "Only admins can approve high-discount promo codes."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        pks = [pk.strip() for pk in request.query_params.get("pks", "").split(",") if pk.strip()]
        session_factory = get_session_factory()
        if session_factory is None:
            request.session["flash_error"] = "Database not configured."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        approved = 0
        skipped = 0
        username = session_username(request)
        with session_factory() as session:
            for pk in pks:
                promo = session.get(PromoCode, uuid.UUID(pk))
                if promo is None:
                    continue
                if not requires_admin_approval(promo.percent_off):
                    skipped += 1
                    continue
                approve_high_discount_promo(promo, admin_username=username)
                approved += 1
                write_audit_log(
                    session,
                    admin_user_id=request.session.get("admin_user_id"),
                    admin_username=username,
                    action="approve_promo",
                    table_name="promo_codes",
                    record_id=promo.code,
                    new_values={
                        "percent_off": promo.percent_off,
                        "admin_approved_by": username,
                    },
                    ip_address=_client_ip(request),
                )
            session.commit()

        if approved:
            request.session["flash_success"] = f"Approved {approved} high-discount promo code(s)."
        elif skipped:
            request.session["flash_error"] = "Selected codes are not above 20% or were already approved."
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

    @action(
        name="extend_7_days",
        label="Extend +7 days",
        confirmation_message="Add 7 days to the end date for selected promos?",
        add_in_list=True,
    )
    async def extend_7_days(self, request: Request):
        return await self._bulk_extend(request, days=7)

    @action(
        name="extend_30_days",
        label="Extend +30 days",
        confirmation_message="Add 30 days to the end date for selected promos?",
        add_in_list=True,
    )
    async def extend_30_days(self, request: Request):
        return await self._bulk_extend(request, days=30)

    async def _bulk_set_active(self, request: Request, *, active: bool) -> RedirectResponse:
        if not has_role(request, PROMO_MANAGER_ROLES):
            request.session["flash_error"] = "You do not have permission to change promo codes."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        pks = [pk.strip() for pk in request.query_params.get("pks", "").split(",") if pk.strip()]
        session_factory = get_session_factory()
        if session_factory is None:
            request.session["flash_error"] = "Database not configured."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        changed = 0
        with session_factory() as session:
            for pk in pks:
                promo = session.get(PromoCode, uuid.UUID(pk))
                if promo is None:
                    continue
                set_promo_active(promo, active=active)
                changed += 1
                write_audit_log(
                    session,
                    admin_user_id=request.session.get("admin_user_id"),
                    admin_username=session_username(request),
                    action="disable_promo" if not active else "enable_promo",
                    table_name="promo_codes",
                    record_id=promo.code,
                    new_values={"is_active": active},
                    ip_address=_client_ip(request),
                )
            session.commit()

        verb = "Disabled" if not active else "Enabled"
        request.session["flash_success"] = f"{verb} {changed} promo code(s)."
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

    async def _bulk_extend(self, request: Request, *, days: int) -> RedirectResponse:
        if not has_role(request, PROMO_MANAGER_ROLES):
            request.session["flash_error"] = "You do not have permission to change promo codes."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        pks = [pk.strip() for pk in request.query_params.get("pks", "").split(",") if pk.strip()]
        session_factory = get_session_factory()
        if session_factory is None:
            request.session["flash_error"] = "Database not configured."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        changed = 0
        with session_factory() as session:
            for pk in pks:
                promo = session.get(PromoCode, uuid.UUID(pk))
                if promo is None:
                    continue
                new_end = extend_promo_end(promo, days=days)
                changed += 1
                write_audit_log(
                    session,
                    admin_user_id=request.session.get("admin_user_id"),
                    admin_username=session_username(request),
                    action="extend_promo",
                    table_name="promo_codes",
                    record_id=promo.code,
                    new_values={"ends_at": new_end.isoformat(), "days_added": days},
                    ip_address=_client_ip(request),
                )
            session.commit()

        request.session["flash_success"] = f"Extended {changed} promo code(s) by {days} days."
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)


class InsiderIssueAdmin(AuditedModelView, model=InsiderIssue):
    name = "Insider Issue"
    name_plural = "Insider Issues"
    icon = "fa-solid fa-envelope-open-text"
    category = "Marketing"
    allowed_roles = (ROLE_ADMIN, ROLE_CATALOG, ROLE_MARKETING)

    can_create = False
    can_delete = False

    column_list = [
        InsiderIssue.slug,
        InsiderIssue.subject,
        InsiderIssue.promo_code,
        InsiderIssue.send_at,
        InsiderIssue.status,
        InsiderIssue.sent_at,
    ]
    column_searchable_list = [InsiderIssue.slug, InsiderIssue.subject]
    column_filters = [InsiderIssue.status]
    column_default_sort = [(InsiderIssue.send_at, True)]

    form_columns = [
        InsiderIssue.subject,
        InsiderIssue.preview,
        InsiderIssue.hero_image_url,
        InsiderIssue.web_path,
        InsiderIssue.promo_code,
        InsiderIssue.send_at,
        InsiderIssue.status,
    ]
