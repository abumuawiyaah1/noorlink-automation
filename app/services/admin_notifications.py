"""In-dashboard notifications — live counts with links to fix things."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from sqlalchemy import func, select

from app.admin.roles import (
    CATALOG_MANAGER_ROLES,
    PROMO_MANAGER_ROLES,
    ROLE_ADMIN,
    ROLE_SUPPORT,
)
from app.db.engine import get_session_factory
from app.db.models import EsimPackage, Order, PlanFulfillmentMap, PromoCode, SupportTicket
from app.services.admin_operations import get_operations_summary
from app.services.promo_codes import HIGH_DISCOUNT_APPROVAL_THRESHOLD, requires_admin_approval

from app.services.admin_support_sla import sla_summary
from app.services.security_threats import security_threats_summary


@dataclass(frozen=True)
class AdminNotification:
    key: str
    title: str
    detail: str
    count: int
    severity: str  # info | warning | urgent
    link_path: str
    roles: Tuple[str, ...]


def _count_pending_promos() -> int:
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        promos = session.scalars(select(PromoCode).where(PromoCode.is_active.is_(True))).all()
        return sum(
            1
            for promo in promos
            if not promo.admin_approved and requires_admin_approval(promo.percent_off)
        )


def _count_pending_catalog() -> int:
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        plans = session.scalar(
            select(func.count())
            .select_from(EsimPackage)
            .where(EsimPackage.is_active.is_(True))
            .where(EsimPackage.admin_approved.is_(False))
        ) or 0
        routes = session.scalar(
            select(func.count())
            .select_from(PlanFulfillmentMap)
            .where(PlanFulfillmentMap.is_active.is_(True))
            .where(PlanFulfillmentMap.admin_approved.is_(False))
        ) or 0
        pending_prices = session.scalar(
            select(func.count())
            .select_from(EsimPackage)
            .where(EsimPackage.pending_price_cents.is_not(None))
        ) or 0
        return int(plans) + int(routes) + int(pending_prices)


def _count_open_unassigned_tickets() -> int:
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        return session.scalar(
            select(func.count())
            .select_from(SupportTicket)
            .where(SupportTicket.status == "open")
            .where(SupportTicket.assigned_to.is_(None))
        ) or 0


def _count_device_catalog_review() -> int:
    try:
        from app.services.device_catalog_monitor import device_catalog_notification_count

        return device_catalog_notification_count()
    except Exception:
        return 0


def notifications_for_role(role: str) -> List[AdminNotification]:
    summary = get_operations_summary()
    items: List[AdminNotification] = []

    def add(item: AdminNotification) -> None:
        if role == ROLE_ADMIN or role in item.roles:
            if item.count > 0:
                items.append(item)

    add(
        AdminNotification(
            key="pending-fulfillment",
            title="Orders paid but not fulfilled",
            detail="Stripe succeeded but no QR email went out — use Fulfill stuck order.",
            count=int(summary.get("pending_fulfillment") or 0),
            severity="urgent",
            link_path="/admin/fulfill-order",
            roles=(ROLE_ADMIN, ROLE_SUPPORT),
        )
    )
    add(
        AdminNotification(
            key="suspended-orders",
            title="Suspended orders",
            detail="Data cap or balance depleted — review before reactivating.",
            count=int(summary.get("suspended_count") or 0),
            severity="warning",
            link_path="/admin/suspended-orders",
            roles=(ROLE_ADMIN, ROLE_SUPPORT),
        )
    )
    add(
        AdminNotification(
            key="open-tickets",
            title="Unassigned support tickets",
            detail="Customers waiting — open Support Inbox and assign.",
            count=_count_open_unassigned_tickets(),
            severity="warning",
            link_path="/admin/support-inbox",
            roles=(ROLE_ADMIN, ROLE_SUPPORT),
        )
    )
    add(
        AdminNotification(
            key="promo-approval",
            title="Promo codes need approval",
            detail=f"Discounts above {HIGH_DISCOUNT_APPROVAL_THRESHOLD}% require admin sign-off.",
            count=_count_pending_promos(),
            severity="warning",
            link_path="/admin/promo-code/list",
            roles=(ROLE_ADMIN,),
        )
    )
    add(
        AdminNotification(
            key="catalog-approval",
            title="Catalog changes need approval",
            detail="Plans, routes, or price changes waiting for admin.",
            count=_count_pending_catalog(),
            severity="warning",
            link_path="/admin/esim-package/list",
            roles=(ROLE_ADMIN,),
        )
    )
    add(
        AdminNotification(
            key="insider-due",
            title="Insider issues due to send",
            detail="Scheduled newsletter ready for the next cron run.",
            count=int(summary.get("due_insider_issues") or 0),
            severity="info",
            link_path="/admin/insider-issue/list",
            roles=PROMO_MANAGER_ROLES,
        )
    )

    sla = sla_summary()
    add(
        AdminNotification(
            key="support-sla",
            title="Support tickets waiting over 24 hours",
            detail="Customers may be waiting — assign and reply in Support Inbox.",
            count=int(sla.get("waiting_over_24h") or 0),
            severity="urgent" if sla.get("unassigned_over_24h") else "warning",
            link_path="/admin/support-inbox",
            roles=(ROLE_ADMIN, ROLE_SUPPORT),
        )
    )

    threats = security_threats_summary(hours=24)
    if threats.get("needs_attention"):
        threat_count = int(threats.get("urgent_count") or 0) or int(threats.get("total") or 0)
        add(
            AdminNotification(
                key="security-threats",
                title="External security signals (24h)",
                detail="Failed logins, bad webhooks, or unauthorized API probes — review in Operations.",
                count=threat_count,
                severity="urgent" if threats.get("repeated_login_ips") else "warning",
                link_path="/admin/operations",
                roles=(ROLE_ADMIN,),
            )
        )

    add(
        AdminNotification(
            key="device-catalog",
            title="eSIM device catalog needs review",
            detail="New models in the reference list or repeated failed device checks — update devices.py.",
            count=_count_device_catalog_review(),
            severity="warning",
            link_path="/admin/system-diagnostics",
            roles=(ROLE_ADMIN,),
        )
    )

    severity_order = {"urgent": 0, "warning": 1, "info": 2}
    items.sort(key=lambda n: (severity_order.get(n.severity, 9), -n.count))
    return items


def notification_badge_count(role: str) -> int:
    return len(notifications_for_role(role))
