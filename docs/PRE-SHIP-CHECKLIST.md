# Pre-ship checklist (next wave #1–6)

Complete these **before** production traffic. Each item maps to a ship-blocker from the dashboard audit.

## 1. Apply Supabase migrations

Run every migration in `supabase/migrations/` against production Supabase (Dashboard → SQL or `supabase db push`).

**Minimum set for admin dashboard + ops (apply in filename order):**

| Migration | Purpose |
|-----------|---------|
| `20260828180000_affiliate_system.sql` | Affiliates, commissions, payouts |
| `20260829290000_affiliate_payout_requests.sql` | Partner payout request queue + 72h auto-approve |
| `20260829180000_admin_dashboard.sql` | Admin users, roles, audit log |
| `20260829200000_support_messaging.sql` | Support threads |
| `20260829210000_support_ticket_notifications.sql` | Ticket email alerts |
| `20260829220000_admin_marketing_role.sql` | Marketing role |
| `20260829230000_promo_admin_approval.sql` | Promo approval workflow |
| `20260829240000_catalog_admin_approval.sql` | Catalog approval workflow |
| `20260829250000_ops_business_dashboard.sql` | Event log, email delivery, GDPR |
| `20260829260000_support_ticket_language.sql` | Ticket language tags |
| `20260829270000_company_documents_vault.sql` | Legal/accounting vault + finance/legal roles |
| `20260829280000_admin_owner_protection.sql` | Owner role + protected accounts |

Earlier catalog/checkout migrations must already be applied on the project.

After owner migration: set `OWNER_RECOVERY_SECRET`, promote yourself with `ADMIN_ROLE=owner` (see `docs/OWNER-PROTECTION.md`).

## 2. Lock down `/admin`

Choose at least one:

- **Cloudflare Access** on `api.noorlink.co/admin/*` (Help → Lock down /admin with Cloudflare)
- **`ADMIN_ALLOWED_IPS`** on Railway — comma-separated office/home IPs

## 3. Wire Resend webhooks

In [Resend → Webhooks](https://resend.com/webhooks):

| Event | URL |
|-------|-----|
| Delivery events | `https://api.noorlink.co/api/v1/webhooks/resend/events` |
| Inbound email | `https://api.noorlink.co/api/v1/webhooks/resend/inbound` |

Set `RESEND_EVENTS_WEBHOOK_SECRET` and `RESEND_INBOUND_WEBHOOK_SECRET` on Railway.

## 4. Schedule daily cron

Hit `POST https://api.noorlink.co/api/cron/run` once per day with header:

`Authorization: Bearer YOUR_CRON_SECRET`

(GitHub Actions workflow `.github/workflows/insider-cron.yml` already does this.)

Tasks: expire promos, Insider send queue, Telna catalog sync, expiry reminders, usage sync, log retention (90 days), 48h auto-refunds, 72h affiliate payout auto-approve, monthly finance summary on the 1st UTC.

## 5. Create admin user

```bash
python scripts/create_admin_user.py --username you --email you@noorlink.co --role admin
```

Create separate users for support, marketing, and catalog roles as needed.

## 6. Do not commit nested repo copy

The folder `noorlink-automation/noorlink-automation/` inside this repo is an accidental clone — it is in `.gitignore`. Never stage or push it.

## Verify before launch

- [ ] `pytest` passes locally
- [ ] Stripe webhook endpoint live in Dashboard (test + live)
- [ ] `OPS_ALERT_EMAIL` or `SLACK_WEBHOOK_URL` set
- [ ] Smoke test: checkout → fulfillment → order lookup → support ticket
