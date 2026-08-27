#!/usr/bin/env bash
# Generate CRON_SECRET and set it on GitHub Actions + Railway (same value).
# Usage:
#   cd noorlink-automation
#   ./scripts/setup_cron_secret.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SECRET="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"

echo "Setting CRON_SECRET on GitHub Actions (noorlink-automation)..."
gh secret set CRON_SECRET --repo abumuawiyaah1/noorlink-automation --body "$SECRET"

echo "Setting CRON_SECRET on Railway..."
if ! railway whoami >/dev/null 2>&1; then
  echo "Railway CLI not logged in. Run: railway login"
  echo "Then re-run this script, or paste this value in Railway → Variables:"
  echo "CRON_SECRET=$SECRET"
  exit 1
fi

railway variables set "CRON_SECRET=$SECRET"
echo "Done. CRON_SECRET is set on GitHub Actions and Railway."
