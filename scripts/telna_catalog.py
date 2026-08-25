#!/usr/bin/env python3
"""
Fetch live Telna Connect Flex catalog (normalized).

Usage:
  cd noorlink-automation
  # Ensure TELNA_API_TOKEN is in .env (never commit the token)
  python scripts/telna_catalog.py
  python scripts/telna_catalog.py --filter "Middle East|Saudi|Global"
  python scripts/telna_catalog.py --product 67f6c112d07af55d502bef78
  python scripts/telna_catalog.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def _run(args: argparse.Namespace) -> int:
    from app.core.config import get_settings
    from app.services.telna import TelnaAuthError, TelnaClient, normalize_product

    settings = get_settings()
    if not settings.telna_api_token.strip():
        print(
            "TELNA_API_TOKEN is empty. Add it to .env (see .env.example), then re-run.",
            file=sys.stderr,
        )
        return 1

    async with TelnaClient() as client:
        if args.product:
            raw = await client.get_product(args.product)
            rows = [normalize_product(raw)]
        else:
            rows = await client.catalog_summary()

    if args.filter:
        pattern = re.compile(args.filter, re.IGNORECASE)
        rows = [
            r
            for r in rows
            if pattern.search(str(r.get("name") or ""))
            or pattern.search(str(r.get("id") or ""))
            or any(pattern.search(str(c)) for c in (r.get("supported_countries") or []))
        ]

    rows.sort(key=lambda r: (str(r.get("name") or ""), str(r.get("id") or "")))

    if args.json:
        # Drop nested raw to keep output readable unless --raw
        out = []
        for row in rows:
            item = dict(row)
            if not args.raw:
                item.pop("raw", None)
            out.append(item)
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"Telna products: {len(rows)}")
    print(
        f"{'ID':<28} {'COST':>8} {'DATA_MB':>10} {'DAYS':>8}  NAME"
    )
    print("-" * 90)
    missing_cost = 0
    for row in rows:
        cost = row.get("unit_cost_usd")
        if cost is None:
            missing_cost += 1
            cost_s = "?"
        else:
            cost_s = f"${cost:.2f}"
        data_mb = row.get("data_mb")
        data_s = f"{data_mb:.0f}" if data_mb is not None else "?"
        days = row.get("duration_days")
        days_s = f"{days:.0f}" if days is not None else "?"
        name = str(row.get("name") or "")[:40]
        print(
            f"{str(row.get('id') or '')[:28]:<28} {cost_s:>8} {data_s:>10} {days_s:>8}  {name}"
        )

    if missing_cost:
        print(
            f"\nNote: {missing_cost} product(s) had no unit_cost in API response. "
            "Portal may still show price — use portal Unit Cost until Telna exposes it.",
            file=sys.stderr,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="List Telna Connect Flex products.")
    parser.add_argument("--product", help="Fetch a single product id")
    parser.add_argument(
        "--filter",
        help="Regex filter on name, id, or supported country codes",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Include raw API payload when using --json",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except TelnaAuthError as exc:
        print(f"Auth error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"Error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    # Late import for nicer CLI auth errors
    from app.services.telna import TelnaAuthError  # noqa: E402

    raise SystemExit(main())
