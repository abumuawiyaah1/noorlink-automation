"""Partner self-service dashboard (code + email verification)."""

from __future__ import annotations

from typing import Any, Dict, List

from app.api import supabase_repository as db
from app.services.affiliates import DEFAULTS, _affiliate_row, normalize_ref_code


class AffiliatePortalError(Exception):
    """Partner dashboard access denied."""


def _emails_for_row(row: Dict[str, Any]) -> List[str]:
    keys = ("contact_email", "payout_email", "referrer_email")
    return [str(row.get(k) or "").strip().lower() for k in keys if row.get(k)]


def get_affiliate_dashboard(*, code: str, email: str) -> Dict[str, Any]:
    normalized_code = normalize_ref_code(code)
    normalized_email = email.strip().lower()
    if not normalized_code or "@" not in normalized_email:
        raise AffiliatePortalError("Valid partner code and email are required.")

    row = _affiliate_row(normalized_code)
    if not row or str(row.get("status") or "active") != "active":
        raise AffiliatePortalError("Partner link not found or inactive.")

    allowed = _emails_for_row(row)
    if normalized_email not in allowed:
        raise AffiliatePortalError("Email does not match this partner account.")

    affiliate_id = str(row["id"])
    affiliate_type = str(row["type"])
    client = db.get_supabase_client()

    commissions = (
        client.table("affiliate_commissions")
        .select("commission_cents, status, order_number, fulfilled_at")
        .eq("affiliate_id", affiliate_id)
        .order("fulfilled_at", desc=True)
        .limit(50)
        .execute()
    ).data or []

    approved_cents = sum(int(c["commission_cents"]) for c in commissions if c.get("status") == "approved")
    paid_cents = sum(int(c["commission_cents"]) for c in commissions if c.get("status") == "paid")
    minimum = int(
        row.get("payout_minimum_cents")
        or DEFAULTS.get(affiliate_type, {}).get("payout_minimum_cents", 2500)
    )

    from app.core.config import get_settings

    app_url = get_settings().app_url.rstrip("/")
    return {
        "code": row["code"],
        "type": affiliate_type,
        "display_name": row.get("display_name") or row.get("organization_name"),
        "referral_url": f"{app_url}/ref/{row['code']}",
        "customer_discount_percent": row.get("customer_discount_percent")
        or DEFAULTS.get(affiliate_type, {}).get("customer_discount_percent"),
        "commission_percent": row.get("commission_percent")
        or DEFAULTS.get(affiliate_type, {}).get("commission_percent"),
        "pays_cash": affiliate_type in {"influencer", "mosque", "connector"},
        "approved_balance_cents": approved_cents,
        "paid_total_cents": paid_cents,
        "payout_minimum_cents": minimum,
        "ready_for_payout": approved_cents >= minimum and affiliate_type != "customer",
        "recent_commissions": commissions[:15],
    }


def request_affiliate_payout(*, code: str, email: str) -> Dict[str, Any]:
    """Partner-initiated payout request — persists queue + emails ops; does not transfer funds."""
    data = get_affiliate_dashboard(code=code, email=email)
    if not data.get("pays_cash"):
        raise AffiliatePortalError("This partner type does not receive cash payouts.")
    if not data.get("ready_for_payout"):
        raise AffiliatePortalError(
            f"Balance ${data['approved_balance_cents'] / 100:.2f} is below the "
            f"${data['payout_minimum_cents'] / 100:.2f} minimum."
        )

    row = _affiliate_row(data["code"]) or {}
    pay_emails = _emails_for_row(row)
    payout_email = pay_emails[0] if pay_emails else email.strip().lower()
    amount_cents = int(data["approved_balance_cents"])

    from app.services.affiliate_payout_requests import (
        AffiliatePayoutRequestError,
        create_payout_request,
    )

    try:
        created = create_payout_request(
            affiliate_id=str(row["id"]),
            affiliate_code=data["code"],
            requested_by_email=email.strip().lower(),
            payout_email=payout_email,
            amount_cents=amount_cents,
        )
    except AffiliatePayoutRequestError as exc:
        raise AffiliatePortalError(str(exc)) from exc

    from app.services.ops_alerts import notify_affiliate_payout_request

    notify_affiliate_payout_request(
        code=data["code"],
        display_name=data.get("display_name") or data["code"],
        email=email.strip().lower(),
        balance_cents=amount_cents,
        payout_email=payout_email,
    )

    from app.services.ops_event_log import log_ops_event

    log_ops_event(
        event_type="affiliate_payout_requested",
        source="affiliate_portal",
        message=f"Payout requested by {data['code']}",
        details={
            "code": data["code"],
            "email": email.strip().lower(),
            "balance_cents": amount_cents,
            "request_id": created.get("id"),
        },
    )

    wait_h = created.get("wait_hours", 72)
    return {
        "code": data["code"],
        "approved_balance_cents": amount_cents,
        "request_id": created.get("id"),
        "message": (
            "Payout request sent to NoorLink ops. We typically process within 5 business days. "
            f"If unattended for {wait_h} hours, it auto-approves for processing "
            "(funds still sent manually)."
        ),
    }
