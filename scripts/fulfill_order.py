#!/usr/bin/env python3
"""
Manually mark an order paid and run fulfillment (mock or live provider).

Use when Stripe checkout succeeded but the webhook did not fire — e.g. missing
or wrong STRIPE_WEBHOOK_SECRET on Railway.

Usage:
  cd noorlink-automation
  python scripts/fulfill_order.py NL-ABC123
  python scripts/fulfill_order.py NL-ABC123 --paid-only   # skip if still pending
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import supabase_repository as db
from app.services.fulfillment import FulfillmentError, fulfill_paid_order, process_paid_order


def main() -> int:
    parser = argparse.ArgumentParser(description="Fulfill a paid (or pending) order.")
    parser.add_argument("order_number", help="Order number, e.g. NL-123456")
    parser.add_argument(
        "--paid-only",
        action="store_true",
        help="Only fulfill if order is already paid/delivered (do not mark paid).",
    )
    args = parser.parse_args()
    order_number = args.order_number.strip()

    try:
        row = db.get_order_row(order_number)
    except db.SupabaseRepositoryError as exc:
        print(f"DB error: {exc}", file=sys.stderr)
        return 1

    if not row:
        print(f"Order not found: {order_number}", file=sys.stderr)
        return 1

    status = row.get("status")
    print(f"Order {order_number} status={status} email={row.get('email')}")

    try:
        if args.paid_only:
            if status not in ("paid", "delivered", "active"):
                print(
                    f"Order is {status!r}; use without --paid-only to mark paid first.",
                    file=sys.stderr,
                )
                return 1
            result = fulfill_paid_order(row)
        else:
            result = process_paid_order(order_number=order_number)
    except FulfillmentError as exc:
        print(f"Fulfillment failed: {exc}", file=sys.stderr)
        return 1
    except db.SupabaseRepositoryError as exc:
        print(f"DB error: {exc}", file=sys.stderr)
        return 1

    if not result:
        print("No order updated.", file=sys.stderr)
        return 1

    print(f"Done. status={result.get('status')} qr={bool(result.get('qr_code_url'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
