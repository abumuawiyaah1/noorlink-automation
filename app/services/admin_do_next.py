"""Personal 'Do next' queue + soft proactive reminders for staff home."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from sqlalchemy import func, or_, select

from app.admin.roles import (
    PROMO_MANAGER_ROLES,
    ROLE_ADMIN,
    ROLE_OWNER,
)
from app.db.engine import get_session_factory
from app.db.models import InsiderIssue, SupportTicket
from app.db.models.creator_outreach import CreatorOutreachContact
from app.services.admin_notifications import AdminNotification, notifications_for_role
from app.services.affiliate_payout_requests import list_open_payout_requests


@dataclass(frozen=True)
class DoNextItem:
    key: str
    title: str
    detail: str
    count: int
    severity: str  # urgent | warning | info | soft
    link_path: str
    cta: str = "Open"


def _role_sees(role: str, roles: Tuple[str, ...]) -> bool:
    if role in (ROLE_ADMIN, ROLE_OWNER):
        return True
    return role in roles


def _count_creators_needing_outreach() -> int:
    """Never contacted, or messaged 7+ days ago with no reply/posted/closed."""
    factory = get_session_factory()
    if factory is None:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        with factory() as session:
            never = session.scalar(
                select(func.count())
                .select_from(CreatorOutreachContact)
                .where(CreatorOutreachContact.status == "to_contact")
            ) or 0
            stale = session.scalar(
                select(func.count())
                .select_from(CreatorOutreachContact)
                .where(CreatorOutreachContact.status == "messaged")
                .where(
                    or_(
                        CreatorOutreachContact.last_email_at.is_(None),
                        CreatorOutreachContact.last_email_at < cutoff,
                    )
                )
            ) or 0
            return int(never) + int(stale)
    except Exception:
        # Table may not exist yet if migration pending
        return 0


def _count_insider_upcoming(days: int = 7) -> int:
    """Scheduled Insider issues sending within the next N days (nudge to test)."""
    factory = get_session_factory()
    if factory is None:
        return 0
    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=days)
    try:
        with factory() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(InsiderIssue)
                    .where(InsiderIssue.status == "scheduled")
                    .where(InsiderIssue.send_at > now)
                    .where(InsiderIssue.send_at <= soon)
                )
                or 0
            )
    except Exception:
        return 0


def _count_tickets_assigned_to(username: str) -> int:
    if not username:
        return 0
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(SupportTicket)
                .where(SupportTicket.assigned_to == username)
                .where(SupportTicket.status.in_(("open", "waiting")))
            )
            or 0
        )


def soft_reminders_for_role(role: str) -> List[AdminNotification]:
    """Proactive nudges (info) — not only red alerts."""
    items: List[AdminNotification] = []

    def add(item: AdminNotification) -> None:
        if _role_sees(role, item.roles) and item.count > 0:
            items.append(item)

    creators = _count_creators_needing_outreach()
    add(
        AdminNotification(
            key="creator-followup",
            title="Creators need a follow-up",
            detail="Not contacted yet, or messaged 7+ days ago — open Creator outreach.",
            count=creators,
            severity="info",
            link_path="/admin/creator-outreach",
            roles=PROMO_MANAGER_ROLES,
        )
    )

    insider_soon = _count_insider_upcoming(7)
    add(
        AdminNotification(
            key="insider-upcoming",
            title="Insider sending within 7 days",
            detail="Send a test to yourself before it goes live.",
            count=insider_soon,
            severity="info",
            link_path="/admin/insider-wizard",
            roles=PROMO_MANAGER_ROLES,
        )
    )

    if _role_sees(role, (ROLE_ADMIN,)):
        try:
            payouts = len(list_open_payout_requests())
        except Exception:
            payouts = 0
        add(
            AdminNotification(
                key="affiliate-payouts",
                title="Affiliate payouts waiting",
                detail="Partners are waiting — attend within 72 hours when you can.",
                count=payouts,
                severity="info",
                link_path="/admin/affiliate-payout",
                roles=(ROLE_ADMIN,),
            )
        )

    return items


def do_next_for_user(*, role: str, username: str = "", limit: int = 6) -> List[DoNextItem]:
    """
    Personal action queue: urgent/warning first, then soft reminders,
    plus tickets assigned to this person.
    """
    items: List[DoNextItem] = []
    seen: set[str] = set()

    def push(item: DoNextItem) -> None:
        if item.key in seen or item.count <= 0:
            return
        seen.add(item.key)
        items.append(item)

    # Tickets assigned to me (personal)
    mine = _count_tickets_assigned_to(username)
    push(
        DoNextItem(
            key="my-tickets",
            title="Tickets assigned to you",
            detail="Reply or close — customers are waiting on your thread.",
            count=mine,
            severity="warning",
            link_path="/admin/support-inbox",
            cta="Open inbox",
        )
    )

    for n in notifications_for_role(role):
        push(
            DoNextItem(
                key=n.key,
                title=n.title,
                detail=n.detail,
                count=n.count,
                severity=n.severity,
                link_path=n.link_path,
                cta="Fix now" if n.severity == "urgent" else "Open",
            )
        )

    for n in soft_reminders_for_role(role):
        push(
            DoNextItem(
                key=n.key,
                title=n.title,
                detail=n.detail,
                count=n.count,
                severity="soft",
                link_path=n.link_path,
                cta="Take a look",
            )
        )

    severity_order = {"urgent": 0, "warning": 1, "info": 2, "soft": 3}
    items.sort(key=lambda x: (severity_order.get(x.severity, 9), -x.count))
    return items[:limit]


def notifications_with_soft_reminders(role: str) -> List[AdminNotification]:
    """Urgent/warning notifications plus soft proactive reminders for the Notifications hub."""
    base = list(notifications_for_role(role))
    soft = soft_reminders_for_role(role)
    # Avoid duplicate keys if any overlap
    keys = {n.key for n in base}
    for item in soft:
        if item.key not in keys:
            base.append(item)
    severity_order = {"urgent": 0, "warning": 1, "info": 2}
    base.sort(key=lambda n: (severity_order.get(n.severity, 9), -n.count))
    return base
