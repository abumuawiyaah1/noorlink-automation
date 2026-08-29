"""
Affiliate payout requests + 72h unanswered auto-approve.

Important: We cannot send PayPal/Wise automatically without a payout API.
After 72h (strict rules), we auto-APPROVE the request and escalate loudly so
you send funds, then mark paid in the wizard. Partner is told it was approved.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import Affiliate, AffiliatePayoutRequest
from app.services.email_brand import wrap_branded_email
from app.services.email_service import EmailDeliveryError, send_email
from app.services.ops_alerts import notify_staff_governance
from app.services.ops_event_log import log_ops_event

logger = logging.getLogger(__name__)

AUTO_PAYOUT_WAIT_HOURS = 72
AUTO_PAYOUT_MAX_CENTS = 50000  # $500
AUTO_PAYOUT_ACTOR = "auto-72h"


class AffiliatePayoutRequestError(Exception):
    """Payout request could not be created or processed."""


def _wait_hours() -> int:
    settings = get_settings()
    raw = getattr(settings, "affiliate_auto_payout_wait_hours", None)
    try:
        value = int(raw) if raw is not None and str(raw).strip() != "" else AUTO_PAYOUT_WAIT_HOURS
    except (TypeError, ValueError):
        value = AUTO_PAYOUT_WAIT_HOURS
    return max(1, value)


def _max_cents() -> int:
    settings = get_settings()
    raw = getattr(settings, "affiliate_auto_payout_max_cents", None)
    try:
        value = int(raw) if raw is not None and str(raw).strip() != "" else AUTO_PAYOUT_MAX_CENTS
    except (TypeError, ValueError):
        value = AUTO_PAYOUT_MAX_CENTS
    return max(100, value)


def create_payout_request(
    *,
    affiliate_id: str,
    affiliate_code: str,
    requested_by_email: str,
    payout_email: str,
    amount_cents: int,
) -> Dict[str, Any]:
    factory = get_session_factory()
    if factory is None:
        raise AffiliatePayoutRequestError("DATABASE_URL is required.")

    # One open request per affiliate
    with factory() as session:
        existing = session.scalar(
            select(AffiliatePayoutRequest)
            .where(AffiliatePayoutRequest.affiliate_id == UUID(affiliate_id))
            .where(AffiliatePayoutRequest.status.in_(("pending", "approved_auto")))
            .order_by(AffiliatePayoutRequest.created_at.desc())
            .limit(1)
        )
        if existing is not None:
            raise AffiliatePayoutRequestError(
                "A payout request is already open for this partner. "
                "We’ll process it — typically within 5 business days "
                f"(auto-escalates after {_wait_hours()} hours if unattended)."
            )

        now = datetime.now(timezone.utc)
        row = AffiliatePayoutRequest(
            id=uuid4(),
            affiliate_id=UUID(affiliate_id),
            affiliate_code=affiliate_code,
            requested_by_email=requested_by_email.strip().lower(),
            payout_email=(payout_email or "").strip().lower() or None,
            amount_cents=int(amount_cents),
            status="pending",
            created_at=now,
            updated_at=now,
            metadata_={},
        )
        session.add(row)
        session.commit()
        return {
            "id": str(row.id),
            "status": row.status,
            "amount_cents": row.amount_cents,
            "wait_hours": _wait_hours(),
        }


def list_open_payout_requests() -> List[Dict[str, Any]]:
    factory = get_session_factory()
    if factory is None:
        return []
    with factory() as session:
        rows = session.scalars(
            select(AffiliatePayoutRequest)
            .where(AffiliatePayoutRequest.status.in_(("pending", "approved_auto")))
            .order_by(AffiliatePayoutRequest.created_at.asc())
        ).all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            age_h = 0
            if row.created_at:
                created = row.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_h = int((datetime.now(timezone.utc) - created).total_seconds() // 3600)
            out.append(
                {
                    "id": str(row.id),
                    "affiliate_id": str(row.affiliate_id),
                    "affiliate_code": row.affiliate_code,
                    "requested_by_email": row.requested_by_email,
                    "payout_email": row.payout_email,
                    "amount_cents": row.amount_cents,
                    "status": row.status,
                    "age_hours": age_h,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "auto_approved_at": row.auto_approved_at.isoformat() if row.auto_approved_at else None,
                }
            )
        return out


def mark_requests_paid_for_affiliate(*, affiliate_id: str, attended_by: str) -> int:
    """Close open requests when staff records a real payout."""
    factory = get_session_factory()
    if factory is None:
        return 0
    now = datetime.now(timezone.utc)
    count = 0
    with factory() as session:
        rows = session.scalars(
            select(AffiliatePayoutRequest)
            .where(AffiliatePayoutRequest.affiliate_id == UUID(affiliate_id))
            .where(AffiliatePayoutRequest.status.in_(("pending", "approved_auto")))
        ).all()
        for row in rows:
            row.status = "paid"
            row.attended_at = now
            row.attended_by = attended_by
            row.updated_at = now
            count += 1
        session.commit()
    return count


def acknowledge_payout_request(*, request_id: str, attended_by: str) -> None:
    """Staff viewed/claimed the request before sending money — stops 72h auto-approve."""
    factory = get_session_factory()
    if factory is None:
        raise AffiliatePayoutRequestError("DATABASE_URL is required.")
    now = datetime.now(timezone.utc)
    with factory() as session:
        row = session.get(AffiliatePayoutRequest, UUID(request_id))
        if row is None:
            raise AffiliatePayoutRequestError("Payout request not found.")
        if row.status not in {"pending", "approved_auto"}:
            raise AffiliatePayoutRequestError(f"Request is already {row.status}.")
        row.attended_at = now
        row.attended_by = attended_by
        row.updated_at = now
        # Keep pending so they still send money; attended stops auto cron
        session.commit()


def evaluate_strict_auto_approve(row: AffiliatePayoutRequest, affiliate: Affiliate) -> None:
    if row.attended_at is not None:
        raise AffiliatePayoutRequestError("Staff already attended this request.")
    if affiliate.status != "active":
        raise AffiliatePayoutRequestError("Affiliate is not active.")
    if affiliate.type == "customer":
        raise AffiliatePayoutRequestError("Customer affiliates are not cash-paid.")
    if row.amount_cents > _max_cents():
        raise AffiliatePayoutRequestError(
            f"Amount ${row.amount_cents / 100:.2f} exceeds auto-approve cap "
            f"(${_max_cents() / 100:.2f})."
        )
    if not (row.payout_email or affiliate.payout_email or affiliate.contact_email):
        raise AffiliatePayoutRequestError("No payout email on file.")


def _email_partner_approved(row: AffiliatePayoutRequest) -> None:
    settings = get_settings()
    to_email = row.requested_by_email
    amount = f"${row.amount_cents / 100:.2f}"
    body = f"""
      <p style="margin:0 0 16px;">Hi,</p>
      <p style="margin:0 0 16px;">
        Your payout request for partner code <strong>{html.escape(row.affiliate_code)}</strong>
        ({amount}) was <strong>approved</strong> after our review window.
      </p>
      <p style="margin:0 0 16px;">
        Funds will be sent to <strong>{html.escape(row.payout_email or row.requested_by_email)}</strong>
        shortly (typically within a few business days). Reply to {html.escape(settings.support_email)}
        if your payout email changed.
      </p>
    """
    html_body = wrap_branded_email(
        eyebrow="Partner payout",
        title="Payout approved",
        body_html=body,
        app_url=settings.app_url,
        tip="Thank you for partnering with NoorLink.",
    )
    try:
        send_email(
            to_email=to_email,
            subject=f"[NoorLink] Payout approved — {row.affiliate_code} ({amount})",
            html_body=html_body,
            reply_to=settings.support_email,
        )
    except EmailDeliveryError:
        logger.exception("Partner payout approval email failed for %s", row.affiliate_code)


def auto_approve_request(row: AffiliatePayoutRequest) -> Dict[str, Any]:
    factory = get_session_factory()
    if factory is None:
        raise AffiliatePayoutRequestError("DATABASE_URL is required.")

    from app.db.models import AffiliateCommission

    now = datetime.now(timezone.utc)
    with factory() as session:
        fresh = session.get(AffiliatePayoutRequest, row.id)
        if fresh is None or fresh.status != "pending":
            raise AffiliatePayoutRequestError("Request no longer pending.")
        affiliate = session.get(Affiliate, fresh.affiliate_id)
        if affiliate is None:
            raise AffiliatePayoutRequestError("Affiliate missing.")
        evaluate_strict_auto_approve(fresh, affiliate)

        approved_balance = sum(
            int(c.commission_cents)
            for c in session.scalars(
                select(AffiliateCommission)
                .where(AffiliateCommission.affiliate_id == affiliate.id)
                .where(AffiliateCommission.status == "approved")
            ).all()
        )
        if approved_balance < fresh.amount_cents:
            raise AffiliatePayoutRequestError(
                f"Approved balance ${approved_balance / 100:.2f} is below requested "
                f"${fresh.amount_cents / 100:.2f}."
            )

        payout_email = fresh.payout_email or affiliate.payout_email or affiliate.contact_email
        code = fresh.affiliate_code
        amount_cents = fresh.amount_cents
        request_id = str(fresh.id)
        partner_email = fresh.requested_by_email

        fresh.status = "approved_auto"
        fresh.auto_approved_at = now
        fresh.updated_at = now
        fresh.notes = ((fresh.notes or "").strip() + f"\nAuto-approved after {_wait_hours()}h unattended.").strip()
        session.commit()

    approved_row = AffiliatePayoutRequest(
        id=UUID(request_id),
        affiliate_id=row.affiliate_id,
        affiliate_code=code,
        requested_by_email=partner_email,
        payout_email=payout_email,
        amount_cents=amount_cents,
        status="approved_auto",
    )
    _email_partner_approved(approved_row)

    amount = f"${amount_cents / 100:.2f}"
    log_ops_event(
        event_type="affiliate_payout_auto_approved",
        source="cron",
        severity="warning",
        message=f"Auto-approved payout {code} {amount} after {_wait_hours()}h",
        details={
            "request_id": request_id,
            "code": code,
            "amount_cents": amount_cents,
            "payout_email": payout_email,
        },
    )
    notify_staff_governance(
        title=f"ACTION: Send affiliate payout — {code}",
        summary=(
            f"Request unattended {_wait_hours()}h+. Auto-approved {amount}. "
            f"Send funds to {payout_email}, then record payout in Admin → Affiliate payout."
        ),
        details={
            "code": code,
            "amount": amount,
            "payout_email": payout_email or "—",
            "request_id": request_id,
        },
    )
    return {
        "id": request_id,
        "code": code,
        "amount_cents": amount_cents,
        "status": "approved_auto",
    }


def process_unanswered_affiliate_payouts() -> Dict[str, Any]:
    hours = _wait_hours()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    factory = get_session_factory()
    if factory is None:
        return {"success": False, "error": "DATABASE_URL not configured"}

    with factory() as session:
        candidates = list(
            session.scalars(
                select(AffiliatePayoutRequest)
                .where(AffiliatePayoutRequest.status == "pending")
                .where(AffiliatePayoutRequest.attended_at.is_(None))
                .where(AffiliatePayoutRequest.created_at <= cutoff)
                .order_by(AffiliatePayoutRequest.created_at.asc())
                .limit(50)
            ).all()
        )
        for row in candidates:
            session.expunge(row)

    processed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for row in candidates:
        try:
            processed.append(auto_approve_request(row))
        except AffiliatePayoutRequestError as exc:
            skipped.append({"id": str(row.id), "code": row.affiliate_code, "reason": str(exc)})
        except Exception as exc:
            skipped.append({"id": str(row.id), "code": row.affiliate_code, "reason": str(exc)[:200]})
            logger.exception("Affiliate auto-approve failed for %s", row.affiliate_code)

    return {
        "success": True,
        "wait_hours": hours,
        "max_cents": _max_cents(),
        "candidates": len(candidates),
        "approved": len(processed),
        "skipped": len(skipped),
        "processed": processed,
        "skip_details": skipped[:20],
    }
