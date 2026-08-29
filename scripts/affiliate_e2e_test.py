#!/usr/bin/env python3
"""
Zero-cost affiliate E2E test: create partners, pending checkout orders, mock fulfill, verify DB.

Usage (production Supabase + mock eSIM — no Stripe, no Citrus spend):
  cd noorlink-automation
  ESIM_PROVIDER=mock python scripts/affiliate_e2e_test.py

Requires service-role Supabase + CRON_SECRET in environment (.env or Railway).
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force mock provisioning for this script only.
os.environ["ESIM_PROVIDER"] = "mock"

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.affiliates import prepare_checkout_discounts
from app.services.fulfillment import process_paid_order

RUN_ID = uuid.uuid4().hex[:6].upper()
TEST_CODES = {
    "influencer": f"E2E-INFL-{RUN_ID}",
    "mosque": f"E2E-MASJ-{RUN_ID}",
    "connector": f"E2E-CONN-{RUN_ID}",
}
BUYER_INFL = f"affiliate.e2e.infl.{RUN_ID.lower()}@gmail.com"
BUYER_FRIEND = f"affiliate.e2e.friend.{RUN_ID.lower()}@gmail.com"
PAYOUT_EMAIL = f"payout.e2e.{RUN_ID.lower()}@gmail.com"


class Check:
    def __init__(self) -> None:
        self.passed: List[str] = []
        self.failed: List[str] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.passed.append(name)
        msg = f"PASS  {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)

    def fail(self, name: str, detail: str = "") -> None:
        self.failed.append(name)
        msg = f"FAIL  {name}"
        if detail:
            msg += f" — {detail}"
        print(msg, file=sys.stderr)

    def summary(self) -> int:
        print("\n" + "=" * 60)
        print(f"Passed: {len(self.passed)}  Failed: {len(self.failed)}")
        if self.failed:
            for name in self.failed:
                print(f"  ✗ {name}")
            return 1
        print("All checks passed.")
        return 0


def _client():
    return db.get_supabase_client()


def ensure_test_affiliates(check: Check) -> None:
    client = _client()
    specs = [
        (
            TEST_CODES["influencer"],
            {
                "type": "influencer",
                "display_name": f"E2E Influencer {RUN_ID}",
                "payout_email": PAYOUT_EMAIL,
                "landing_path": "/destinations",
            },
        ),
        (
            TEST_CODES["mosque"],
            {
                "type": "mosque",
                "organization_name": f"E2E Masjid {RUN_ID}",
                "payout_email": f"masjid-{PAYOUT_EMAIL}",
                "landing_path": "/hajj-umrah",
            },
        ),
        (
            TEST_CODES["connector"],
            {
                "type": "connector",
                "display_name": f"E2E Connector {RUN_ID}",
                "payout_email": f"conn-{PAYOUT_EMAIL}",
                "landing_path": "/destinations",
            },
        ),
    ]
    for code, extra in specs:
        existing = client.table("affiliates").select("id").eq("code", code).limit(1).execute()
        if existing.data:
            check.ok(f"affiliate exists {code}")
            continue
        payload = {
            "code": code,
            "status": "active",
            "customer_discount_percent": extra["type"] == "mosque" and 5 or 10,
            "commission_percent": {"influencer": 10, "mosque": 12, "connector": 8}[extra["type"]],
            "payout_minimum_cents": extra["type"] == "mosque" and 5000 or 2500,
            **extra,
        }
        client.table("affiliates").insert(payload).execute()
        check.ok(f"affiliate created {code}")


def _pick_package() -> Tuple[str, str, float]:
    """Return (package_id, country, catalog_price_usd)."""
    client = _client()
    result = (
        client.table("esim_packages")
        .select("id, slug, country, price_cents, is_active, is_managed")
        .eq("is_active", True)
        .order("price_cents")
        .limit(50)
        .execute()
    )
    rows = result.data or []
    for row in rows:
        country = str(row.get("country") or "").lower()
        slug = str(row.get("slug") or "").lower()
        if "saudi" in country or "saudi" in slug or "caribbean" in country:
            continue
        price_cents = int(row.get("price_cents") or 0)
        if price_cents >= 500:
            return str(row["id"]), str(row.get("country") or "turkey"), price_cents / 100.0
    if not rows:
        raise RuntimeError("No active esim_packages found.")
    row = rows[0]
    return str(row["id"]), str(row.get("country") or "turkey"), int(row["price_cents"]) / 100.0


def create_pending_order(
    *,
    affiliate_ref: str,
    buyer_email: str,
    package_id: str,
    country: str,
    catalog_price: float,
) -> Dict[str, Any]:
    pricing = prepare_checkout_discounts(
        catalog_price=catalog_price,
        country=country,
        buyer_email=buyer_email,
        package_id=package_id,
        promo_code=None,
        affiliate_ref=affiliate_ref,
    )
    from app.services.affiliates import affiliate_metadata_patch

    affiliate_meta = (
        affiliate_metadata_patch(pricing.affiliate).get("affiliate")
        if pricing.affiliate
        else None
    )
    created = db.create_order(
        email=buyer_email,
        country=country,
        price=catalog_price,
        flag=None,
        travel_date=None,
        package_id=package_id,
        phone=None,
        promo_code=None,
        promo_discount_cents=None,
        promo_subtotal_cents=None,
        total_discount_cents=pricing.discount_cents,
        affiliate_metadata=affiliate_meta,
        wants_topup=False,
    )
    row = db.get_order_row_by_order_number(created.order.order_number)
    if not row:
        raise RuntimeError(f"Order row missing after create: {created.order.order_number}")
    return {
        "order_number": created.order.order_number,
        "pricing": pricing,
        "row": row,
    }


def fulfill_order(order_number: str) -> Dict[str, Any]:
    result = process_paid_order(order_number=order_number)
    if not result:
        raise RuntimeError(f"Fulfillment returned None for {order_number}")
    if result.get("status") != "delivered":
        raise RuntimeError(f"Expected delivered, got {result.get('status')}")
    return result


def verify_commission(
    check: Check,
    *,
    order_number: str,
    expected_code: str,
    expected_percent: int,
) -> None:
    client = _client()
    order = client.table("orders").select("*").eq("order_number", order_number).limit(1).execute()
    if not order.data:
        check.fail("order lookup", order_number)
        return
    order_row = order.data[0]
    amount_cents = int(order_row.get("amount_cents") or 0)
    expected_commission = int(round(amount_cents * expected_percent / 100))

    comm = (
        client.table("affiliate_commissions")
        .select("*")
        .eq("order_number", order_number)
        .limit(1)
        .execute()
    )
    if not comm.data:
        check.fail(f"commission {order_number}", "no row")
        return
    row = comm.data[0]
    aff = (
        client.table("affiliates")
        .select("code")
        .eq("id", row["affiliate_id"])
        .limit(1)
        .execute()
    )
    code = aff.data[0]["code"] if aff.data else "?"
    if code != expected_code:
        check.fail(f"commission affiliate {order_number}", f"got {code}")
        return
    got = int(row["commission_cents"])
    if got != expected_commission:
        check.fail(
            f"commission amount {order_number}",
            f"expected {expected_commission}, got {got}",
        )
        return
    check.ok(
        f"commission {order_number}",
        f"{expected_percent}% on {amount_cents}c → {got}c ({code})",
    )


def verify_customer_reward(check: Check, *, order_number: str, referrer_email: str) -> None:
    client = _client()
    order = client.table("orders").select("id").eq("order_number", order_number).limit(1).execute()
    if not order.data:
        check.fail("customer reward order", order_number)
        return
    order_id = order.data[0]["id"]

    comm = (
        client.table("affiliate_commissions")
        .select("id")
        .eq("order_number", order_number)
        .execute()
    )
    if comm.data:
        check.fail("customer reward no cash commission", f"found {len(comm.data)} rows")
        return
    check.ok("customer reward no cash commission")

    reward = (
        client.table("affiliate_referral_rewards")
        .select("*")
        .eq("triggered_by_order_id", order_id)
        .limit(1)
        .execute()
    )
    if not reward.data:
        check.fail("customer referral reward row")
        return
    reward_row = reward.data[0]
    if reward_row.get("recipient_email") != referrer_email.lower():
        check.fail("reward recipient", str(reward_row.get("recipient_email")))
        return
    promo_code = reward_row.get("reward_promo_code")
    promo = client.table("promo_codes").select("*").eq("code", promo_code).limit(1).execute()
    if not promo.data:
        check.fail("reward promo code", promo_code or "missing")
        return
    check.ok("customer referral reward", f"promo {promo_code} for {referrer_email}")


def verify_self_referral_blocked(check: Check) -> None:
    package_id, country, price = _pick_package()
    pricing = prepare_checkout_discounts(
        catalog_price=price,
        country=country,
        buyer_email=PAYOUT_EMAIL,
        package_id=package_id,
        promo_code=None,
        affiliate_ref=TEST_CODES["influencer"],
    )
    if pricing.discount_cents > 0 and pricing.affiliate and not pricing.affiliate.self_referral_blocked:
        check.fail("self-referral discount blocked")
    else:
        check.ok("self-referral discount blocked")


def main() -> int:
    check = Check()
    settings = get_settings()
    print(f"Affiliate E2E test run {RUN_ID}")
    print(f"Environment: {settings.environment}  ESIM_PROVIDER: {settings.esim_provider}")
    if "your-project" in settings.supabase_url:
        check.fail("supabase configured", "placeholder URL in .env — use Railway run")
        return check.summary()

    try:
        ensure_test_affiliates(check)
        verify_self_referral_blocked(check)

        package_id, country, catalog_price = _pick_package()
        check.ok("package picked", f"{country} ${catalog_price:.2f} id={package_id[:8]}…")

        # Influencer flow
        infl = create_pending_order(
            affiliate_ref=TEST_CODES["influencer"],
            buyer_email=BUYER_INFL,
            package_id=package_id,
            country=country,
            catalog_price=catalog_price,
        )
        on = infl["order_number"]
        pricing = infl["pricing"]
        if pricing.discount_cents <= 0:
            check.fail("influencer checkout discount")
        else:
            check.ok(
                "influencer checkout discount",
                f"{pricing.discount_cents}c off → {pricing.final_cents}c",
            )
        aff_meta = (infl["row"].get("metadata") or {}).get("affiliate") or {}
        if aff_meta.get("code") != TEST_CODES["influencer"]:
            check.fail("influencer metadata", json.dumps(aff_meta))
        else:
            check.ok("influencer metadata on pending order")

        fulfill_order(on)
        check.ok("influencer mock fulfill", on)

        verify_commission(
            check,
            order_number=on,
            expected_code=TEST_CODES["influencer"],
            expected_percent=10,
        )

        # Customer affiliate for buyer
        client = _client()
        cust = (
            client.table("affiliates")
            .select("code")
            .eq("referrer_email", BUYER_INFL.lower())
            .eq("type", "customer")
            .limit(1)
            .execute()
        )
        friend_on: Optional[str] = None
        if not cust.data:
            check.fail("customer affiliate created for buyer")
        else:
            customer_code = cust.data[0]["code"]
            check.ok("customer affiliate created", customer_code)

            # Refer-a-friend flow
            friend = create_pending_order(
                affiliate_ref=customer_code,
                buyer_email=BUYER_FRIEND,
                package_id=package_id,
                country=country,
                catalog_price=catalog_price,
            )
            friend_on = friend["order_number"]
            fulfill_order(friend_on)
            check.ok("refer-a-friend mock fulfill", friend_on)
            verify_customer_reward(check, order_number=friend_on, referrer_email=BUYER_INFL)

        friend_on_display = friend_on or "n/a"
        print(f"\nTest order numbers: {on}, {friend_on_display}")
        print(f"Test affiliate codes: {', '.join(TEST_CODES.values())}")

    except Exception as exc:
        check.fail("unexpected error", str(exc))
        import traceback

        traceback.print_exc()

    return check.summary()


if __name__ == "__main__":
    raise SystemExit(main())
