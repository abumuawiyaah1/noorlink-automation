"""Help center playbooks, full documentation search, and read-only doc viewer."""

from __future__ import annotations

import html
import re
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

# Legacy slug map for playbooks that reference old keys
DOC_SLUG_ALIASES = {
    "telna-runbook": "telna-runbook",
    "stripe-wallets": "stripe-wallets",
    "breakage-fulfillment": "breakage-fulfillment",
}

PLAYBOOKS: Tuple[HelpPlaybook, ...] = (
    HelpPlaybook(
        id="no-esim-after-payment",
        title="Customer paid but didn't get eSIM",
        problem="Stripe charge succeeded but no QR / activation email arrived.",
        steps=(
            "Look up the order in Order lookup",
            "If status is paid with no QR, open Fulfill stuck order",
            "If already delivered, use Resend eSIM email on the order",
        ),
        tags=("webhook", "stripe", "fulfillment", "qr", "email", "paid"),
        wizard_path="/admin/fulfill-order",
        doc_slug="stripe-wallets",
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
        tags=("suspended", "data", "cap", "usage", "citrus", "simbase"),
        wizard_path="/admin/suspended-orders",
        doc_slug="breakage-fulfillment",
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
        tags=("support", "auto", "automatic", "qr", "inbox", "bot", "self-serve"),
        wizard_path="/admin/support-inbox",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
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
        tags=("support", "ticket", "email", "customer", "help"),
        wizard_path="/admin/help-customer",
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
        tags=("promo", "discount", "checkout", "approval"),
        wizard_path="/admin/promo-wizard",
        roles=(ROLE_ADMIN, ROLE_MARKETING, ROLE_CATALOG),
    ),
    HelpPlaybook(
        id="insider-send",
        title="Send Insider newsletter",
        problem="Monthly newsletter or special issue needs to go out.",
        steps=(
            "Create the issue in Send Insider wizard",
            "Send a test email to yourself first",
            "Schedule send date — cron delivers on that day",
        ),
        tags=("insider", "newsletter", "email", "marketing"),
        wizard_path="/admin/insider-wizard",
        roles=(ROLE_ADMIN, ROLE_MARKETING),
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
        tags=("telna", "provider", "catalog", "sku", "api", "403"),
        wizard_path="/admin/provider-catalog",
        doc_slug="telna-runbook",
        roles=(ROLE_ADMIN, ROLE_CATALOG),
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
    ),
    HelpPlaybook(
        id="gift-order",
        title="Gift eSIM — wrong recipient or resend",
        problem="Gift buyer needs QR sent to recipient or order details checked.",
        steps=(
            "Order lookup shows gift recipient and sender",
            "Resend eSIM email goes to the gift recipient automatically",
        ),
        tags=("gift", "recipient", "email", "qr"),
        wizard_path="/admin/order-insight",
    ),
    HelpPlaybook(
        id="affiliate-payout",
        title="Pay an affiliate partner",
        problem="Approved commissions ready to mark as paid.",
        steps=(
            "Send payment via PayPal/Wise/bank",
            "Record affiliate payout wizard marks commissions paid",
        ),
        tags=("affiliate", "payout", "commission"),
        wizard_path="/admin/affiliate-payout",
        roles=(ROLE_ADMIN,),
    ),
    HelpPlaybook(
        id="email-delivery",
        title="Emails not sending",
        problem="Customers or staff not receiving transactional email.",
        steps=(
            "Operations → Admin → Email probe script",
            "Confirm RESEND_FROM_EMAIL uses @noorlink.co",
            "Check spam; Resend dashboard for bounces",
        ),
        tags=("email", "resend", "delivery", "noreply"),
        wizard_path="/admin/diagnostics",
        doc_slug="stripe-wallets",
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
        tags=("refund", "stripe", "chargeback", "money"),
        wizard_path="/admin/refund-order",
    ),
    HelpPlaybook(
        id="finance-review",
        title="Monthly revenue and margin review",
        problem="Need a snapshot of business performance.",
        steps=(
            "Open Finance dashboard for revenue, margin, and affiliate liability",
            "Export orders CSV for accounting",
            "Send monthly summary email to ops inbox",
        ),
        tags=("finance", "revenue", "margin", "accounting", "csv"),
        wizard_path="/admin/finance",
        roles=(ROLE_ADMIN, ROLE_SUPPORT),
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
        tags=("webhook", "event", "log", "stripe", "fulfillment", "debug"),
        wizard_path="/admin/event-log",
    ),
    HelpPlaybook(
        id="security-threats",
        title="Suspicious login or API activity",
        problem="Failed admin logins, bad Stripe webhooks, or unauthorized API probes.",
        steps=(
            "Open Operations → Security → External threats",
            "Check repeated IPs on failed admin login",
            "Ops email/Slack fires automatically after 5 failures from one IP in 60 minutes",
            "Filter Event log by type security_ for full history",
            "If Cloudflare is in front, review WAF/firewall events and block abusive IPs",
        ),
        tags=("security", "login", "webhook", "unauthorized", "threat", "brute force", "waf"),
        wizard_path="/admin/operations",
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
            "Help → search if something looks stuck (webhook, Telna, email)",
        ),
        tags=("routine", "monday", "weekly", "checklist", "ops", "health"),
        wizard_path="/admin/notifications",
    ),
    HelpPlaybook(
        id="cloudflare-admin",
        title="Lock down /admin with Cloudflare",
        problem="Reduce brute-force risk on the staff dashboard.",
        steps=(
            "Cloudflare → Zero Trust → Access → add application for api.noorlink.co/admin",
            "Require email OTP or team identity provider for /admin/*",
            "Set ADMIN_ALLOWED_IPS on Railway to your office/home IPs as backup",
            "Enable WAF managed rules and bot fight mode on the zone",
        ),
        tags=("cloudflare", "access", "admin", "security", "waf", "2fa", "ip"),
        wizard_path="/admin/operations",
    ),
    HelpPlaybook(
        id="full-dashboard-docs",
        title="Read the full admin dashboard guide",
        problem="Need complete documentation of every sidebar section and role.",
        steps=(
            "Open Admin dashboard — full staff guide from the sidebar",
            "Or search Help for wizard names, roles, finance, operations",
        ),
        tags=("documentation", "guide", "dashboard", "admin", "help", "manual", "reference"),
        wizard_path="/admin/help?doc=admin-dashboard",
        doc_slug="admin-dashboard",
    ),
    HelpPlaybook(
        id="developer-docs",
        title="Developer codebase reference",
        problem="Engineering team needs API routes, services, and migration list.",
        steps=(
            "Open Developer codebase guide (admin only)",
            "Search for api, webhook, migration, cron, fulfillment",
        ),
        tags=("developer", "code", "api", "architecture", "engineering", "research"),
        wizard_path="/admin/help?doc=developer-codebase",
        doc_slug="developer-codebase",
        roles=(ROLE_ADMIN,),
    ),
    HelpPlaybook(
        id="onboarding-support",
        title="Support team — first day checklist",
        problem="New support staff need to know where tickets, orders, and read-only finance live.",
        steps=(
            "Notifications — check fulfillment failures and tickets over 24h",
            "Support Inbox — reply with templates; assign tickets to yourself",
            "Order lookup wizard — verify email + order ID before sharing QR details",
            "Finance (read-only) — confirm charges when customers ask about billing",
            "Help → Customer paid but no eSIM if fulfillment is stuck",
        ),
        tags=("onboarding", "support", "checklist", "first day", "staff"),
        wizard_path="/admin/support-inbox",
        roles=(ROLE_SUPPORT,),
    ),
    HelpPlaybook(
        id="onboarding-marketing",
        title="Marketing team — first day checklist",
        problem="New marketing staff need promo, Insider, and analytics paths.",
        steps=(
            "Promo wizard — create codes; remember 20%+ needs admin approval",
            "Send Insider wizard — test email first, then schedule",
            "Insights — review promo performance and Insider send counts",
            "Help → Promo code rejected if customers report checkout issues",
        ),
        tags=("onboarding", "marketing", "checklist", "insider", "promo"),
        wizard_path="/admin/promo-wizard",
        roles=(ROLE_MARKETING,),
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
    ),
    HelpPlaybook(
        id="onboarding-admin",
        title="Admin — first day checklist",
        problem="Full-access staff need finance, security, and ops paths.",
        steps=(
            "Pre-ship checklist doc — migrations, webhooks, cron before launch",
            "Finance — confirm Stripe live vs test badge before processing refunds",
            "Documents — upload legal/accounting papers; grant finance or legal roles when ready",
            "Operations → Security — review threats and set ADMIN_ALLOWED_IPS",
            "Backup & restore doc — know Supabase PITR and weekly CSV exports",
            "Privacy tools — GDPR export/delete when customers request data",
        ),
        tags=("onboarding", "admin", "checklist", "finance", "security"),
        wizard_path="/admin/finance",
        roles=(ROLE_ADMIN,),
    ),
    HelpPlaybook(
        id="owner-lockout",
        title="Locked out of admin / rogue staff account",
        problem="Someone with admin access deactivated you or changed passwords.",
        steps=(
            "Use Railway CLI with OWNER_RECOVERY_SECRET — scripts/recover_owner.py",
            "Optionally set DEACTIVATE_USERNAME to disable the rogue account",
            "Log in as owner, then rotate SECRET_KEY to kill old sessions",
            "Read Owner protection & break-glass in Help docs",
        ),
        tags=("owner", "security", "lockout", "break-glass", "recovery", "admin"),
        wizard_path="/admin/help?doc=owner-protection",
        doc_slug="owner-protection",
        roles=(ROLE_ADMIN,),
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
        tags=("documents", "legal", "accounting", "tax", "contracts", "vault", "upload"),
        wizard_path="/admin/documents",
        doc_slug="document-vault",
        roles=(ROLE_ADMIN, ROLE_FINANCE, ROLE_LEGAL),
    ),
    HelpPlaybook(
        id="onboarding-finance",
        title="Finance team — first day checklist",
        problem="Finance staff need revenue views and the document vault.",
        steps=(
            "Finance dashboard — revenue, refunds, exports (admin still owns margin/exports)",
            "Documents — upload tax and accounting papers; download vault files",
            "Help → search refund or finance if a charge dispute arrives",
        ),
        tags=("onboarding", "finance", "checklist", "accounting", "documents"),
        wizard_path="/admin/documents",
        roles=(ROLE_FINANCE,),
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


def search_playbooks(query: str, *, role: str = ROLE_ADMIN) -> List[HelpPlaybook]:
    needle = _normalize(query)
    if not needle:
        return [p for p in PLAYBOOKS if _playbook_visible(p, role)]

    scored: List[tuple[int, HelpPlaybook]] = []
    for playbook in PLAYBOOKS:
        if not _playbook_visible(playbook, role):
            continue
        haystack = _normalize(
            " ".join([playbook.title, playbook.problem, *playbook.steps, *playbook.tags])
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
