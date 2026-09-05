"""Staff-friendly wizard registry — plain language, role-filtered."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.admin.nav_catalog import WIZARD_CATEGORY
from app.admin.roles import (
    CATALOG_MANAGER_ROLES,
    PROMO_MANAGER_ROLES,
    ROLE_ADMIN,
    ROLE_SUPPORT,
)


@dataclass(frozen=True)
class StaffWizard:
    key: str
    title: str
    summary: str
    steps: Tuple[str, ...]
    icon: str
    endpoint: str
    roles: Tuple[str, ...]
    badge: str = ""


# Re-export for views that import from here
__all__ = ("WIZARD_CATEGORY", "STAFF_WIZARDS", "StaffWizard", "wizards_for_role")


STAFF_WIZARDS: Tuple[StaffWizard, ...] = (
    StaffWizard(
        key="help-customer",
        title="Help a customer",
        summary="Log a support request when someone emails or messages you. Tie it to their order if you have it.",
        steps=("Customer details", "What they need", "Send confirmation"),
        icon="fa-solid fa-life-ring",
        endpoint="admin:help-customer",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Support",
    ),
    StaffWizard(
        key="new-promo",
        title="Create a promo code",
        summary="Set up a discount code for a campaign. Codes above 20% need admin approval.",
        steps=("Code & discount", "Dates & limits", "Save"),
        icon="fa-solid fa-tag",
        endpoint="admin:promo-wizard",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    StaffWizard(
        key="new-custom-plan",
        title="Add a new travel plan",
        summary="Create what customers see on the site and connect it to Citrus, eSIM Access, or Telna.",
        steps=("Plan details", "Provider SKU", "Publish"),
        icon="fa-solid fa-sim-card",
        endpoint="admin:new-custom-plan",
        roles=CATALOG_MANAGER_ROLES,
        badge="Catalog",
    ),
    StaffWizard(
        key="complimentary-esim",
        title="Send a free eSIM",
        summary="Give a complimentary plan to staff or a partner. They receive the QR email automatically.",
        steps=("Pick plan", "Recipient", "Send"),
        icon="fa-solid fa-gift",
        endpoint="admin:complimentary-esim",
        roles=(ROLE_ADMIN,),
        badge="Admin only",
    ),
    StaffWizard(
        key="insider-wizard",
        title="Send Insider newsletter",
        summary="Create and schedule a newsletter issue. Send a test email before it goes live.",
        steps=("Write issue", "Schedule", "Test & publish"),
        icon="fa-solid fa-paper-plane",
        endpoint="admin:insider-wizard",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    StaffWizard(
        key="social-media-hub",
        title="Social media toolkit",
        summary="Upload partner photos/videos, copy captions, and open Meta to post on Facebook and Instagram.",
        steps=("Upload media", "Copy caption", "Post on Meta", "Mark posted"),
        icon="fa-solid fa-share-nodes",
        endpoint="admin:social-media-hub",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    StaffWizard(
        key="creator-outreach-hub",
        title="Creator outreach",
        summary="Track DIY Umrah creators, premade pitches, and send branded NoorLink partnership emails.",
        steps=("Add creator", "Pick template", "Send branded email", "Track replies"),
        icon="fa-solid fa-envelope-open-text",
        endpoint="admin:creator-outreach-hub",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    StaffWizard(
        key="newsletter-admin",
        title="Newsletter subscribers",
        summary="View who's subscribed, export a list, or unsubscribe someone.",
        steps=("Browse list", "Export or unsubscribe"),
        icon="fa-solid fa-users",
        endpoint="admin:newsletter-admin",
        roles=PROMO_MANAGER_ROLES,
        badge="Marketing",
    ),
    StaffWizard(
        key="fulfill-order",
        title="Fulfill a stuck order",
        summary="Customer paid but no eSIM? Run fulfillment manually.",
        steps=("Order number", "Confirm", "Send eSIM"),
        icon="fa-solid fa-bolt",
        endpoint="admin:fulfill-order",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Support",
    ),
    StaffWizard(
        key="order-insight",
        title="Look up an order",
        summary="Gift info, reminders sent, breakage allowance — everything in one view.",
        steps=("Order number", "Review details"),
        icon="fa-solid fa-magnifying-glass",
        endpoint="admin:order-insight",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        badge="Support",
    ),
    StaffWizard(
        key="affiliate-payout",
        title="Record affiliate payout",
        summary="After you pay an affiliate, mark their commissions as paid here.",
        steps=("Pick affiliate", "Payment details", "Save"),
        icon="fa-solid fa-money-bill-transfer",
        endpoint="admin:affiliate-payout",
        roles=(ROLE_ADMIN,),
        badge="Admin",
    ),
    StaffWizard(
        key="staff-user",
        title="Add a staff member",
        summary="Create a login for support, catalog, or marketing.",
        steps=("Username & role", "Set password", "Save"),
        icon="fa-solid fa-user-plus",
        endpoint="admin:staff-user",
        roles=(ROLE_ADMIN,),
        badge="Admin",
    ),
    StaffWizard(
        key="finance-hub",
        title="Finance dashboard",
        summary="Revenue, margin, affiliate liability, CSV exports, and monthly summary email.",
        steps=("Review snapshot", "Export if needed", "Email summary"),
        icon="fa-solid fa-chart-line",
        endpoint="admin:finance-hub",
        roles=(ROLE_ADMIN,),
        badge="Finance",
    ),
    StaffWizard(
        key="refund-order",
        title="Refund a customer",
        summary="Issue a Stripe refund. Blocks refunds when data usage is over 50% unless you override.",
        steps=("Order number", "Reason", "Confirm refund"),
        icon="fa-solid fa-rotate-left",
        endpoint="admin:refund-order",
        roles=(ROLE_ADMIN,),
        badge="Finance",
    ),
)


def wizards_for_role(role: str) -> list[StaffWizard]:
    if role == ROLE_ADMIN:
        return list(STAFF_WIZARDS)
    return [wizard for wizard in STAFF_WIZARDS if role in wizard.roles]
