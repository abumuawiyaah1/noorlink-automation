#!/usr/bin/env python3
"""
Telna Connect Flex connectivity probe.

Usage:
  cd noorlink-automation
  python scripts/telna_probe.py
  python scripts/telna_probe.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def _probe() -> dict:
    from app.core.config import get_settings
    import httpx

    settings = get_settings()
    token = (settings.telna_api_token or "").strip()
    account = (settings.telna_account_id or "").strip()
    ordering = settings.telna_ordering_base_url.rstrip("/")
    diagnostic = settings.telna_diagnostic_base_url.rstrip("/")

    result: dict = {
        "token_configured": bool(token),
        "token_length": len(token),
        "account_id_configured": bool(account),
        "account_id_prefix": account[:8] if account else None,
        "ordering_base_url": ordering,
        "diagnostic_base_url": diagnostic,
        "checks": [],
    }

    if not token:
        result["ok"] = False
        result["summary"] = "TELNA_API_TOKEN is missing from .env / Railway variables."
        return result

    headers = {
        "Authorization": token,
        "Accept": "application/json",
        "User-Agent": "NoorLink/1.0 (+https://noorlink.co)",
        "Request-ID": "noorlink-probe",
    }

    probes = [
        ("list_products", f"{ordering}/products", {"count": 1, "offset": 0}),
    ]
    if account:
        probes.append(
            (
                "list_products_with_account",
                f"{ordering}/products",
                {"count": 1, "offset": 0, "account": account},
            )
        )
    probes.append(
        (
            "diagnostic_profile",
            f"{diagnostic}/euicc-profiles/0000000000000000000",
            None,
        )
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        for name, url, params in probes:
            try:
                response = await client.get(url, headers=headers, params=params)
                body = response.text[:400]
                error = None
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        error = payload.get("error")
                except ValueError:
                    error = body or None
                result["checks"].append(
                    {
                        "name": name,
                        "status_code": response.status_code,
                        "ok": response.status_code == 200,
                        "error": error,
                        "reference_id": response.headers.get("Reference-ID"),
                    }
                )
            except httpx.RequestError as exc:
                result["checks"].append(
                    {
                        "name": name,
                        "status_code": None,
                        "ok": False,
                        "error": str(exc),
                    }
                )

    product_ok = any(
        c["name"].startswith("list_products") and c.get("ok") for c in result["checks"]
    )
    if product_ok:
        result["ok"] = True
        result["summary"] = "Telna Ordering API is reachable. Run: python scripts/telna_catalog.py"
    else:
        blocked = any(
            c.get("status_code") == 403
            and "disallowed" in str(c.get("error") or "").lower()
            for c in result["checks"]
        )
        result["ok"] = False
        if blocked:
            result["summary"] = (
                "Telna returned 403 'Access to this API has been disallowed'. "
                "Your token is present but Ordering/Diagnostic API access is not enabled "
                "on this Connect Flex account. Email support@telna.com to enable API access."
            )
        else:
            result["summary"] = (
                "Telna probe failed. Check token, account id, and Telna support ticket status."
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Telna Connect Flex API access.")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    payload = asyncio.run(_probe())
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload.get("summary") or "Probe complete.")
        print()
        for check in payload.get("checks") or []:
            status = check.get("status_code")
            name = check.get("name")
            error = check.get("error") or "OK"
            ref = check.get("reference_id")
            line = f"- {name}: HTTP {status} — {error}"
            if ref:
                line += f" (Reference-ID: {ref})"
            print(line)
        if not payload.get("ok"):
            print()
            print("Next step:")
            print("  Email support@telna.com from your portal login address.")
            print("  Subject: Enable Connect Flex Ordering API — Account 6A8BF313C5A7F047663C48F8")
            print("  Ask them to enable GET /products and POST /work-orders for your account.")

    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
