#!/usr/bin/env python3
"""
Zero-cost gift E2E test: pending gift order, mock fulfill, verify metadata.

Usage:
  cd noorlink-automation
  ESIM_PROVIDER=mock railway run python3 scripts/gift_e2e_test.py
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["ESIM_PROVIDER"] = "mock"

from app.api import supabase_repository as db
from app.core.config import get_settings
from app.services.fulfillment import process_paid_order
from app.services.gift_orders import build_gift_metadata, validate_gift_checkout
from app.api.schemas import CheckoutSessionRequest, GiftCheckoutDetails

RUN_ID = uuid.uuid4().hex[:6].upper()
BUYER = f"gift.e2e.buyer.{RUN_ID.lower()}@gmail.com"
RECIPIENT = f"gift.e2e.friend.{RUN_ID.lower()}@gmail.com"


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


def _pick_package():
    client = db.get_supabase_client()
    result = (
        client.table("esim_packages")
        .select("id, country, price_cents")
        .eq("is_active", True)
        .order("price_cents")
        .limit(30)
        .execute()
    )
    for row in result.data or []:
        country = str(row.get("country") or "").lower()
        if "saudi" in country or "caribbean" in country:
            continue
        price_cents = int(row.get("price_cents") or 0)
        if price_cents >= 500:
            return str(row["id"]), str(row.get("country") or "turkey"), price_cents / 100.0
    raise RuntimeError("No suitable package found.")


def main() -> int:
    check = Check()
    settings = get_settings()
    print(f"Gift E2E test run {RUN_ID}")
    print(f"Environment: {settings.environment}  ESIM_PROVIDER: {settings.esim_provider}")

    if "your-project" in settings.supabase_url:
        check.fail("supabase configured", "use railway run for prod credentials")
        return check.summary()

    try:
        package_id, country, price = _pick_package()
        check.ok("package picked", f"{country} ${price:.2f}")

        body = CheckoutSessionRequest(
            country=country,
            price=price,
            email=BUYER,
            packageId=package_id,
            isGift=True,
            gift=GiftCheckoutDetails(
                recipientEmail=RECIPIENT,
                recipientName="Gift Friend",
                giftMessage=f"Safe travels — test {RUN_ID}",
                senderName="Gift Tester",
            ),
        )
        validate_gift_checkout(body)
        check.ok("gift validation")

        with_check = CheckoutSessionRequest(
            country=country,
            price=price,
            email=BUYER,
            packageId=package_id,
            isGift=True,
            gift=GiftCheckoutDetails(
                recipientEmail=BUYER,
                recipientName="Self",
            ),
        )
        try:
            validate_gift_checkout(with_check)
            check.fail("self-recipient blocked")
        except Exception:
            check.ok("self-recipient blocked")

        gift_meta = build_gift_metadata(body)
        if not gift_meta or not gift_meta.get("is_gift"):
            check.fail("gift metadata built")
        else:
            check.ok("gift metadata built", gift_meta["recipient_email"])

        created = db.create_order(
            email=BUYER,
            country=country,
            price=price,
            flag=None,
            travel_date=None,
            package_id=package_id,
            gift_metadata=gift_meta,
        )
        order_number = created.order.order_number
        row = db.get_order_row_by_order_number(order_number)
        if not row:
            check.fail("order created")
            return check.summary()

        meta_gift = (row.get("metadata") or {}).get("gift") or {}
        if meta_gift.get("recipient_email") != RECIPIENT.lower():
            check.fail("gift metadata on order")
        else:
            check.ok("gift metadata on order", order_number)

        if not db.order_access_email_matches(row, BUYER):
            check.fail("buyer order access")
        else:
            check.ok("buyer order access")

        if not db.order_access_email_matches(row, RECIPIENT):
            check.fail("recipient order access")
        else:
            check.ok("recipient order access")

        result = process_paid_order(order_number=order_number)
        if not result or result.get("status") != "delivered":
            check.fail("mock fulfill", str(result.get("status") if result else "none"))
        else:
            check.ok("mock fulfill", order_number)

        refreshed = db.get_order_row_by_order_number(order_number) or result
        from app.services.order_customer_view import enrich_order_row

        _, order = enrich_order_row(refreshed)
        if not order.is_gift:
            check.fail("order.is_gift flag")
        else:
            check.ok("order.is_gift flag")
        if order.gift_recipient_email != RECIPIENT.lower():
            check.fail("order gift recipient email")
        else:
            check.ok("order gift recipient email", order.gift_recipient_name or "")

        fulfillment = (refreshed.get("metadata") or {}).get("fulfillment") or {}
        if not fulfillment.get("email_sent"):
            check.fail("fulfillment email sent flag")
        else:
            check.ok("fulfillment email sent flag")

        comm = (
            db.get_supabase_client()
            .table("affiliate_commissions")
            .select("id")
            .eq("order_number", order_number)
            .execute()
        )
        if comm.data:
            check.fail("no affiliate commission on gift")
        else:
            check.ok("no affiliate commission on gift")

        print(f"\nTest order: {order_number}")
        print(f"Buyer: {BUYER}")
        print(f"Recipient: {RECIPIENT}")

    except Exception as exc:
        check.fail("unexpected error", str(exc))
        import traceback

        traceback.print_exc()

    return check.summary()


if __name__ == "__main__":
    raise SystemExit(main())
