# Backup & restore guide

How to protect NoorLink customer and order data (Supabase Postgres + operational exports).

## Supabase point-in-time recovery (PITR)

**Recommended for production.**

1. Supabase Dashboard → **Project Settings → Database → Backups**
2. Enable **Point in Time Recovery** (Pro plan or higher)
3. Retention: 7 days minimum; 30 days if budget allows
4. Document recovery RPO/RTO with your team: typically minutes of data loss, ~15–30 min restore

**To restore:** open a support ticket with Supabase or use Dashboard restore to a new project, then repoint `DATABASE_URL` / `SUPABASE_URL` on Railway after validation.

## Weekly logical export (manual cadence)

Every **Monday** (or after major catalog changes):

| Export | How |
|--------|-----|
| Orders + revenue | Admin → Finance → Export orders CSV |
| Affiliate commissions | Admin → Finance → Export commissions CSV |
| GDPR bundle (spot check) | Admin → Privacy tools → export one test email |
| Promo / Insider snapshot | Admin → Insights → note top promos |

Store CSVs in a **private** folder (1Password, Google Drive restricted, or S3 with encryption). Do not commit to Git.

## Environment secrets backup

Maintain an offline copy of Railway env vars (1Password vault):

- `DATABASE_URL`, `SUPABASE_*`, Stripe keys, Resend, provider API keys, `CRON_SECRET`, `SECRET_KEY`, webhook secrets

## What is NOT in Supabase alone

- Resend send history (use Resend dashboard + `email_delivery_events` table)
- Stripe charges (Stripe Dashboard is source of truth)
- Provider wallet balances (Citrus/Simbase/Telna portals)

## Disaster recovery runbook

1. Confirm outage scope (Railway, Supabase, Cloudflare, Stripe)
2. Check **Operations → Event log** and Railway logs for last successful webhook
3. If DB corrupt: restore Supabase PITR to staging project first
4. Replay stuck orders: Admin → Fulfill stuck order / `scripts/fulfill_order.py`
5. Notify customers if QR emails were delayed >24h

## Retention policy

- Ops event log: **90 days** (cron purge)
- Email delivery events: follow Supabase storage; export monthly if needed for compliance
- Support tickets: keep indefinitely unless GDPR deletion request
