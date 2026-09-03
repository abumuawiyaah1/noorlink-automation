"""Mount SQLAdmin on the FastAPI application."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

from app.admin.auth import NoorLinkAdminAuth
from app.admin.ip_guard import AdminIPGuardMiddleware, parse_allowed_ips
from app.admin.views.admin_users import AdminAuditLogAdmin, AdminUserAdmin
from app.admin.views.affiliates import (
    AffiliateAdmin,
    AffiliateCommissionAdmin,
    AffiliatePayoutAdmin,
)
from app.admin.views.catalog import EsimPackageAdmin, PlanFulfillmentMapAdmin
from app.admin.views.affiliate_payout_wizard import AffiliatePayoutWizardView
from app.admin.views.breakage_list import BreakageListView
from app.admin.views.catalog_overview import CatalogOverviewView
from app.admin.views.custom_plan_wizard import CustomPlanWizardView
from app.admin.views.commerce import InsiderIssueAdmin, OrderAdmin, PromoCodeAdmin
from app.admin.views.complimentary_esim import ComplimentaryEsimView
from app.admin.views.document_vault import DocumentVaultView
from app.admin.views.event_log_view import EventLogView
from app.admin.views.finance_hub import FinanceHubView
from app.admin.views.fulfill_order_wizard import FulfillOrderWizardView
from app.admin.views.help_center import HelpCenterView
from app.admin.views.help_customer_wizard import HelpCustomerWizardView
from app.admin.views.insider_wizard import InsiderWizardView
from app.admin.views.insights_hub import GdprToolsView, InsightsHubView
from app.admin.views.newsletter_admin import NewsletterAdminView
from app.admin.views.notifications_hub import NotificationsHubView
from app.admin.views.operations_hub import OperationsHubView
from app.admin.views.order_insight import OrderInsightView
from app.admin.views.promo_wizard import PromoWizardView
from app.admin.views.refund_wizard import RefundWizardView
from app.admin.views.social_media_hub import SocialMediaHubView
from app.admin.views.staff_wizards_hub import StaffWizardsHubView
from app.admin.views.staff_user_wizard import StaffUserWizardView
from app.admin.views.suspended_orders import SuspendedOrdersView
from app.admin.views.system_diagnostics import ProviderCatalogBrowserView, SystemDiagnosticsView
from app.admin.views.support import SupportTicketAdmin
from app.admin.views.support_inbox import SupportInboxView
from app.core.config import get_settings
from app.db.engine import get_engine

logger = logging.getLogger(__name__)
ADMIN_TEMPLATES = str(Path(__file__).resolve().parent / "templates")


def mount_admin(app: FastAPI) -> Admin | None:
    settings = get_settings()
    if not settings.admin_enabled:
        logger.info("Admin dashboard disabled (ADMIN_ENABLED=false)")
        return None

    engine = get_engine()
    if engine is None:
        logger.warning(
            "Admin dashboard not mounted: set DATABASE_URL to your Supabase Postgres pooler URI."
        )
        return None

    is_production = settings.environment.lower() in {"production", "prod"}
    allowed_ips = parse_allowed_ips(settings.admin_allowed_ips)
    if allowed_ips:
        app.add_middleware(AdminIPGuardMiddleware, allowed_ips=allowed_ips)
        logger.info("Admin IP allowlist enabled (%d IPs)", len(allowed_ips))

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=is_production,
        same_site="lax",
        max_age=settings.admin_session_max_age,
    )

    auth_backend = NoorLinkAdminAuth(secret_key=settings.secret_key)
    admin = Admin(
        app,
        engine,
        authentication_backend=auth_backend,
        base_url="/admin",
        title="NoorLink Admin",
        logo_url=settings.email_logo_url,
        templates_dir=ADMIN_TEMPLATES,
    )
    admin.templates.env.globals["admin_session_max_age"] = settings.admin_session_max_age

    admin.add_base_view(StaffWizardsHubView)
    admin.add_base_view(NotificationsHubView)
    admin.add_base_view(HelpCenterView)
    admin.add_base_view(FinanceHubView)
    admin.add_base_view(DocumentVaultView)
    admin.add_base_view(InsightsHubView)
    admin.add_base_view(OperationsHubView)
    admin.add_base_view(HelpCustomerWizardView)
    admin.add_base_view(PromoWizardView)
    admin.add_base_view(FulfillOrderWizardView)
    admin.add_base_view(SuspendedOrdersView)
    admin.add_base_view(OrderInsightView)
    admin.add_base_view(InsiderWizardView)
    admin.add_base_view(NewsletterAdminView)
    admin.add_base_view(SocialMediaHubView)
    admin.add_base_view(CatalogOverviewView)
    admin.add_base_view(ProviderCatalogBrowserView)
    admin.add_base_view(AffiliatePayoutWizardView)
    admin.add_base_view(StaffUserWizardView)
    admin.add_base_view(SystemDiagnosticsView)
    admin.add_base_view(RefundWizardView)
    admin.add_base_view(EventLogView)
    admin.add_base_view(BreakageListView)
    admin.add_base_view(GdprToolsView)
    admin.add_base_view(CustomPlanWizardView)
    admin.add_view(EsimPackageAdmin)
    admin.add_view(PlanFulfillmentMapAdmin)
    admin.add_view(PromoCodeAdmin)
    admin.add_view(InsiderIssueAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(AffiliateAdmin)
    admin.add_view(AffiliateCommissionAdmin)
    admin.add_view(AffiliatePayoutAdmin)
    admin.add_view(SupportTicketAdmin)
    admin.add_base_view(SupportInboxView)
    admin.add_view(AdminUserAdmin)
    admin.add_view(AdminAuditLogAdmin)
    admin.add_base_view(ComplimentaryEsimView)

    logger.info("NoorLink admin dashboard mounted at /admin")
    return admin
