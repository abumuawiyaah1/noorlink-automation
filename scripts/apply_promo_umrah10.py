#!/usr/bin/env python3
"""Create / refresh WhatsApp promo code UMRAH10 (10% off).

Uses SUPABASE_URL + SUPABASE_SERVICE_KEY from noorlink-automation/.env
(or Railway: railway run python3 scripts/apply_promo_umrah10.py).

Usage:
  python3 scripts/apply_promo_umrah10.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

CODE = "UMRAH10"
LABEL = "WhatsApp Umrah 10% off"
PERCENT = 10
STARTS_AT = "2026-09-22T00:00:00+00:00"
ENDS_AT = "2027-08-31T23:59:59+00:00"
SHARE_URL = "https://noorlink.co/hajj-umrah?promo=UMRAH10"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_KEY"):
        if os.getenv(key):
            env[key] = os.getenv(key, "").strip()
    return env


def main() -> int:
    env = load_env()
    url = env.get("SUPABASE_URL") or ""
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_KEY") or ""
    if not url or "your-project" in url or not key or len(key) < 40:
        print(
            "Missing real Supabase credentials.\n\n"
            "Option A — fill SUPABASE_URL + SUPABASE_SERVICE_KEY in .env\n"
            "Option B — from a linked Railway project:\n"
            "  railway run python3 scripts/apply_promo_umrah10.py\n"
            "Option C — Admin → Promo code wizard at /admin/promo-wizard\n",
            file=sys.stderr,
        )
        return 1

    from supabase import create_client

    client = create_client(url, key)
    payload = {
        "code": CODE,
        "label": LABEL,
        "percent_off": PERCENT,
        "amount_off_cents": None,
        "starts_at": STARTS_AT,
        "ends_at": ENDS_AT,
        "is_active": True,
        "admin_approved": True,
        "min_order_cents": 0,
        "max_redemptions": None,
        "insider_issue_slug": None,
    }

    existing = (
        client.table("promo_codes")
        .select("code")
        .eq("code", CODE)
        .limit(1)
        .execute()
    )
    if existing.data:
        client.table("promo_codes").update(
            {
                "label": LABEL,
                "percent_off": PERCENT,
                "starts_at": STARTS_AT,
                "ends_at": ENDS_AT,
                "is_active": True,
                "admin_approved": True,
                "min_order_cents": 0,
            }
        ).eq("code", CODE).execute()
        action = "updated"
    else:
        client.table("promo_codes").insert(payload).execute()
        action = "created"

    row = (
        client.table("promo_codes")
        .select(
            "code,label,percent_off,is_active,starts_at,ends_at,admin_approved,redemption_count"
        )
        .eq("code", CODE)
        .single()
        .execute()
    )

    msg = (
        "Hi — here’s 10% off on NoorLink travel eSIM for Umrah & Hajj.\n\n"
        f"Open this link and checkout: {SHARE_URL}\n\n"
        f"Or enter code {CODE} at checkout on noorlink.co."
    )
    print(action)
    print(row.data)
    print("SHARE_URL", SHARE_URL)
    print("WA_URL", f"https://wa.me/?text={quote(msg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
