#!/usr/bin/env python3
"""Apply Insider Year 2 + Ramadan/Hajj specials migration to Supabase.

Requires DATABASE_URL in .env (Supabase → Project Settings → Database → URI).

Usage:
  python3 scripts/apply_insider_year2_specials.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "supabase" / "migrations" / "20260827120000_insider_year2_specials.sql"
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
        "2. Copy the URI connection string (Transaction or Session pooler is fine)\n"
        "3. Add to noorlink-automation/.env:\n"
        "   DATABASE_URL=postgresql://postgres.[ref]:[YOUR-PASSWORD]@...\n",
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
            cur.execute(
                """
                select slug, audience, status, promo_code
                from public.insider_issues
                where slug in (
                  '2027-01-ramadan-special',
                  '2027-04-hajj-special',
                  '2027-09-morocco-maghreb'
                )
                order by send_at
                """
            )
            rows = cur.fetchall()
        print("Migration applied successfully.\n")
        print("Check:")
        for row in rows:
            print(f"  {row[0]}  audience={row[1]}  status={row[2]}  promo={row[3]}")
        if len(rows) < 3:
            print("\nWarning: expected 3 rows; verify in SQL Editor.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
