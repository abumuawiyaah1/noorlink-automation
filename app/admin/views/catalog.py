from __future__ import annotations

import uuid

from sqladmin import action
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.admin.audit import write_audit_log
from app.admin.roles import (
    CATALOG_MANAGER_ROLES,
    ROLE_ADMIN,
    has_role,
    session_username,
)
from app.admin.views.base import AuditedModelView, _client_ip
from app.db.engine import get_session_factory
from app.db.models import EsimPackage, PlanFulfillmentMap
from app.services.admin_catalog import (
    AdminCatalogError,
    apply_fulfillment_approval_rules,
    apply_package_approval_rules,
    approve_catalog_package,
    approve_fulfillment_map,
    is_known_provider,
    package_sale_status,
    validate_fulfillment_map_payload,
    validate_package_payload,
)


def _format_package_sale(model: EsimPackage, _name) -> str:
    return package_sale_status(
        is_active=model.is_active,
        admin_approved=model.admin_approved,
        pending_price_cents=model.pending_price_cents,
    )


def _format_package_price(model: EsimPackage, _name) -> str:
    base = f"${model.price_cents / 100:.2f}"
    if model.pending_price_cents is not None:
        return f"{base} → ${model.pending_price_cents / 100:.2f} pending"
    return base


def _format_map_provider(model: PlanFulfillmentMap, _name) -> str:
    provider = model.provider or ""
    if not model.admin_approved:
        suffix = " (pending approval)"
    elif not is_known_provider(provider):
        suffix = " (new provider)"
    else:
        suffix = ""
    return f"{provider}{suffix}"


class EsimPackageAdmin(AuditedModelView, model=EsimPackage):
    name = "eSIM Package"
    name_plural = "eSIM Plans"
    icon = "fa-solid fa-sim-card"
    category = "Catalog"
    allowed_roles = CATALOG_MANAGER_ROLES

    can_delete = False
    page_size = 50

    column_list = [
        EsimPackage.slug,
        EsimPackage.name,
        EsimPackage.country,
        EsimPackage.data_label,
        EsimPackage.price_cents,
        EsimPackage.is_active,
        EsimPackage.admin_approved,
        EsimPackage.pending_price_cents,
        EsimPackage.sort_order,
    ]
    column_searchable_list = [EsimPackage.slug, EsimPackage.name, EsimPackage.country]
    column_sortable_list = [
        EsimPackage.sort_order,
        EsimPackage.price_cents,
        EsimPackage.country,
        EsimPackage.created_at,
    ]
    column_filters = [EsimPackage.is_active, EsimPackage.admin_approved, EsimPackage.country]
    column_default_sort = [(EsimPackage.sort_order, False)]
    column_details_list = [
        EsimPackage.slug,
        EsimPackage.name,
        EsimPackage.country,
        EsimPackage.country_code,
        EsimPackage.region,
        EsimPackage.data_label,
        EsimPackage.data_total_gb,
        EsimPackage.validity_days,
        EsimPackage.price_cents,
        EsimPackage.pending_price_cents,
        EsimPackage.currency,
        EsimPackage.is_active,
        EsimPackage.admin_approved,
        EsimPackage.admin_approved_by,
        EsimPackage.admin_approved_at,
        EsimPackage.provider_sku,
        EsimPackage.stripe_price_id,
        EsimPackage.is_managed,
        EsimPackage.is_featured,
        EsimPackage.created_at,
        EsimPackage.updated_at,
    ]

    form_columns = [
        EsimPackage.slug,
        EsimPackage.name,
        EsimPackage.country,
        EsimPackage.country_code,
        EsimPackage.region,
        EsimPackage.flag_emoji,
        EsimPackage.description,
        EsimPackage.data_label,
        EsimPackage.data_total_gb,
        EsimPackage.validity_days,
        EsimPackage.price_cents,
        EsimPackage.currency,
        EsimPackage.provider_sku,
        EsimPackage.network_label,
        EsimPackage.stripe_product_id,
        EsimPackage.stripe_price_id,
        EsimPackage.is_active,
        EsimPackage.is_featured,
        EsimPackage.is_managed,
        EsimPackage.tier,
        EsimPackage.sort_order,
    ]

    form_widget_args = {
        "description": {"rows": 4},
        "price_cents": {"placeholder": "1999 = $19.99 — >10% changes need admin approval"},
        "slug": {"placeholder": "turkey-traveler-10gb"},
    }

    column_labels = {
        EsimPackage.is_active: "Sale status",
        EsimPackage.price_cents: "Price",
        EsimPackage.pending_price_cents: "Pending price (¢)",
        EsimPackage.admin_approved: "Approved",
    }

    column_formatters = {
        EsimPackage.is_active: _format_package_sale,
        EsimPackage.price_cents: _format_package_price,
    }

    async def on_model_change(
        self, data: dict, model: EsimPackage, is_created: bool, request: Request
    ) -> None:
        if not has_role(request, CATALOG_MANAGER_ROLES):
            raise ValueError("You do not have permission to edit catalog plans.")
        try:
            validated = validate_package_payload(data, is_create=is_created)
            apply_package_approval_rules(
                validated,
                is_create=is_created,
                editor_is_admin=has_role(request, (ROLE_ADMIN,)),
                editor_username=session_username(request),
                existing=None if is_created else model,
            )
        except AdminCatalogError as exc:
            raise ValueError(str(exc)) from exc
        data.clear()
        data.update(validated)
        if is_created:
            data["id"] = uuid.uuid4()
        if validated.get("pending_price_cents") is not None and not has_role(request, (ROLE_ADMIN,)):
            request.session["flash_success"] = (
                "Price change saved as pending — an admin must approve before it goes live."
            )
        elif is_created and not validated.get("admin_approved"):
            request.session["flash_success"] = (
                "Plan saved. An admin must approve before it appears for sale."
            )

    @action(
        name="stop_sale",
        label="Stop sale",
        confirmation_message="Remove selected plans from sale immediately?",
        add_in_list=True,
    )
    async def stop_sale(self, request: Request):
        return await self._bulk_sale(request, active=False)

    @action(
        name="start_sale",
        label="Put on sale",
        confirmation_message="Enable selected approved plans for sale?",
        add_in_list=True,
    )
    async def start_sale(self, request: Request):
        return await self._bulk_sale(request, active=True)

    @action(
        name="approve_plans",
        label="Approve plan / price",
        confirmation_message="Approve selected plans (and any pending prices) for sale?",
        add_in_list=True,
    )
    async def approve_plans(self, request: Request):
        if not has_role(request, (ROLE_ADMIN,)):
            request.session["flash_error"] = "Only admins can approve catalog plans."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)
        return await self._bulk_approve(request)

    async def _bulk_sale(self, request: Request, *, active: bool) -> RedirectResponse:
        pks = [pk.strip() for pk in request.query_params.get("pks", "").split(",") if pk.strip()]
        session_factory = get_session_factory()
        if session_factory is None:
            request.session["flash_error"] = "Database not configured."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

        changed = 0
        with session_factory() as session:
            for pk in pks:
                package = session.get(EsimPackage, uuid.UUID(pk))
                if package is None:
                    continue
                if active and not package.admin_approved:
                    continue
                package.is_active = active
                changed += 1
                write_audit_log(
                    session,
                    admin_user_id=request.session.get("admin_user_id"),
                    admin_username=session_username(request),
                    action="start_sale" if active else "stop_sale",
                    table_name="esim_packages",
                    record_id=package.slug,
                    new_values={"is_active": active},
                    ip_address=_client_ip(request),
                )
            session.commit()

        verb = "Enabled" if active else "Stopped"
        request.session["flash_success"] = f"{verb} sale for {changed} plan(s)."
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

    async def _bulk_approve(self, request: Request) -> RedirectResponse:
        pks = [pk.strip() for pk in request.query_params.get("pks", "").split(",") if pk.strip()]
        session_factory = get_session_factory()
        username = session_username(request)
        approved = 0
        with session_factory() as session:
            for pk in pks:
                package = session.get(EsimPackage, uuid.UUID(pk))
                if package is None:
                    continue
                approve_catalog_package(package, admin_username=username)
                if not package.is_active:
                    package.is_active = True
                approved += 1
                write_audit_log(
                    session,
                    admin_user_id=request.session.get("admin_user_id"),
                    admin_username=username,
                    action="approve_catalog_plan",
                    table_name="esim_packages",
                    record_id=package.slug,
                    new_values={
                        "price_cents": package.price_cents,
                        "pending_price_cents": package.pending_price_cents,
                    },
                    ip_address=_client_ip(request),
                )
            session.commit()

        request.session["flash_success"] = f"Approved {approved} plan(s) for sale."
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)


class PlanFulfillmentMapAdmin(AuditedModelView, model=PlanFulfillmentMap):
    name = "Fulfillment Map"
    name_plural = "Provider routes"
    icon = "fa-solid fa-route"
    category = "Catalog"
    allowed_roles = CATALOG_MANAGER_ROLES

    can_delete = False
    page_size = 50

    column_list = [
        PlanFulfillmentMap.catalog_key,
        PlanFulfillmentMap.country_code,
        PlanFulfillmentMap.data_gb,
        PlanFulfillmentMap.validity_days,
        PlanFulfillmentMap.provider,
        PlanFulfillmentMap.provider_sku,
        PlanFulfillmentMap.wholesale_cents,
        PlanFulfillmentMap.is_active,
        PlanFulfillmentMap.admin_approved,
    ]
    column_searchable_list = [
        PlanFulfillmentMap.catalog_key,
        PlanFulfillmentMap.provider_sku,
        PlanFulfillmentMap.country_slug,
    ]
    column_filters = [
        PlanFulfillmentMap.provider,
        PlanFulfillmentMap.is_active,
        PlanFulfillmentMap.admin_approved,
    ]
    column_default_sort = [(PlanFulfillmentMap.catalog_key, False)]

    form_columns = [
        PlanFulfillmentMap.catalog_key,
        PlanFulfillmentMap.package_id,
        PlanFulfillmentMap.country_code,
        PlanFulfillmentMap.country_slug,
        PlanFulfillmentMap.data_gb,
        PlanFulfillmentMap.validity_days,
        PlanFulfillmentMap.provider,
        PlanFulfillmentMap.provider_sku,
        PlanFulfillmentMap.provider_slug,
        PlanFulfillmentMap.wholesale_cents,
        PlanFulfillmentMap.period_num,
        PlanFulfillmentMap.is_active,
        PlanFulfillmentMap.notes,
    ]

    form_widget_args = {
        "notes": {"rows": 3},
        "provider": {
            "placeholder": "citrus, esimaccess, telna, simbase — new routes need admin approval",
        },
    }

    column_labels = {
        PlanFulfillmentMap.provider: "Provider",
        PlanFulfillmentMap.admin_approved: "Approved",
    }

    column_formatters = {
        PlanFulfillmentMap.provider: _format_map_provider,
    }

    async def on_model_change(
        self, data: dict, model: PlanFulfillmentMap, is_created: bool, request: Request
    ) -> None:
        if not has_role(request, CATALOG_MANAGER_ROLES):
            raise ValueError("You do not have permission to edit provider routes.")
        try:
            validated = validate_fulfillment_map_payload(data, is_create=is_created)
            apply_fulfillment_approval_rules(
                validated,
                is_create=is_created,
                editor_is_admin=has_role(request, (ROLE_ADMIN,)),
                editor_username=session_username(request),
                existing=None if is_created else model,
            )
        except AdminCatalogError as exc:
            raise ValueError(str(exc)) from exc
        data.clear()
        data.update(validated)
        if is_created:
            data["id"] = uuid.uuid4()
        if not validated.get("admin_approved") and not has_role(request, (ROLE_ADMIN,)):
            request.session["flash_success"] = (
                "Provider route saved. An admin must approve before checkout can use it."
            )

    @action(
        name="disable_routes",
        label="Disable routes",
        confirmation_message="Disable selected provider routes?",
        add_in_list=True,
    )
    async def disable_routes(self, request: Request):
        return await self._bulk_active(request, active=False)

    @action(
        name="enable_routes",
        label="Enable routes",
        confirmation_message="Enable selected approved routes?",
        add_in_list=True,
    )
    async def enable_routes(self, request: Request):
        return await self._bulk_active(request, active=True)

    @action(
        name="approve_routes",
        label="Approve provider route",
        confirmation_message="Approve selected provider routes for checkout fulfillment?",
        add_in_list=True,
    )
    async def approve_routes(self, request: Request):
        if not has_role(request, (ROLE_ADMIN,)):
            request.session["flash_error"] = "Only admins can approve provider routes."
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)
        return await self._bulk_approve_routes(request)

    async def _bulk_active(self, request: Request, *, active: bool) -> RedirectResponse:
        pks = [pk.strip() for pk in request.query_params.get("pks", "").split(",") if pk.strip()]
        session_factory = get_session_factory()
        changed = 0
        with session_factory() as session:
            for pk in pks:
                row = session.get(PlanFulfillmentMap, uuid.UUID(pk))
                if row is None:
                    continue
                if active and not row.admin_approved:
                    continue
                row.is_active = active
                changed += 1
            session.commit()
        verb = "Enabled" if active else "Disabled"
        request.session["flash_success"] = f"{verb} {changed} provider route(s)."
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

    async def _bulk_approve_routes(self, request: Request) -> RedirectResponse:
        pks = [pk.strip() for pk in request.query_params.get("pks", "").split(",") if pk.strip()]
        session_factory = get_session_factory()
        username = session_username(request)
        approved = 0
        with session_factory() as session:
            for pk in pks:
                row = session.get(PlanFulfillmentMap, uuid.UUID(pk))
                if row is None:
                    continue
                approve_fulfillment_map(row, admin_username=username)
                approved += 1
                write_audit_log(
                    session,
                    admin_user_id=request.session.get("admin_user_id"),
                    admin_username=username,
                    action="approve_fulfillment_map",
                    table_name="plan_fulfillment_map",
                    record_id=row.catalog_key,
                    new_values={"provider": row.provider, "provider_sku": row.provider_sku},
                    ip_address=_client_ip(request),
                )
            session.commit()
        request.session["flash_success"] = f"Approved {approved} provider route(s)."
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)
