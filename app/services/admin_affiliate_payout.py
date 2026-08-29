"""Affiliate payout wizard — record payouts and mark commissions paid."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import Affiliate, AffiliateCommission, AffiliatePayout
from app.services.affiliates import DEFAULTS


class AdminAffiliatePayoutError(Exception):
    """Affiliate payout wizard failed."""


def list_payout_candidates() -> List[Dict[str, Any]]:
    factory = get_session_factory()
    if factory is None:
        return []

    rows: List[Dict[str, Any]] = []
    with factory() as session:
        affiliates = session.scalars(
            select(Affiliate).where(Affiliate.status == "active").order_by(Affiliate.code)
        ).all()
        for affiliate in affiliates:
            if affiliate.type == "customer":
                continue
            commissions = session.scalars(
                select(AffiliateCommission)
                .where(AffiliateCommission.affiliate_id == affiliate.id)
                .where(AffiliateCommission.status == "approved")
            ).all()
            balance = sum(int(c.commission_cents) for c in commissions)
            minimum = int(
                affiliate.payout_minimum_cents
                or DEFAULTS.get(affiliate.type, {}).get("payout_minimum_cents", 2500)
            )
            rows.append(
                {
                    "affiliate_id": str(affiliate.id),
                    "code": affiliate.code,
                    "display_name": affiliate.display_name or affiliate.organization_name or affiliate.code,
                    "type": affiliate.type,
                    "payout_email": affiliate.payout_email or affiliate.contact_email,
                    "balance_cents": balance,
                    "minimum_cents": minimum,
                    "commission_count": len(commissions),
                    "ready": balance >= minimum and balance > 0,
                }
            )
    return rows


def record_affiliate_payout(
    *,
    affiliate_id: str,
    method: str,
    reference: str,
    notes: str,
) -> Dict[str, Any]:
    try:
        affiliate_uuid = UUID(affiliate_id.strip())
    except ValueError as exc:
        raise AdminAffiliatePayoutError("Invalid affiliate selected.") from exc

    factory = get_session_factory()
    if factory is None:
        raise AdminAffiliatePayoutError("DATABASE_URL is required.")

    with factory() as session:
        affiliate = session.get(Affiliate, affiliate_uuid)
        if affiliate is None:
            raise AdminAffiliatePayoutError("Affiliate not found.")
        if affiliate.type == "customer":
            raise AdminAffiliatePayoutError("Customer referral affiliates are not paid in cash.")

        commissions = session.scalars(
            select(AffiliateCommission)
            .where(AffiliateCommission.affiliate_id == affiliate.id)
            .where(AffiliateCommission.status == "approved")
        ).all()
        amount_cents = sum(int(c.commission_cents) for c in commissions)
        minimum = int(
            affiliate.payout_minimum_cents
            or DEFAULTS.get(affiliate.type, {}).get("payout_minimum_cents", 2500)
        )
        if amount_cents < minimum:
            raise AdminAffiliatePayoutError(
                f"Balance ${amount_cents / 100:.2f} is below minimum ${minimum / 100:.2f}."
            )
        if amount_cents <= 0:
            raise AdminAffiliatePayoutError("No approved commissions to pay.")

        now = datetime.now(timezone.utc)
        payout = AffiliatePayout(
            id=uuid4(),
            affiliate_id=affiliate.id,
            amount_cents=amount_cents,
            method=(method or "manual").strip() or "manual",
            reference=(reference or "").strip() or None,
            notes=(notes or "").strip() or None,
            paid_at=now,
        )
        session.add(payout)
        session.flush()

        for commission in commissions:
            commission.status = "paid"
            commission.payout_id = payout.id

        session.commit()
        affiliate_code = affiliate.code

    try:
        from app.services.affiliate_payout_requests import mark_requests_paid_for_affiliate

        mark_requests_paid_for_affiliate(
            affiliate_id=str(affiliate_uuid),
            attended_by="payout_wizard",
        )
    except Exception:
        pass

    return {
        "affiliate_code": affiliate_code,
        "amount_cents": amount_cents,
        "commission_count": len(commissions),
        "payout_id": str(payout.id),
    }
