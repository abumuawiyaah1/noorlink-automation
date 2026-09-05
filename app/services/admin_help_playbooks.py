"""Help center playbooks, how-to wiki browse, and read-only doc viewer."""

from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, Tuple

from app.admin.roles import (
    ROLE_ADMIN,
    ROLE_CATALOG,
    ROLE_FINANCE,
    ROLE_LEGAL,
    ROLE_MARKETING,
    ROLE_OWNER,
    ROLE_SUPPORT,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"

DocAudience = Literal["staff", "dev"]

# Wiki browse areas — plain-language staff training sections
HELP_AREAS: Tuple[Tuple[str, str, str], ...] = (
    ("getting-started", "Getting started", "Sign-in, roles, daily checks, first-day checklists"),
    ("support", "Support", "Tickets, orders, eSIM delivery, suspended plans"),
    ("marketing", "Marketing", "Promos, Insider, social posts, creator outreach"),
    ("catalog", "Catalog", "Travel plans, provider SKUs, browse vs checkout"),
    ("finance", "Finance", "Revenue, refunds, affiliates, document vault"),
    ("admin", "Admin & ops", "Staff logins, security, operations, GDPR"),
)


@dataclass(frozen=True)
class HelpPlaybook:
    id: str
    title: str
    problem: str
    steps: Tuple[str, ...]
    tags: Tuple[str, ...]
    wizard_path: str
    doc_slug: Optional[str] = None
    roles: Tuple[str, ...] = ()
    area: str = "support"


@dataclass(frozen=True)
class HelpDoc:
    slug: str
    filename: str
    title: str
    summary: str
    audience: DocAudience
    pinned: bool = False


@dataclass(frozen=True)
class DocSearchHit:
    slug: str
    title: str
    audience: DocAudience
    excerpt: str
    score: int


HELP_DOCS: Tuple[HelpDoc, ...] = (
    HelpDoc(
        slug="admin-dashboard",
        filename="ADMIN-DASHBOARD-GUIDE.md",
        title="Admin dashboard — full staff guide",
        summary="Sidebar, roles, wizards, finance, operations, security, weekly routine.",
        audience="staff",
        pinned=True,
    ),
    HelpDoc(
        slug="developer-codebase",
        filename="DEVELOPER-CODEBASE-GUIDE.md",
        title="Developer codebase guide",
        summary="API routes, services, migrations, env vars, repos — read-only research.",
        audience="dev",
        pinned=True,
    ),
    HelpDoc(
        slug="social-media",
        filename="SOCIAL-MEDIA-HUB.md",
        title="Social media toolkit",
        summary="Partner photo/video library, captions, Meta posting workflow.",
        audience="staff",
        pinned=True,
    ),
    HelpDoc(
        slug="creator-outreach",
        filename="CREATOR-OUTREACH.md",
        title="Creator outreach",
        summary="Creator databank, premade pitches, branded partnership emails.",
        audience="staff",
        pinned=True,
    ),
    HelpDoc(
        slug="telna-runbook",
        filename="TELNA-RUNBOOK.md",
        title="Telna runbook",
        summary="Telna API errors, Cloudflare 1010, catalog sync.",
        audience="staff",
    ),
    HelpDoc(
        slug="stripe-wallets",
        filename="STRIPE-WALLETS.md",
        title="Stripe & wallets",
        summary="Express checkout, Apple Pay, Google Pay setup.",
        audience="staff",
    ),
    HelpDoc(
        slug="owner-protection",
        filename="OWNER-PROTECTION.md",
        title="Owner protection & break-glass",
        summary="Prevent rogue admins from locking you out; recover via Railway CLI.",
        audience="staff",
        pinned=True,
    ),
    HelpDoc(
        slug="document-vault",
        filename="DOCUMENT-VAULT.md",
        title="Legal & accounting document vault",
        summary="Upload/store contracts and accounting papers; finance and legal roles.",
        audience="staff",
        pinned=True,
    ),
    HelpDoc(
        slug="backup-restore",
        filename="BACKUP-RESTORE-GUIDE.md",
        title="Backup & restore",
        summary="Supabase PITR, weekly exports, disaster recovery.",
        audience="staff",
    ),
    HelpDoc(
        slug="pre-ship",
        filename="PRE-SHIP-CHECKLIST.md",
        title="Pre-ship checklist",
        summary="Migrations, webhooks, cron, admin lockdown before launch.",
        audience="staff",
        pinned=True,
    ),
)

DOC_SLUG_ALIASES = {
    "telna-runbook": "telna-runbook",
    "stripe-wallets": "stripe-wallets",
    "breakage-fulfillment": "breakage-fulfillment",
}

PLAYBOOKS: Tuple[HelpPlaybook, ...] = (
    HelpPlaybook(
        id="support-saved-replies",
        title="Use saved replies in Support Inbox",
        problem="Want faster, calmer customer replies without typing from scratch.",
        steps=(
            "Open a ticket in Support Inbox",
            "Under For this topic — pick a category template",
            "Under Saved replies — use shared snippets (QR missing, install before you fly, refund policy)",
            "Edit the text if needed, then Send reply",
        ),
        tags=("support", "inbox", "templates", "saved", "replies", "snippets"),
        wizard_path="/admin/support-inbox",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        area="support",
    ),
    HelpPlaybook(
        id="no-esim-after-payment",
        title="Customer paid but didn't get eSIM",
        problem="Stripe charge succeeded but no QR / activation email arrived.",
        steps=(
            "Look up the order in Order lookup",
            "If status is paid with no QR, open Fulfill stuck order",
            "If already delivered, use Resend eSIM email on the order",
        ),
        tags=("fulfill", "esim", "qr", "email", "paid", "stuck-order", "stripe", "webhook"),
        wizard_path="/admin/fulfill-order",
        doc_slug="stripe-wallets",
        area="support",
    ),
    HelpPlaybook(
        id="suspended-order",
        title="Customer's eSIM stopped working",
        problem="Order shows suspended — usually data cap or balance depleted.",
        steps=(
            "Open Suspended orders and find the order",
            "Check usage in Order lookup",
            "Reactivate only if you've confirmed with the provider",
        ),
        tags=("suspended", "data", "cap", "usage", "esim", "citrus"),
        wizard_path="/admin/suspended-orders",
        area="support",
    ),
    HelpPlaybook(
        id="auto-refund-48h",
        title="48-hour unanswered auto-refund",
        problem="What happens if nobody answers a refund ticket?",
        steps=(
            "Refund tickets get an auto-reply and Needs human alert immediately",
            "If no staff reply for 48 hours, cron checks strict rules",
            "Auto-refund only if usage under 20%, amount ≤ $50, order email matches",
            "Customer is emailed; ticket closed; you get an ops alert",
            "Staff reply within 48h cancels auto-refund for that ticket",
        ),
        tags=("refund", "auto", "48", "sla", "stripe", "money"),
        wizard_path="/admin/refund-order",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        area="support",
    ),
    HelpPlaybook(
        id="support-auto-reply",
        title="How support auto-reply works",
        problem="Want tickets to answer common QR/install questions without staff.",
        steps=(
            "Customer submits contact form → confirmation email goes out",
            "System classifies intent (QR missing, install, order status, refund)",
            "If order ID + email match: status reply; may resend QR once and close",
            "Refunds and stuck paid-no-QR always flag Needs human + Slack/email",
            "Staff-created tickets from Help a customer skip auto-reply",
        ),
        tags=("support", "auto", "qr", "inbox", "ticket"),
        wizard_path="/admin/support-inbox",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        area="support",
    ),
    HelpPlaybook(
        id="support-ticket",
        title="Log or reply to a customer request",
        problem="Customer called, WhatsApp'd, or emailed outside the website form.",
        steps=(
            "Use Help a customer wizard to create a ticket",
            "Open Support Inbox to reply with a branded email",
            "Tie the ticket to their order number if you have it",
        ),
        tags=("support", "ticket", "email", "customer", "help", "inbox"),
        wizard_path="/admin/help-customer",
        area="support",
    ),
    HelpPlaybook(
        id="order-lookup-howto",
        title="Look up an order",
        problem="Need gift details, usage, reminders, or breakage for a paid order.",
        steps=(
            "Open Look up an order (Quick start or Operations)",
            "Enter the order number (and confirm email if asked)",
            "Review gift recipient, QR status, usage, and reminder history",
        ),
        tags=("order", "lookup", "gift", "usage", "esim"),
        wizard_path="/admin/order-insight",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        area="support",
    ),
    HelpPlaybook(
        id="promo-not-working",
        title="Promo code rejected at checkout",
        problem="Customer says a code doesn't work.",
        steps=(
            "Check Promo codes table — active dates and redemption limit",
            "Codes above 20% need admin approval before checkout works",
            "Create a replacement code in the promo wizard if needed",
        ),
        tags=("promo", "discount", "checkout", "approval", "marketing"),
        wizard_path="/admin/promo-wizard",
        roles=(ROLE_ADMIN, ROLE_MARKETING, ROLE_CATALOG),
        area="marketing",
    ),
    HelpPlaybook(
        id="create-promo",
        title="Create a promo code",
        problem="Need a discount code for a campaign or partner.",
        steps=(
            "Open Create a promo code from Quick start",
            "Enter code, discount %, start/end dates, and optional usage limit",
            "Save — if over 20%, ask an admin to approve before customers can use it",
        ),
        tags=("promo", "discount", "campaign", "marketing", "create"),
        wizard_path="/admin/promo-wizard",
        roles=(ROLE_ADMIN, ROLE_MARKETING, ROLE_CATALOG),
        area="marketing",
    ),
    HelpPlaybook(
        id="insider-send",
        title="Send Insider newsletter",
        problem="Monthly newsletter or special issue needs to go out.",
        steps=(
            "Create the issue in Send Insider wizard",
            "Send a test email to yourself first",
            "Schedule send date — the system delivers on that day",
        ),
        tags=("insider", "newsletter", "email", "marketing"),
        wizard_path="/admin/insider-wizard",
        roles=(ROLE_ADMIN, ROLE_MARKETING),
        area="marketing",
    ),
    HelpPlaybook(
        id="newsletter-subscribers",
        title="Manage newsletter subscribers",
        problem="Need to export the list or unsubscribe someone.",
        steps=(
            "Open Newsletter subscribers under Marketing",
            "Browse or search by email",
            "Export CSV for a campaign, or unsubscribe on request",
        ),
        tags=("newsletter", "subscribers", "export", "unsubscribe", "marketing"),
        wizard_path="/admin/newsletter-admin",
        roles=(ROLE_ADMIN, ROLE_MARKETING, ROLE_CATALOG),
        area="marketing",
    ),
    HelpPlaybook(
        id="social-media-post",
        title="Post partner photos on Facebook or Instagram",
        problem="You have partner media ready and need to publish on Meta.",
        steps=(
            "Open Social media under Marketing",
            "Upload the photo or video (keep files under ~100 MB)",
            "Copy the caption, then open Meta Business Suite / Instagram to post",
            "Mark the asset as Posted, and delete old posted files when storage fills up",
        ),
        tags=("social", "instagram", "facebook", "meta", "caption", "media", "marketing"),
        wizard_path="/admin/social-media",
        doc_slug="social-media",
        roles=(ROLE_ADMIN, ROLE_MARKETING, ROLE_CATALOG),
        area="marketing",
    ),
    HelpPlaybook(
        id="creator-outreach-email",
        title="Creator outreach — email a travel creator",
        problem="Reach DIY Umrah / Muslim travel creators with a branded pitch from the Creator outreach hub.",
        steps=(
            "Open Creator outreach under Marketing (or Quick start)",
            "Pick a creator (or Add one) and enter their email",
            "Choose a premade template, edit the body, then Send branded email",
            "Or use Copy for DM if you're messaging on Instagram instead",
            "Update status as they reply → gifted → posted",
        ),
        tags=("outreach", "creator", "influencer", "email", "affiliate", "marketing", "instagram", "how-to"),
        wizard_path="/admin/creator-outreach",
        doc_slug="creator-outreach",
        roles=(ROLE_ADMIN, ROLE_MARKETING, ROLE_CATALOG),
        area="marketing",
    ),
    HelpPlaybook(
        id="complimentary-esim",
        title="Send a free eSIM to staff or a partner",
        problem="Gift a complimentary plan without a customer checkout.",
        steps=(
            "Open Send a free eSIM (admin only)",
            "Pick the plan and enter the recipient email",
            "Send — they get the QR email automatically; the gift is audit-logged",
        ),
        tags=("gift", "complimentary", "esim", "partner", "staff"),
        wizard_path="/admin/complimentary-esim",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="telna-catalog",
        title="Telna API or catalog problems",
        problem="Fulfillment fails for Telna routes or catalog sync errors.",
        steps=(
            "Run Telna connectivity probe in Operations → Admin scripts",
            "Check Provider SKU browser for the correct SKU",
            "See Telna runbook for Cloudflare 1010 / 403 errors",
        ),
        tags=("telna", "provider", "catalog", "sku", "api"),
        wizard_path="/admin/provider-catalog",
        doc_slug="telna-runbook",
        roles=(ROLE_ADMIN, ROLE_CATALOG),
        area="catalog",
    ),
    HelpPlaybook(
        id="catalog-mismatch",
        title="Plan on website doesn't match checkout",
        problem="Browse page shows a plan customers can't buy.",
        steps=(
            "Open Catalog overview and filter by country",
            "Fix mismatches in checkout plans or browse catalog",
            "Use Add travel plan wizard for new checkout SKUs",
        ),
        tags=("catalog", "plans", "checkout", "browse", "mismatch"),
        wizard_path="/admin/catalog-overview",
        roles=(ROLE_ADMIN, ROLE_CATALOG),
        area="catalog",
    ),
    HelpPlaybook(
        id="add-travel-plan",
        title="Add a new travel plan",
        problem="Need a new package customers can buy on the site.",
        steps=(
            "Open Add a new travel plan from Quick start",
            "Enter plan name, destination, data amount, and price",
            "Connect the provider SKU (Citrus, eSIM Access, or Telna)",
            "Publish when ready — confirm it appears in Catalog overview",
        ),
        tags=("catalog", "plans", "create", "sku", "checkout"),
        wizard_path="/admin/new-custom-plan",
        roles=(ROLE_ADMIN, ROLE_CATALOG),
        area="catalog",
    ),
    HelpPlaybook(
        id="gift-order",
        title="Gift eSIM — wrong recipient or resend",
        problem="Gift buyer needs QR sent to recipient or order details checked.",
        steps=(
            "Order lookup shows gift recipient and sender",
            "Resend eSIM email goes to the gift recipient automatically",
        ),
        tags=("gift", "recipient", "email", "qr", "esim"),
        wizard_path="/admin/order-insight",
        area="support",
    ),
    HelpPlaybook(
        id="affiliate-payout",
        title="Pay an affiliate partner",
        problem="Approved commissions ready to mark as paid.",
        steps=(
            "Check Notifications for payout requests (attend within 72 hours)",
            "Send payment via PayPal / Wise / bank",
            "Record affiliate payout wizard marks commissions paid and closes the request",
        ),
        tags=("affiliate", "payout", "commission", "finance"),
        wizard_path="/admin/affiliate-payout",
        roles=(ROLE_ADMIN,),
        area="finance",
    ),
    HelpPlaybook(
        id="email-delivery",
        title="Emails not sending",
        problem="Customers or staff not receiving transactional email.",
        steps=(
            "Operations → Admin scripts → Email probe",
            "Confirm the from-address uses @noorlink.co",
            "Ask the customer to check spam; review Resend for bounces if needed",
        ),
        tags=("email", "resend", "delivery", "ops"),
        wizard_path="/admin/diagnostics",
        area="admin",
    ),
    HelpPlaybook(
        id="refund-order",
        title="Refund a customer order",
        problem="Customer wants money back after a charge.",
        steps=(
            "Check usage in Order lookup — over 50% used needs admin override",
            "Open Refund order wizard and enter order ID + reason",
            "Confirm status shows refunded in Finance dashboard",
        ),
        tags=("refund", "stripe", "money", "finance"),
        wizard_path="/admin/refund-order",
        roles=(ROLE_ADMIN,),
        area="finance",
    ),
    HelpPlaybook(
        id="finance-review",
        title="Monthly revenue and margin review",
        problem="Need a snapshot of business performance.",
        steps=(
            "Open Finance dashboard for revenue, margin, and affiliate liability",
            "Export orders CSV for accounting",
            "Send monthly summary email to ops inbox if needed",
        ),
        tags=("finance", "revenue", "margin", "accounting", "csv"),
        wizard_path="/admin/finance",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
        area="finance",
    ),
    HelpPlaybook(
        id="gdpr-request",
        title="Customer privacy / GDPR request",
        problem="Customer asks for data export or deletion.",
        steps=(
            "Verify identity via order email match",
            "Operations → Privacy tools → export JSON bundle",
            "For deletion: confirm checkbox — orders are redacted, not deleted",
        ),
        tags=("gdpr", "privacy", "delete", "export", "data"),
        wizard_path="/admin/gdpr",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="event-log",
        title="Trace webhook or fulfillment failure",
        problem="Need to see what happened after Stripe or provisioning.",
        steps=(
            "Open Event log and filter by order number",
            "Cross-check with Order lookup status",
            "Use Fulfill stuck order if payment succeeded but no QR",
        ),
        tags=("webhook", "event", "log", "stripe", "fulfillment"),
        wizard_path="/admin/event-log",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="security-threats",
        title="Suspicious login or API activity",
        problem="Failed admin logins, bad Stripe webhooks, or unauthorized API probes.",
        steps=(
            "Open Operations → Security → External threats",
            "Check repeated IPs on failed admin login",
            "Ops email/Slack fires automatically after 5 failures from one IP in 60 minutes",
            "Ask admin to review Cloudflare WAF if abuse continues",
        ),
        tags=("security", "login", "threat", "ops"),
        wizard_path="/admin/operations",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="notifications-daily",
        title="Check Notifications (daily)",
        problem="Don't miss stuck orders, SLA tickets, or payout requests.",
        steps=(
            "Open Notifications from the sidebar",
            "Clear Paid but not fulfilled first",
            "Handle Support SLA (tickets open >24h) and payout requests next",
            "Security signals go to Operations (admin)",
        ),
        tags=("notifications", "daily", "sla", "fulfill", "routine"),
        wizard_path="/admin/notifications",
        area="getting-started",
    ),
    HelpPlaybook(
        id="do-next-home",
        title="Use Do next (your daily queue)",
        problem="Want a short list of what to clear today instead of hunting the sidebar.",
        steps=(
            "Open Do next in Quick start (or the logo /admin/home)",
            "Clear red urgent items first (stuck orders, SLA tickets)",
            "Then soft reminders (creator follow-ups, Insider soon, payouts)",
            "Tickets assigned to you appear at the top when you have any",
        ),
        tags=("do-next", "home", "queue", "proactive", "daily", "notifications"),
        wizard_path="/admin/home",
        area="getting-started",
    ),
    HelpPlaybook(
        id="layout-shortcuts",
        title="Move the menu and use Your shortcuts",
        problem="Want the sidebar on the other side, or faster jumps to tools you use often.",
        steps=(
            "Top bar → A− / A / A+ / A++ — change word size for easier reading (saved on this browser)",
            "Top bar → Menu on right (or Menu on left) — moves the sidebar; saved on this browser",
            "Visit the tools you use most (Creator outreach, Order lookup, etc.)",
            "A Your shortcuts row appears under the top bar with your top pages",
            "Click Reset on that row if you want to clear learned shortcuts",
        ),
        tags=("shortcuts", "sidebar", "layout", "menu", "quick", "personalize", "text", "font", "size", "accessibility"),
        wizard_path="/admin/wizards",
        area="getting-started",
    ),
    HelpPlaybook(
        id="monday-routine",
        title="Weekly ops routine (Monday)",
        problem="Quick health check to keep the business running smoothly.",
        steps=(
            "Notifications — clear anything urgent (fulfillment, SLA, security)",
            "Finance — review revenue, margin, and pending affiliate liability",
            "Operations — scan external threats and run background tasks if Insider is due",
            "Support Inbox — assign open tickets and reply to anything over 24h",
            "Help → browse how-tos if something looks stuck",
        ),
        tags=("routine", "monday", "weekly", "checklist", "ops"),
        wizard_path="/admin/notifications",
        area="getting-started",
    ),
    HelpPlaybook(
        id="add-staff-user",
        title="Add a staff member",
        problem="New teammate needs a dashboard login.",
        steps=(
            "Open Add a staff member (admin only)",
            "Choose username, role (support / marketing / catalog / finance / legal), and password",
            "Save — share login privately; they should change password on first use if your process requires it",
            "Point them to Help → Getting started for their role checklist",
        ),
        tags=("staff", "login", "user", "onboarding", "admin"),
        wizard_path="/admin/staff-user",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="cloudflare-admin",
        title="Lock down /admin with Cloudflare",
        problem="Reduce brute-force risk on the staff dashboard.",
        steps=(
            "Cloudflare → Zero Trust → Access → protect api.noorlink.co/admin",
            "Require email OTP or team identity for /admin/*",
            "Ask engineering to set allowed office/home IPs as backup if needed",
        ),
        tags=("cloudflare", "access", "admin", "security"),
        wizard_path="/admin/operations",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="full-dashboard-docs",
        title="Read the full admin dashboard guide",
        problem="Need complete documentation of every sidebar section and role.",
        steps=(
            "Open Admin dashboard — full staff guide from the Help sidebar",
            "Or search Help for wizard names, roles, finance, operations",
        ),
        tags=("documentation", "guide", "dashboard", "help", "manual"),
        wizard_path="/admin/help?doc=admin-dashboard",
        doc_slug="admin-dashboard",
        area="getting-started",
    ),
    HelpPlaybook(
        id="developer-docs",
        title="Developer codebase reference",
        problem="Engineering team needs API routes, services, and migration list.",
        steps=(
            "Open Developer codebase guide (admin only)",
            "Search for api, webhook, migration, cron, fulfillment",
        ),
        tags=("developer", "code", "api", "architecture"),
        wizard_path="/admin/help?doc=developer-codebase",
        doc_slug="developer-codebase",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="onboarding-support",
        title="Support team — first day checklist",
        problem="New support staff need to know where tickets, orders, and read-only finance live.",
        steps=(
            "Notifications — check fulfillment failures and tickets over 24h",
            "Support Inbox — reply with templates; assign tickets to yourself",
            "Order lookup — verify email + order ID before sharing QR details",
            "Finance (read-only) — confirm charges when customers ask about billing",
            "Help → Customer paid but no eSIM if fulfillment is stuck",
        ),
        tags=("onboarding", "support", "checklist", "first-day"),
        wizard_path="/admin/support-inbox",
        roles=(ROLE_SUPPORT,),
        area="getting-started",
    ),
    HelpPlaybook(
        id="onboarding-marketing",
        title="Marketing team — first day checklist",
        problem="New marketing staff need promo, Insider, social, and outreach paths.",
        steps=(
            "Promo wizard — create codes; remember 20%+ needs admin approval",
            "Send Insider — test email first, then schedule",
            "Social media — upload partner media and copy captions for Meta",
            "Creator outreach — track creators and send branded partnership emails",
            "Help → Marketing area for more how-tos",
        ),
        tags=("onboarding", "marketing", "checklist", "insider", "promo", "outreach", "social"),
        wizard_path="/admin/promo-wizard",
        roles=(ROLE_MARKETING,),
        area="getting-started",
    ),
    HelpPlaybook(
        id="onboarding-catalog",
        title="Catalog team — first day checklist",
        problem="New catalog staff manage plans, SKUs, and provider mappings.",
        steps=(
            "Catalog overview — fix browse vs checkout mismatches",
            "Provider SKU browser — confirm Telna/Citrus SKUs before publishing",
            "Add travel plan wizard for new checkout packages",
            "Help → Telna API problems when fulfillment fails on a route",
        ),
        tags=("onboarding", "catalog", "checklist", "plans", "sku"),
        wizard_path="/admin/catalog-overview",
        roles=(ROLE_CATALOG,),
        area="getting-started",
    ),
    HelpPlaybook(
        id="onboarding-admin",
        title="Admin — first day checklist",
        problem="Full-access staff need finance, security, and ops paths.",
        steps=(
            "Pre-ship checklist doc — migrations, webhooks, cron before launch",
            "Finance — confirm Stripe live vs test badge before processing refunds",
            "Documents — upload legal/accounting papers; grant finance or legal roles when ready",
            "Operations → Security — review threats",
            "Privacy tools — GDPR export/delete when customers request data",
        ),
        tags=("onboarding", "admin", "checklist", "finance", "security"),
        wizard_path="/admin/finance",
        roles=(ROLE_ADMIN,),
        area="getting-started",
    ),
    HelpPlaybook(
        id="owner-lockout",
        title="Locked out of admin / rogue staff account",
        problem="Someone with admin access deactivated you or changed passwords.",
        steps=(
            "Use the owner recovery process with your break-glass secret (ask engineering if unsure)",
            "Disable the rogue account if needed",
            "Log in as owner, then rotate sessions",
            "Read Owner protection & break-glass in Help docs",
        ),
        tags=("owner", "security", "lockout", "recovery", "admin"),
        wizard_path="/admin/help?doc=owner-protection",
        doc_slug="owner-protection",
        roles=(ROLE_ADMIN,),
        area="admin",
    ),
    HelpPlaybook(
        id="document-vault",
        title="Store legal or accounting paperwork",
        problem="Need a private place for contracts, tax forms, and accounting files.",
        steps=(
            "Open Finance → Documents",
            "Upload PDF/Word/Excel with a clear title and category",
            "Use Admin only for highly sensitive originals",
            "Create finance or legal staff logins when those teams need access",
        ),
        tags=("documents", "legal", "accounting", "tax", "contracts", "vault"),
        wizard_path="/admin/documents",
        doc_slug="document-vault",
        roles=(ROLE_ADMIN, ROLE_FINANCE, ROLE_LEGAL),
        area="finance",
    ),
    HelpPlaybook(
        id="onboarding-finance",
        title="Finance team — first day checklist",
        problem="Finance staff need revenue views and the document vault.",
        steps=(
            "Finance dashboard — revenue, refunds, exports (admin still owns margin/exports)",
            "Documents — upload tax and accounting papers; download vault files",
            "Help → Finance area for refund and payout how-tos",
        ),
        tags=("onboarding", "finance", "checklist", "accounting", "documents"),
        wizard_path="/admin/documents",
        roles=(ROLE_FINANCE,),
        area="getting-started",
    ),
    HelpPlaybook(
        id="onboarding-legal",
        title="Legal team — first day checklist",
        problem="Legal staff need the company document vault.",
        steps=(
            "Documents — upload contracts, NDAs, and compliance files",
            "Mark highly sensitive originals as Admin only if needed",
            "Help → Legal & accounting document vault for access rules",
        ),
        tags=("onboarding", "legal", "checklist", "contracts", "documents"),
        wizard_path="/admin/documents",
        roles=(ROLE_LEGAL,),
        area="getting-started",
    ),
)


def _doc_by_slug(slug: str) -> Optional[HelpDoc]:
    for doc in HELP_DOCS:
        if doc.slug == slug:
            return doc
    return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _playbook_visible(playbook: HelpPlaybook, role: str) -> bool:
    if role in (ROLE_ADMIN, ROLE_OWNER):
        return True
    if not playbook.roles:
        return True
    return role in playbook.roles


def _can_view_doc(doc: HelpDoc, role: str) -> bool:
    if doc.audience == "dev" and role not in (ROLE_ADMIN, ROLE_OWNER):
        return False
    return True


def list_help_areas() -> List[dict]:
    return [
        {"key": key, "label": label, "summary": summary}
        for key, label, summary in HELP_AREAS
    ]


def get_playbook(playbook_id: str, *, role: str = ROLE_ADMIN) -> Optional[HelpPlaybook]:
    for playbook in PLAYBOOKS:
        if playbook.id == playbook_id and _playbook_visible(playbook, role):
            return playbook
    return None


def filter_playbooks(
    *,
    role: str = ROLE_ADMIN,
    query: str = "",
    area: str = "",
    tag: str = "",
) -> List[HelpPlaybook]:
    results = search_playbooks(query, role=role)
    area_key = (area or "").strip().lower()
    tag_key = (tag or "").strip().lower()
    if area_key:
        results = [p for p in results if p.area == area_key]
    if tag_key:
        results = [
            p
            for p in results
            if tag_key in {t.lower() for t in p.tags}
            or tag_key in _normalize(p.title)
            or tag_key in _normalize(p.problem)
        ]
    return results


def popular_tags(*, role: str = ROLE_ADMIN, limit: int = 24) -> List[str]:
    counts: Counter[str] = Counter()
    for playbook in PLAYBOOKS:
        if not _playbook_visible(playbook, role):
            continue
        for tag in playbook.tags:
            counts[tag.lower()] += 1
    return [tag for tag, _ in counts.most_common(limit)]


def search_playbooks(query: str, *, role: str = ROLE_ADMIN) -> List[HelpPlaybook]:
    needle = _normalize(query)
    if not needle:
        return [p for p in PLAYBOOKS if _playbook_visible(p, role)]

    scored: List[tuple[int, HelpPlaybook]] = []
    for playbook in PLAYBOOKS:
        if not _playbook_visible(playbook, role):
            continue
        haystack = _normalize(
            " ".join(
                [
                    playbook.title,
                    playbook.problem,
                    playbook.area,
                    *playbook.steps,
                    *playbook.tags,
                ]
            )
        )
        if needle in haystack:
            score = haystack.count(needle)
            if playbook.title.lower().startswith(needle):
                score += 10
            scored.append((score, playbook))

    scored.sort(key=lambda item: (-item[0], item[1].title))
    return [item[1] for item in scored]


def _excerpt(content: str, query: str, *, radius: int = 120) -> str:
    if not query.strip():
        return content[:280].strip() + ("…" if len(content) > 280 else "")

    needle = query.strip().lower()
    lowered = content.lower()
    idx = lowered.find(needle)
    if idx < 0:
        return content[:280].strip() + ("…" if len(content) > 280 else "")

    start = max(0, idx - radius)
    end = min(len(content), idx + len(needle) + radius)
    snippet = content[start:end].replace("\n", " ").strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    return f"{prefix}{snippet}{suffix}"


def search_docs(query: str, *, role: str) -> List[DocSearchHit]:
    needle = _normalize(query)
    hits: List[DocSearchHit] = []

    for doc in HELP_DOCS:
        if not _can_view_doc(doc, role):
            continue
        path = DOCS_DIR / doc.filename
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        haystack = _normalize(
            " ".join([doc.title, doc.summary, doc.slug, content])
        )
        if needle and needle not in haystack:
            continue
        score = haystack.count(needle) if needle else 1
        if doc.pinned and not needle:
            score += 5
        if needle and needle in _normalize(doc.title):
            score += 8
        hits.append(
            DocSearchHit(
                slug=doc.slug,
                title=doc.title,
                audience=doc.audience,
                excerpt=_excerpt(content, query),
                score=score,
            )
        )

    hits.sort(key=lambda h: (-h.score, h.title))
    return hits


def load_doc_markdown(slug: str, *, role: str = ROLE_ADMIN) -> Optional[str]:
    doc = _doc_by_slug(slug)
    if doc is None:
        return None
    if not _can_view_doc(doc, role):
        return None
    path = DOCS_DIR / doc.filename
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def get_doc_meta(slug: str) -> Optional[HelpDoc]:
    return _doc_by_slug(slug)


def list_doc_summaries(*, role: str) -> List[dict]:
    rows: List[dict] = []
    for doc in HELP_DOCS:
        if not _can_view_doc(doc, role):
            continue
        path = DOCS_DIR / doc.filename
        rows.append(
            {
                "slug": doc.slug,
                "filename": doc.filename,
                "title": doc.title,
                "summary": doc.summary,
                "audience": doc.audience,
                "pinned": doc.pinned,
                "available": path.is_file(),
            }
        )
    return rows


def markdown_to_safe_html(text: str) -> str:
    """Minimal read-only markdown rendering (headings, lists, code, paragraphs)."""
    parts: List[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            parts.append("</ul>")
            in_list = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            close_list()
            parts.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            close_list()
            parts.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("# "):
            close_list()
            parts.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("| ") and "---" not in line:
            close_list()
            cells = [html.escape(c.strip()) for c in line.strip("|").split("|")]
            parts.append(f"<p class=\"small\"><code>{' | '.join(cells)}</code></p>")
        elif line.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip() == "":
            close_list()
        else:
            close_list()
            escaped = html.escape(line)
            escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
            if line.startswith("    ") or line.startswith("\t"):
                parts.append(f"<pre class=\"nl-doc-code\">{escaped}</pre>")
            else:
                parts.append(f"<p>{escaped}</p>")

    close_list()
    return "\n".join(parts)
