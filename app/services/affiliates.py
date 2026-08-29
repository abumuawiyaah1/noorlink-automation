"""Affiliate attribution, checkout discounts, commissions, and refer-a-friend rewards."""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.api import supabase_repository as db
from app.services.promo_codes import PromoCodeError, PromoDiscount, normalize_code, validate_promo_row

logger = logging.getLogger(__name__)

AffiliateType = str  # influencer | mosque | connector | customer

DEFAULTS: Dict[str, Dict[str, int]] = {
    "influencer": {
        "customer_discount_percent": 10,
        "commission_percent": 10,
        "payout_minimum_cents": 2500,
    },
    "mosque": {
        "customer_discount_percent": 5,
        "commission_percent": 12,
        "commission_percent_hajj": 15,
        "payout_minimum_cents": 5000,
    },
    "connector": {
        "customer_discount_percent": 10,
        "commission_percent": 8,
        "payout_minimum_cents": 2500,
    },
    "customer": {
        "customer_discount_percent": 10,
        "referrer_reward_percent": 10,
        "payout_minimum_cents": 0,
    },
}

HAJJ_COUNTRY_SLUGS = frozenset(
    {"saudi-arabia", "saudi", "umrah", "hajj", "sa"}
)
THIN_MARGIN_REGIONS = frozenset({"caribbean", "regional-caribbean"})
CUSTOMER_REFERRAL_MAX_PER_YEAR = 5
REFERRAL_REWARD_VALID_DAYS = 365


class AffiliateError(Exception):
    """Affiliate validation or configuration error."""


@dataclass(frozen=True)
class AffiliateAttribution:
    affiliate_id: str
    code: str
    affiliate_type: AffiliateType
    display_name: Optional[str]
    customer_discount_percent: int
    commission_percent: int
    discount_cents: int
    subtotal_cents: int
    final_cents: int
    is_hajj_corridor: bool
    self_referral_blocked: bool = False


@dataclass(frozen=True)
class CheckoutDiscountResult:
    subtotal_cents: int
    discount_cents: int
    final_cents: int
    promo: Optional[PromoDiscount]
    affiliate: Optional[AffiliateAttribution]
    force_custom_price: bool


def normalize_ref_code(code: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9-]", "", (code or "").strip().upper())
    return cleaned[:32]


def _is_hajj_corridor(country: str) -> bool:
    slug = (country or "").strip().lower().replace("_", "-")
    return slug in HAJJ_COUNTRY_SLUGS or "saudi" in slug


def _is_thin_margin(*, country: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    meta = metadata or {}
    regional = str(meta.get("regional_product_id") or meta.get("region_slug") or "").lower()
    if any(token in regional for token in THIN_MARGIN_REGIONS):
        return True
    slug = (country or "").strip().lower()
    return slug == "caribbean"


def _affiliate_row(code: str) -> Optional[Dict[str, Any]]:
    normalized = normalize_ref_code(code)
    if not normalized:
        return None
    try:
        client = db.get_supabase_client()
        result = (
            client.table("affiliates")
            .select("*")
            .eq("code", normalized)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        logger.exception("affiliate lookup failed for %s", normalized)
        return None


def _emails_match(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def _customer_discount_percent(row: Dict[str, Any], *, is_hajj: bool, thin: bool) -> int:
    if row.get("customer_discount_percent") is not None:
        return int(row["customer_discount_percent"])
    affiliate_type = str(row["type"])
    defaults = DEFAULTS.get(affiliate_type, DEFAULTS["influencer"])
    if thin and affiliate_type == "influencer":
        return 8
    if thin and affiliate_type == "connector":
        return 8
    if thin and affiliate_type == "mosque":
        return 0
    return int(defaults["customer_discount_percent"])


def _commission_percent(row: Dict[str, Any], *, is_hajj: bool, thin: bool) -> int:
    if row.get("commission_percent") is not None:
        return int(row["commission_percent"])
    affiliate_type = str(row["type"])
    defaults = DEFAULTS.get(affiliate_type, DEFAULTS["influencer"])
    if affiliate_type == "customer":
        return 0
    if affiliate_type == "mosque" and is_hajj:
        return int(defaults.get("commission_percent_hajj", defaults["commission_percent"]))
    if thin:
        if affiliate_type == "influencer":
            return 6
        if affiliate_type == "connector":
            return 6
        if affiliate_type == "mosque":
            return 12
    return int(defaults["commission_percent"])


def resolve_affiliate_for_checkout(
    *,
    ref_code: Optional[str],
    buyer_email: str,
    subtotal_cents: int,
    country: str,
) -> Optional[AffiliateAttribution]:
    if not ref_code or not str(ref_code).strip():
        return None
    row = _affiliate_row(ref_code)
    if not row:
        return None

    affiliate_type = str(row["type"])
    is_hajj = _is_hajj_corridor(country)
    thin = _is_thin_margin(country=country, metadata=row.get("metadata"))

    payout_email = (row.get("payout_email") or row.get("contact_email") or "").strip()
    referrer_email = (row.get("referrer_email") or "").strip()
    self_referral = _emails_match(buyer_email, payout_email) or (
        referrer_email and _emails_match(buyer_email, referrer_email)
    )
    if self_referral:
        return AffiliateAttribution(
            affiliate_id=str(row["id"]),
            code=str(row["code"]),
            affiliate_type=affiliate_type,
            display_name=row.get("display_name") or row.get("organization_name"),
            customer_discount_percent=0,
            commission_percent=0,
            discount_cents=0,
            subtotal_cents=subtotal_cents,
            final_cents=subtotal_cents,
            is_hajj_corridor=is_hajj,
            self_referral_blocked=True,
        )

    discount_percent = _customer_discount_percent(row, is_hajj=is_hajj, thin=thin)
    discount_cents = 0
    if discount_percent > 0 and subtotal_cents > 1:
        discount_cents = int(round(subtotal_cents * discount_percent / 100))
        discount_cents = max(0, min(discount_cents, subtotal_cents - 1))

    commission_percent = _commission_percent(row, is_hajj=is_hajj, thin=thin)
    final_cents = subtotal_cents - discount_cents

    return AffiliateAttribution(
        affiliate_id=str(row["id"]),
        code=str(row["code"]),
        affiliate_type=affiliate_type,
        display_name=row.get("display_name") or row.get("organization_name"),
        customer_discount_percent=discount_percent,
        commission_percent=commission_percent,
        discount_cents=discount_cents,
        subtotal_cents=subtotal_cents,
        final_cents=final_cents,
        is_hajj_corridor=is_hajj,
        self_referral_blocked=False,
    )


def prepare_checkout_discounts(
    *,
    catalog_price: float,
    country: str,
    buyer_email: str,
    package_id: str,
    promo_code: Optional[str],
    affiliate_ref: Optional[str],
) -> CheckoutDiscountResult:
    subtotal_cents = int(round(catalog_price * 100))

    affiliate = resolve_affiliate_for_checkout(
        ref_code=affiliate_ref,
        buyer_email=buyer_email,
        subtotal_cents=subtotal_cents,
        country=country,
    )

    promo: Optional[PromoDiscount] = None
    if promo_code and promo_code.strip():
        try:
            db.expire_promo_codes()
        except db.SupabaseRepositoryError:
            pass
        row = db.get_promo_code(normalize_code(promo_code))
        try:
            promo = validate_promo_row(row, subtotal_cents=subtotal_cents)
        except PromoCodeError as exc:
            raise AffiliateError(str(exc)) from exc

    affiliate_discount = (
        0
        if not affiliate or affiliate.self_referral_blocked
        else affiliate.discount_cents
    )
    promo_discount = promo.discount_cents if promo else 0

    if affiliate_discount >= promo_discount:
        discount_cents = affiliate_discount
        chosen_promo = None
        chosen_affiliate = affiliate if affiliate and not affiliate.self_referral_blocked else None
    else:
        discount_cents = promo_discount
        chosen_promo = promo
        # Still attribute affiliate when valid (best-discount rule).
        chosen_affiliate = affiliate if affiliate and not affiliate.self_referral_blocked else None

    final_cents = max(1, subtotal_cents - discount_cents)
    return CheckoutDiscountResult(
        subtotal_cents=subtotal_cents,
        discount_cents=discount_cents,
        final_cents=final_cents,
        promo=chosen_promo,
        affiliate=chosen_affiliate,
        force_custom_price=discount_cents > 0,
    )


def affiliate_metadata_patch(
    affiliate: Optional[AffiliateAttribution],
    *,
    attribution_source: Optional[str] = None,
) -> Dict[str, Any]:
    if not affiliate or affiliate.self_referral_blocked:
        return {}
    patch: Dict[str, Any] = {
        "affiliate": {
            "id": affiliate.affiliate_id,
            "code": affiliate.code,
            "type": affiliate.affiliate_type,
            "customer_discount_percent": affiliate.customer_discount_percent,
            "commission_percent": affiliate.commission_percent,
            "discount_cents": affiliate.discount_cents,
            "subtotal_cents": affiliate.subtotal_cents,
            "is_hajj_corridor": affiliate.is_hajj_corridor,
        }
    }
    if attribution_source:
        patch["affiliate"]["source"] = attribution_source
    return patch


def _generate_customer_code() -> str:
    return f"NL-{secrets.token_hex(3).upper()}"


def ensure_customer_affiliate(*, email: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    normalized_email = email.strip().lower()
    client = db.get_supabase_client()
    existing = (
        client.table("affiliates")
        .select("*")
        .eq("referrer_email", normalized_email)
        .eq("type", "customer")
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    for _ in range(8):
        code = _generate_customer_code()
        payload = {
            "code": code,
            "type": "customer",
            "display_name": display_name or normalized_email.split("@")[0],
            "referrer_email": normalized_email,
            "status": "active",
            "landing_path": "/destinations",
        }
        try:
            result = client.table("affiliates").insert(payload).execute()
            if result.data:
                return result.data[0]
        except Exception as exc:
            if "duplicate" in str(exc).lower() or "23505" in str(exc):
                continue
            raise
    raise AffiliateError("Could not allocate a customer referral code.")


def _count_customer_rewards_this_year(affiliate_id: str) -> int:
    client = db.get_supabase_client()
    since = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    result = (
        client.table("affiliate_referral_rewards")
        .select("id", count="exact")
        .eq("affiliate_id", affiliate_id)
        .gte("created_at", since)
        .execute()
    )
    return int(result.count or 0)


def _create_reward_promo(*, code: str, percent: int) -> None:
    client = db.get_supabase_client()
    now = datetime.now(timezone.utc)
    ends = now + timedelta(days=REFERRAL_REWARD_VALID_DAYS)
    payload = {
        "code": code,
        "label": "Refer-a-friend reward",
        "percent_off": percent,
        "starts_at": now.isoformat(),
        "ends_at": ends.isoformat(),
        "is_active": True,
        "max_redemptions": 1,
        "min_order_cents": 0,
    }
    client.table("promo_codes").insert(payload).execute()


def _issue_customer_referrer_reward(
    *,
    affiliate_row: Dict[str, Any],
    order_row: Dict[str, Any],
) -> Optional[str]:
    affiliate_id = str(affiliate_row["id"])
    if _count_customer_rewards_this_year(affiliate_id) >= CUSTOMER_REFERRAL_MAX_PER_YEAR:
        logger.info("Customer affiliate %s hit yearly referral reward cap", affiliate_row["code"])
        return None

    recipient = str(affiliate_row.get("referrer_email") or "").strip().lower()
    if not recipient:
        return None

    reward_code = f"REWARD-{normalize_ref_code(affiliate_row['code'])}-{secrets.token_hex(2).upper()}"
    percent = int(DEFAULTS["customer"]["referrer_reward_percent"])
    _create_reward_promo(code=reward_code, percent=percent)

    client = db.get_supabase_client()
    client.table("affiliate_referral_rewards").insert(
        {
            "affiliate_id": affiliate_id,
            "recipient_email": recipient,
            "triggered_by_order_id": str(order_row["id"]),
            "reward_promo_code": reward_code,
            "status": "issued",
        }
    ).execute()
    return reward_code


def _record_cash_commission(
    *,
    affiliate_row: Dict[str, Any],
    order_row: Dict[str, Any],
    commission_percent: int,
) -> None:
    client = db.get_supabase_client()
    order_id = str(order_row["id"])
    existing = (
        client.table("affiliate_commissions")
        .select("id")
        .eq("order_id", order_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return

    amount_cents = int(order_row.get("amount_cents") or 0)
    if amount_cents <= 0:
        return

    commission_cents = int(round(amount_cents * commission_percent / 100))
    if commission_cents <= 0:
        return

    client.table("affiliate_commissions").insert(
        {
            "affiliate_id": str(affiliate_row["id"]),
            "order_id": order_id,
            "order_number": str(order_row["order_number"]),
            "order_amount_cents": amount_cents,
            "commission_percent": commission_percent,
            "commission_cents": commission_cents,
            "status": "approved",
        }
    ).execute()


def process_affiliate_on_fulfillment(order_row: Dict[str, Any]) -> None:
    """Create commissions or refer-a-friend rewards after an order is delivered."""
    metadata = order_row.get("metadata") or {}
    if not isinstance(metadata, dict):
        return
    aff = metadata.get("affiliate")
    if not isinstance(aff, dict) or not aff.get("code"):
        return

    row = _affiliate_row(str(aff["code"]))
    if not row:
        return

    affiliate_type = str(row["type"])
    buyer_email = str(order_row.get("email") or "")

    payout_email = (row.get("payout_email") or row.get("contact_email") or "").strip()
    referrer_email = (row.get("referrer_email") or "").strip()
    if _emails_match(buyer_email, payout_email) or (
        referrer_email and _emails_match(buyer_email, referrer_email)
    ):
        return

    if affiliate_type == "customer":
        reward_code = _issue_customer_referrer_reward(affiliate_row=row, order_row=order_row)
        if reward_code:
            try:
                from app.services.email_service import send_referral_reward_email

                send_referral_reward_email(
                    to_email=referrer_email,
                    reward_code=reward_code,
                    friend_order_number=str(order_row["order_number"]),
                )
            except Exception:
                logger.exception(
                    "Referral reward email failed for order %s", order_row.get("order_number")
                )
        return

    commission_percent = int(
        aff.get("commission_percent")
        or _commission_percent(
            row,
            is_hajj=bool(aff.get("is_hajj_corridor")),
            thin=_is_thin_margin(country=str(order_row.get("country") or ""), metadata=metadata),
        )
    )
    _record_cash_commission(
        affiliate_row=row,
        order_row=order_row,
        commission_percent=commission_percent,
    )


def get_affiliate_summary(code: str) -> Optional[Dict[str, Any]]:
    row = _affiliate_row(code)
    if not row:
        return None
    affiliate_type = str(row["type"])
    defaults = DEFAULTS.get(affiliate_type, {})
    return {
        "code": row["code"],
        "type": affiliate_type,
        "displayName": row.get("display_name") or row.get("organization_name"),
        "organizationName": row.get("organization_name"),
        "customerDiscountPercent": row.get("customer_discount_percent")
        or defaults.get("customer_discount_percent"),
        "landingPath": row.get("landing_path") or "/destinations",
        "paysCash": affiliate_type in {"influencer", "mosque", "connector"},
    }


def get_customer_referral_link(*, email: str) -> Dict[str, Any]:
    row = ensure_customer_affiliate(email=email)
    from app.core.config import get_settings

    app_url = get_settings().app_url.rstrip("/")
    code = str(row["code"])
    return {
        "code": code,
        "url": f"{app_url}/ref/{code}",
        "customerDiscountPercent": DEFAULTS["customer"]["customer_discount_percent"],
        "referrerRewardPercent": DEFAULTS["customer"]["referrer_reward_percent"],
    }
