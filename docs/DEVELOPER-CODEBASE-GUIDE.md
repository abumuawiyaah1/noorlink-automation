# NoorLink Developer Codebase Guide

**Read-only — admin role only.** Research reference for engineers working on NoorLink automation (backend) and the Next.js storefront.

Search keywords: *api*, *webhook*, *migration*, *supabase*, *stripe*, *admin*, *cron*, *fulfillment*.

---

## Repositories

| Repo | Path (local example) | Deploy |
|------|----------------------|--------|
| **noorlink-automation** | Backend API + admin SQLAdmin | Railway → `api.noorlink.co` |
| **new noorlink-next site** | Next.js customer site | Vercel → `noorlink.co` |

---

## Backend stack

- **FastAPI** — public API (`app/api/main.py`)
- **SQLAdmin** — staff dashboard (`app/admin/`)
- **Supabase** — Postgres + REST (`app/api/supabase_repository.py`)
- **SQLAlchemy** — admin ORM (`app/db/models.py`) via `DATABASE_URL` pooler
- **Stripe** — checkout + webhooks
- **Resend** — transactional + Insider email
- **Providers** — Citrus, Telna, eSIM Access, Simbase (`app/services/`)

---

## Key API routes (public)

```
GET  /api/orders/lookup              — customer order lookup
POST /api/orders/resend-esim         — customer QR resend (cooldown)
GET  /api/orders/topup/options       — top-up eligibility
POST /api/orders/topup/session       — Stripe top-up checkout
GET  /api/orders/support-messages    — order-scoped support thread
POST /api/checkout/session           — new purchase
POST /api/stripe/webhook             — Stripe events
POST /api/cron/run                   — scheduled jobs (CRON_SECRET)
GET  /api/affiliate/resolve          — validate ref code
GET  /api/affiliate/referral-link    — customer refer-a-friend
GET  /api/affiliate/dashboard        — partner self-service
POST /api/contact                    — support form
POST /api/newsletter/subscribe       — Insider signup
```

---

## Webhooks (`app/api/webhooks.py`)

```
POST /api/v1/webhooks/simbase
POST /api/v1/webhooks/citrus
POST /api/v1/webhooks/esimaccess
POST /api/v1/webhooks/resend/inbound    — support email → tickets
POST /api/v1/webhooks/resend/events     — bounce, complaint, delivered
```

---

## Admin mount (`app/admin/setup.py`)

Base URL: `/admin`

Categories: Quick start, Notifications, Help, Finance, Insights, Operations + SQLAdmin model tables.

Views (BaseView): wizards, finance_hub, insights_hub, operations_hub, support_inbox, event_log, gdpr, etc.

Auth: `app/admin/auth.py` — session cookies, bcrypt passwords in `admin_users` table.

IP guard: `ADMIN_ALLOWED_IPS` → `app/admin/ip_guard.py`

---

## Services map (backend)

| Service | Role |
|---------|------|
| `fulfillment.py` | Post-payment eSIM + email pipeline |
| `admin_operations.py` | Ops summary, manual fulfill, cron subset |
| `admin_finance.py` | Revenue snapshot, CSV exports |
| `admin_refunds.py` | Stripe refunds + usage policy |
| `admin_notifications.py` | In-dashboard alert counts |
| `security_threats.py` | External security event log + login alerts |
| `ops_event_log.py` | `ops_event_log` + `email_delivery_events` tables |
| `insider_release.py` | Schedule/send Insider issues |
| `support_messaging.py` | Tickets + threaded messages |
| `affiliate_portal.py` | Partner dashboard API |
| `admin_help_playbooks.py` | Help search + doc registry |

---

## Database migrations (`supabase/migrations/`)

Apply in order:

1. `20260829180000_admin_dashboard.sql`
2. `20260829200000_support_messaging.sql`
3. `20260829210000_support_ticket_notifications.sql`
4. `20260829220000_admin_marketing_role.sql`
5. `20260829230000_promo_admin_approval.sql`
6. `20260829240000_catalog_admin_approval.sql`
7. `20260829250000_ops_business_dashboard.sql` — ops_event_log, email_delivery_events, gdpr_requests

---

## Environment variables (critical)

```
DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
RESEND_API_KEY, RESEND_FROM_EMAIL
SECRET_KEY, CRON_SECRET, ADMIN_ENABLED=true
OPS_ALERT_EMAIL, SLACK_WEBHOOK_URL
APP_URL, CORS_ORIGINS
ADMIN_ALLOWED_IPS (optional)
TELNA_API_TOKEN, CITRUS_API_KEY, ESIM_ACCESS_ACCESS_CODE, SIMBASE_API_KEY
RESEND_INBOUND_WEBHOOK_SECRET, RESEND_EVENTS_WEBHOOK_SECRET
```

See `.env.example` for full list.

---

## Cron (`POST /api/cron/run`)

Daily job: expire promos, send due Insider, Telna catalog sync, expiry reminders, usage sync, log retention (90d), **48h support auto-refund** (strict), **72h affiliate payout auto-approve** (strict; still send funds manually). Day 1 of month: finance summary email.

Env: `SUPPORT_AUTO_REFUND_*`, `AFFILIATE_AUTO_PAYOUT_WAIT_HOURS`, `AFFILIATE_AUTO_PAYOUT_MAX_CENTS`.
Service: `app/services/affiliate_payout_requests.py`. Migration: `20260829290000_affiliate_payout_requests.sql`.

---

## Frontend (Next.js)

```
app/(site)/          — marketing, support, partners, dashboard
app/(minimal)/       — checkout, success, gift
lib/orders-api.ts    — order lookup, resend, top-up, support messages
lib/affiliate-api.ts — affiliate resolve, partner dashboard
components/orders/   — OrderLookupCard, TopUp, SupportThread
styles/tokens.css    — brand colors (#0F3D3E, #FF9500)
```

Brand rule: deal/promo cards = light surface; teal for headers; orange CTAs.

---

## Tests

```
tests/test_admin_wizards.py
tests/test_admin_hybrid_nav.py
tests/test_admin_business_phases.py
tests/test_security_threats.py
tests/test_recommendations.py
```

Run: `python3 -m pytest tests/ -q`

---

## Event log event types

- `stripe_webhook`, `fulfillment_success`, `fulfillment_failed`
- `order_refunded`, `customer_resend_esim`
- `security_*` — login failures, IP blocks, bad webhooks

Filter in admin: `/admin/event-log?type=security_`

---

## Adding new admin features

1. Service in `app/services/admin_*.py`
2. BaseView in `app/admin/views/`
3. Template in `app/admin/templates/`
4. Register in `app/admin/setup.py`
5. Optional: wizard in `wizard_catalog.py`, tool in `tools_catalog.py`, playbook in `admin_help_playbooks.py`
6. Update `docs/ADMIN-DASHBOARD-GUIDE.md` and this file

---

## Local dev

```bash
# Backend
cd noorlink-automation
uvicorn app.api.main:app --reload

# Frontend
cd "new noorlink-next site"
npm run dev

# Admin: http://localhost:8000/admin (needs DATABASE_URL)
# Create user: python3 scripts/create_admin_user.py
```

---

*Read-only research doc. Do not store secrets in this file.*
