"""Public and internal affiliate API routes."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api import supabase_repository as db
from app.api.internal_auth import require_internal_in_production
from app.api.schemas import (
    AffiliateCreateRequest,
    AffiliatePayoutRequest,
    AffiliateReferralLinkResponse,
    AffiliateResolveResponse,
)
from app.services.affiliates import (
    DEFAULTS,
    get_affiliate_summary,
    get_customer_referral_link,
    normalize_ref_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["affiliates"])


@router.get("/api/affiliate/resolve", response_model=AffiliateResolveResponse)
async def affiliate_resolve(ref: str = Query(..., min_length=2, max_length=32)):
    summary = get_affiliate_summary(ref)
    if not summary:
        return AffiliateResolveResponse(valid=False, message="Referral link not found.")
    return AffiliateResolveResponse(
        valid=True,
        code=summary["code"],
        type=summary["type"],
        display_name=summary.get("displayName"),
        organization_name=summary.get("organizationName"),
        customer_discount_percent=summary.get("customerDiscountPercent"),
        landing_path=summary.get("landingPath"),
        pays_cash=summary.get("paysCash"),
    )


@router.get("/api/affiliate/referral-link", response_model=AffiliateReferralLinkResponse)
async def affiliate_referral_link(
    email: str = Query(..., min_length=3),
    order_number: Optional[str] = Query(None, alias="orderNumber", min_length=4),
):
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise HTTPException(status_code=400, detail="Valid email is required.")

    if order_number:
        try:
            order = db.lookup_order(order_number, normalized)
        except db.SupabaseRepositoryError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not order:
            return AffiliateReferralLinkResponse(
                success=False,
                message="Order not found for this email.",
            )

    try:
        payload = get_customer_referral_link(email=normalized)
    except Exception as exc:
        logger.exception("referral-link failed for %s", normalized)
        raise HTTPException(status_code=503, detail="Could not create referral link.") from exc

    return AffiliateReferralLinkResponse(
        success=True,
        code=payload["code"],
        url=payload["url"],
        customer_discount_percent=payload["customerDiscountPercent"],
        referrer_reward_percent=payload["referrerRewardPercent"],
    )


@router.post("/api/internal/affiliates")
async def internal_create_affiliate(
    body: AffiliateCreateRequest,
    _: None = Depends(require_internal_in_production),
):
    code = normalize_ref_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="Invalid affiliate code.")

    defaults = DEFAULTS.get(body.type, {})
    payload: Dict[str, Any] = {
        "code": code,
        "type": body.type,
        "display_name": body.display_name,
        "organization_name": body.organization_name,
        "contact_email": str(body.contact_email).lower() if body.contact_email else None,
        "payout_email": str(body.payout_email).lower() if body.payout_email else None,
        "referrer_email": str(body.referrer_email).lower() if body.referrer_email else None,
        "customer_discount_percent": body.customer_discount_percent
        or defaults.get("customer_discount_percent"),
        "commission_percent": body.commission_percent or defaults.get("commission_percent"),
        "payout_minimum_cents": body.payout_minimum_cents
        or defaults.get("payout_minimum_cents"),
        "landing_path": body.landing_path or defaults.get("landing_path", "/destinations"),
        "status": body.status,
    }
    if body.type == "mosque" and body.landing_path is None:
        payload["landing_path"] = "/hajj-umrah"

    client = db.get_supabase_client()
    try:
        result = client.table("affiliates").insert(payload).execute()
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise HTTPException(status_code=409, detail="Affiliate code already exists.") from exc
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not result.data:
        raise HTTPException(status_code=503, detail="Affiliate create failed.")
    return {"success": True, "affiliate": result.data[0]}


@router.get("/api/internal/affiliates")
async def internal_list_affiliates(
    _: None = Depends(require_internal_in_production),
):
    client = db.get_supabase_client()
    result = client.table("affiliates").select("*").order("created_at", desc=True).execute()
    return {"success": True, "affiliates": result.data or []}


@router.get("/api/internal/affiliate/payouts")
async def internal_affiliate_payouts(
    _: None = Depends(require_internal_in_production),
):
    client = db.get_supabase_client()
    affiliates = client.table("affiliates").select("*").eq("status", "active").execute()
    rows: List[Dict[str, Any]] = []

    for affiliate in affiliates.data or []:
        affiliate_id = str(affiliate["id"])
        affiliate_type = str(affiliate["type"])
        if affiliate_type == "customer":
            continue

        commissions = (
            client.table("affiliate_commissions")
            .select("commission_cents")
            .eq("affiliate_id", affiliate_id)
            .eq("status", "approved")
            .execute()
        )
        balance_cents = sum(int(c["commission_cents"]) for c in (commissions.data or []))
        minimum = int(
            affiliate.get("payout_minimum_cents")
            or DEFAULTS.get(affiliate_type, {}).get("payout_minimum_cents", 2500)
        )
        rows.append(
            {
                "affiliateId": affiliate_id,
                "code": affiliate["code"],
                "type": affiliate_type,
                "displayName": affiliate.get("display_name") or affiliate.get("organization_name"),
                "payoutEmail": affiliate.get("payout_email") or affiliate.get("contact_email"),
                "balanceCents": balance_cents,
                "minimumCents": minimum,
                "readyForPayout": balance_cents >= minimum,
            }
        )

    return {"success": True, "payouts": rows}


@router.post("/api/internal/affiliate/payouts/mark-paid")
async def internal_mark_affiliate_paid(
    body: AffiliatePayoutRequest,
    _: None = Depends(require_internal_in_production),
):
    client = db.get_supabase_client()
    affiliate = (
        client.table("affiliates")
        .select("*")
        .eq("id", body.affiliate_id)
        .limit(1)
        .execute()
    )
    if not affiliate.data:
        raise HTTPException(status_code=404, detail="Affiliate not found.")

    row = affiliate.data[0]
    affiliate_type = str(row["type"])
    if affiliate_type == "customer":
        raise HTTPException(status_code=400, detail="Customer affiliates are not paid in cash.")

    commissions = (
        client.table("affiliate_commissions")
        .select("*")
        .eq("affiliate_id", body.affiliate_id)
        .eq("status", "approved")
        .execute()
    )
    approved = commissions.data or []
    amount_cents = sum(int(c["commission_cents"]) for c in approved)
    minimum = int(
        row.get("payout_minimum_cents")
        or DEFAULTS.get(affiliate_type, {}).get("payout_minimum_cents", 2500)
    )
    if amount_cents < minimum:
        raise HTTPException(
            status_code=400,
            detail=f"Balance ${amount_cents / 100:.2f} is below minimum ${minimum / 100:.2f}.",
        )

    payout = (
        client.table("affiliate_payouts")
        .insert(
            {
                "affiliate_id": body.affiliate_id,
                "amount_cents": amount_cents,
                "method": body.method or "manual",
                "reference": body.reference,
                "notes": body.notes,
            }
        )
        .execute()
    )
    if not payout.data:
        raise HTTPException(status_code=503, detail="Payout record failed.")

    payout_id = payout.data[0]["id"]
    for commission in approved:
        client.table("affiliate_commissions").update({"status": "paid", "payout_id": payout_id}).eq(
            "id", commission["id"]
        ).execute()

    return {
        "success": True,
        "payoutId": payout_id,
        "amountCents": amount_cents,
        "commissionCount": len(approved),
    }
