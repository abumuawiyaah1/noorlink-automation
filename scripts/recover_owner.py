#!/usr/bin/env python3
"""
Break-glass: restore or create a business OWNER account and optionally disable a rogue admin.

This script is intentionally CLI-only (Railway / local). It is NOT exposed in the web UI.

Usage:
  # Set a long random secret in Railway, then:
  OWNER_RECOVERY_SECRET='your-secret' \\
  OWNER_USERNAME='you' \\
  OWNER_PASSWORD='...' \\
  railway run python3 scripts/recover_owner.py

  # Also deactivate a compromised admin:
  OWNER_RECOVERY_SECRET='...' OWNER_USERNAME='you' OWNER_PASSWORD='...' \\
  DEACTIVATE_USERNAME='rogue' \\
  railway run python3 scripts/recover_owner.py

Requires:
  - DATABASE_URL
  - OWNER_RECOVERY_SECRET matching the env var on Railway
"""

from __future__ import annotations

import getpass
import hmac
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db.engine import get_engine
from app.services.admin_owner_guard import OwnerGuardError, recover_or_create_owner
from app.services.ops_alerts import notify_staff_governance


def main() -> int:
    expected = (os.environ.get("OWNER_RECOVERY_SECRET") or "").strip()
    provided = (os.environ.get("OWNER_RECOVERY_SECRET_CONFIRM") or expected).strip()
    # Require the secret to be set and non-trivial
    if len(expected) < 16:
        print(
            "Set OWNER_RECOVERY_SECRET to a long random value (≥16 chars) on Railway before using break-glass.",
            file=sys.stderr,
        )
        return 1

    # Optional second factor: if CONFIRM is set, it must match
    confirm = (os.environ.get("OWNER_RECOVERY_SECRET_CONFIRM") or "").strip()
    if confirm and not hmac.compare_digest(expected, confirm):
        print("OWNER_RECOVERY_SECRET_CONFIRM does not match OWNER_RECOVERY_SECRET.", file=sys.stderr)
        return 1

    if get_engine() is None:
        print("DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    username = (os.environ.get("OWNER_USERNAME") or "").strip().lower()
    password = os.environ.get("OWNER_PASSWORD") or ""
    display_name = (os.environ.get("OWNER_DISPLAY_NAME") or "").strip()
    deactivate = (os.environ.get("DEACTIVATE_USERNAME") or "").strip().lower() or None

    if not username:
        username = input("Owner username to restore/create: ").strip().lower()
    if not password:
        password = getpass.getpass("New owner password (min 12 chars): ")
        confirm_pw = getpass.getpass("Confirm password: ")
        if password != confirm_pw:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    try:
        result = recover_or_create_owner(
            username=username,
            password=password,
            display_name=display_name,
            deactivate_username=deactivate,
        )
    except OwnerGuardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    notify_staff_governance(
        title="Break-glass owner recovery used",
        summary=f"Owner account '{result['username']}' was restored via CLI recovery.",
        details={"actions": ", ".join(result.get("actions") or []), "username": result["username"]},
    )

    print(f"OK — owner ready: {result['username']}")
    for action in result.get("actions") or []:
        print(f"  - {action}")
    print("Log in at /admin, then rotate SECRET_KEY if sessions were compromised.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
