"""Operations hub cards — admin/support tools beyond Quick start wizards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.admin.nav_catalog import OPERATIONS_CATEGORY
from app.admin.roles import (
    CATALOG_MANAGER_ROLES,
    PROMO_MANAGER_ROLES,
    ROLE_ADMIN,
    ROLE_SUPPORT,
)


@dataclass(frozen=True)
class AdminTool:
    key: str
    title: str
    summary: str
    icon: str
    endpoint: str
    roles: Tuple[str, ...]
    badge: str = ""


ADMIN_TOOLS: Tuple[AdminTool, ...] = (
    AdminTool(
        key="operations-hub",
        title="System health",
        summary="See counts for suspended orders, stuck fulfillments, and scheduled jobs. Run background tasks.",
        icon="fa-solid fa-heart-pulse",
        endpoint="admin:operations-hub",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Ops",
    ),
    AdminTool(
        key="fulfill-order",
        title="Fulfill a stuck order",
        summary="Use when Stripe charged the customer but the eSIM email never went out.",
        icon="fa-solid fa-bolt",
        endpoint="admin:fulfill-order",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Support",
    ),
    AdminTool(
        key="suspended-orders",
        title="Suspended orders",
        summary="Orders paused after data cap. Review and reactivate if appropriate.",
        icon="fa-solid fa-pause-circle",
        endpoint="admin:suspended-orders",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Support",
    ),
    AdminTool(
        key="order-insight",
        title="Order lookup",
        summary="Gift details, reminder emails sent, breakage allowance — all in one place.",
        icon="fa-solid fa-magnifying-glass",
        endpoint="admin:order-insight",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Support",
    ),
    AdminTool(
        key="insider-wizard",
        title="Send Insider newsletter",
        summary="Create and schedule a newsletter issue. Send a test to yourself first.",
        icon="fa-solid fa-paper-plane",
        endpoint="admin:insider-wizard",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    AdminTool(
        key="newsletter-admin",
        title="Newsletter subscribers",
        summary="View subscribers, export CSV, or unsubscribe someone on request.",
        icon="fa-solid fa-users",
        endpoint="admin:newsletter-admin",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    AdminTool(
        key="social-media-hub",
        title="Social media toolkit",
        summary="Partner media library, caption templates, and Meta quick links for FB/IG.",
        icon="fa-solid fa-share-nodes",
        endpoint="admin:social-media-hub",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    AdminTool(
        key="catalog-overview",
        title="Catalog overview",
        summary="Compare checkout plans vs browse-page plans and spot mismatches.",
        icon="fa-solid fa-layer-group",
        endpoint="admin:catalog-overview",
        roles=CATALOG_MANAGER_ROLES,
        badge="Catalog",
    ),
    AdminTool(
        key="provider-catalog",
        title="Provider SKU browser",
        summary="Search Telna and other provider SKUs when building a new plan.",
        icon="fa-solid fa-warehouse",
        endpoint="admin:provider-catalog",
        roles=CATALOG_MANAGER_ROLES,
        badge="Catalog",
    ),
    AdminTool(
        key="affiliate-payout",
        title="Record affiliate payout",
        summary="Mark approved commissions as paid after you send money.",
        icon="fa-solid fa-money-bill-transfer",
        endpoint="admin:affiliate-payout",
        roles=(ROLE_ADMIN,),
        badge="Admin",
    ),
    AdminTool(
        key="staff-user",
        title="Add staff member",
        summary="Create a login for support, catalog, or marketing team.",
        icon="fa-solid fa-user-plus",
        endpoint="admin:staff-user",
        roles=(ROLE_ADMIN,),
        badge="Admin",
    ),
    AdminTool(
        key="finance-hub",
        title="Finance dashboard",
        summary="Revenue, margin, affiliate liability, CSV exports, and monthly summary email.",
        icon="fa-solid fa-chart-line",
        endpoint="admin:finance-hub",
        roles=(ROLE_ADMIN,),
        badge="Finance",
    ),
    AdminTool(
        key="refund-order",
        title="Refund an order",
        summary="Issue a Stripe refund with usage policy guards.",
        icon="fa-solid fa-rotate-left",
        endpoint="admin:refund-order",
        roles=(ROLE_ADMIN,),
        badge="Finance",
    ),
    AdminTool(
        key="insights-hub",
        title="Business insights",
        summary="Orders by country, email analytics, provider health, and trending plans.",
        icon="fa-solid fa-chart-pie",
        endpoint="admin:insights-hub",
        roles=(ROLE_ADMIN,),
        badge="Insights",
    ),
    AdminTool(
        key="event-log",
        title="Event log",
        summary="Stripe webhooks, fulfillment, refunds, and customer resend history.",
        icon="fa-solid fa-list-check",
        endpoint="admin:event-log",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Ops",
    ),
    AdminTool(
        key="breakage-list",
        title="Breakage allowances",
        summary="Review active breakage credits issued with orders.",
        icon="fa-solid fa-shield",
        endpoint="admin:breakage-list",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Ops",
    ),
    AdminTool(
        key="gdpr-tools",
        title="Privacy / GDPR tools",
        summary="Export or redact customer data on request.",
        icon="fa-solid fa-user-shield",
        endpoint="admin:gdpr-tools",
        roles=(ROLE_ADMIN,),
        badge="Admin",
    ),
)


def tools_for_role(role: str) -> list[AdminTool]:
    if role == ROLE_ADMIN:
        return list(ADMIN_TOOLS)
    return [tool for tool in ADMIN_TOOLS if role in tool.roles]
