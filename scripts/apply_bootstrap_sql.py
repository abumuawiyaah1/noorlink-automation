#!/usr/bin/env python3
"""Apply bootstrap_plans_minimal.sql to Supabase Postgres.

Requires DATABASE_URL in .env (Supabase → Settings → Database → Connection string).

Usage:
  python3 scripts/apply_bootstrap_sql.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "supabase" / "migrations" / "20260607000000_bootstrap_plans_minimal.sql"
ENV_FILE = ROOT / ".env"


def load_database_url() -> str:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")

    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url

    print(
        "Missing DATABASE_URL.\n\n"
        "1. Supabase Dashboard → Project Settings → Database\n"
        "2. Copy the URI connection string (use the database password)\n"
        "3. Add to .env:\n"
        "   DATABASE_URL=postgresql://postgres.[ref]:[password]@...\n",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> int:
    if not SQL_FILE.exists():
        print(f"SQL file not found: {SQL_FILE}", file=sys.stderr)
        return 1

    try:
        import psycopg2
    except ImportError:
        print("Installing psycopg2-binary...", file=sys.stderr)
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"]
        )
        import psycopg2

    database_url = load_database_url()
    sql = SQL_FILE.read_text()

    print(f"Applying {SQL_FILE.name} ...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        print("Bootstrap applied successfully.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
