#!/usr/bin/env python3
"""
Create or update a NoorLink admin dashboard user.

Usage:
  railway run python3 scripts/create_admin_user.py
  ADMIN_USERNAME=you ADMIN_PASSWORD='...' ADMIN_ROLE=owner python3 scripts/create_admin_user.py

To create/update an OWNER account you must also set:
  OWNER_RECOVERY_SECRET=<same value as on Railway>

Password must be at least 12 characters. Requires DATABASE_URL.
"""

from __future__ import annotations

import getpass
import hmac
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import select

from app.admin.passwords import MIN_PASSWORD_LENGTH, hash_password
from app.admin.roles import ALL_ROLES, ROLE_OWNER
from app.db.engine import get_engine, get_session_factory
from app.db.models import AdminUser


def main() -> int:
    username = (os.environ.get("ADMIN_USERNAME") or "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    display_name = (os.environ.get("ADMIN_DISPLAY_NAME") or "").strip()
    role = (os.environ.get("ADMIN_ROLE") or "admin").strip().lower()

    if role not in ALL_ROLES:
        print(f"Invalid ADMIN_ROLE: {role}. Allowed: {', '.join(sorted(ALL_ROLES))}", file=sys.stderr)
        return 1

    if role == ROLE_OWNER:
        secret = (os.environ.get("OWNER_RECOVERY_SECRET") or "").strip()
        if len(secret) < 16:
            print(
                "Creating an owner requires OWNER_RECOVERY_SECRET (≥16 chars) on the environment.",
                file=sys.stderr,
            )
            return 1
        confirm = (os.environ.get("OWNER_RECOVERY_SECRET_CONFIRM") or "").strip()
        if confirm and not hmac.compare_digest(secret, confirm):
            print("OWNER_RECOVERY_SECRET_CONFIRM mismatch.", file=sys.stderr)
            return 1

    if not username:
        username = input("Admin username: ").strip().lower()
    if not password:
        password = getpass.getpass("Password (min 12 chars): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    if len(username) < 3:
        print("Username must be at least 3 characters.", file=sys.stderr)
        return 1
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1

    if get_engine() is None:
        print("DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    session_factory = get_session_factory()
    assert session_factory is not None

    password_hash = hash_password(password)
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        existing = session.execute(
            select(AdminUser).where(AdminUser.username == username)
        ).scalar_one_or_none()

        if existing:
            existing.password_hash = password_hash
            existing.display_name = display_name or existing.display_name
            existing.role = role
            existing.is_active = True
            existing.is_protected = role == ROLE_OWNER or bool(existing.is_protected and role == ROLE_OWNER)
            if role == ROLE_OWNER:
                existing.is_protected = True
            existing.updated_at = now
            session.commit()
            print(f"Updated admin user '{username}' (role={role}).")
            return 0

        user = AdminUser(
            username=username,
            password_hash=password_hash,
            display_name=display_name or username,
            role=role,
            is_active=True,
            is_protected=(role == ROLE_OWNER),
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.commit()
        print(f"Created admin user '{username}' (role={role}).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
