# NoorLink Admin Dashboard — Staff Guide

Read-only reference for support, marketing, catalog, and admin roles.
Search this document from **Help** using keywords like *fulfillment*, *refund*, *Insider*, or *security*.

---

## Sidebar overview

| Section | Purpose | Who sees it |
|---------|---------|-------------|
| **Quick start** | Step-by-step wizards for daily tasks | Role-filtered |
| **Notifications** | Live counts that need action | All roles |
| **Help** | Search, playbooks, full documentation (this guide) | All roles |
| **Finance** | Revenue, margin, exports, refunds | Admin full; Support read-only |
| **Insights** | Sales metrics, email analytics, provider health | Admin only |
| **Operations** | Health stats, tools, cron, security, scripts | Admin + support tools |
| **Tables** | Orders, promos, catalog, affiliates, audit log | Role-based |

### Marketing

| Tool | Purpose | Who |
|------|---------|-----|
| **Social media** | Partner photo/video library, captions, Meta links | Admin, marketing |
| **Creator outreach** | Creator databank, premade pitches, branded partnership emails | Admin, marketing |
| **Insider wizard** | Schedule newsletter issues | Admin, marketing, catalog |
| **Newsletter subscribers** | Export / unsubscribe | Admin, marketing, catalog |
| **Promo wizard** | Campaign discount codes (20%+ needs admin approval) | Admin, marketing, catalog |

Hidden tools (linked from Operations or Finance): Event log, Refund wizard, Breakage list, GDPR tools, Diagnostics.

### Do next (daily queue)

Sidebar → **Quick start → Do next** (or click the logo). Shows your top actions: stuck orders, tickets assigned to you, soft reminders (creator follow-ups, Insider soon, payouts). Clear red items first.

### Your layout (per browser)

- **Text size** — top bar **A− / A / A+ / A++** makes words smaller or larger (saved on this device).
- **Menu on right / left** — button in the top bar moves the sidebar to the other side (saved on this device).
- **Your shortcuts** — after you visit tools a few times, quick buttons appear for your most-used pages. **Reset** clears them.

---

## Roles

- **admin** — Full access including refunds, exports, GDPR, Insights, staff users.
- **support** — Help customer, fulfill orders, order lookup, suspended orders, Support Inbox, read-only Finance.
- **marketing** — Promo wizard, Insider, newsletter subscribers.
- **catalog** — Custom plans, catalog overview, provider SKU browser, promos.

---

## Quick start wizards

### Help a customer
Log support requests from phone/WhatsApp. Creates a ticket and optional confirmation email. Tie to order number when you have it.

### Fulfill a stuck order
Use when Stripe charged but no QR email. Enter order number → confirm → system provisions eSIM and sends email.

### Order lookup
Gift details, usage, breakage allowance, reminder history — one screen.

### Create promo code
Campaign discounts. Codes **above 20%** need admin approval before checkout works.

### Add travel plan
New checkout SKU linked to Citrus, eSIM Access, or Telna provider SKU.

### Send Insider newsletter
Write issue → test email to yourself → schedule send date. Cron sends on that day.

### Newsletter subscribers
Export CSV or unsubscribe someone on request.

### Social media toolkit
Upload partner photos/videos → copy caption → post in Meta → mark Posted. Delete old posted files when storage fills up.

### Creator outreach
Track DIY Umrah / travel creators. Pick a premade template → send branded email (or copy for Instagram DM). Update status: To contact → Messaged → Replied → Gifted → Posted → Closed.

### Send free eSIM
Complimentary plans for staff/partners — logged in audit trail.

### Record affiliate payout
1. Partner requests payout from `/partners/dashboard` (cash-paying types only, balance ≥ minimum).
2. Request appears in **Affiliate payout** wizard + ops alert.
3. **Attend within 72 hours** (click “I’m on it” or record payout) — otherwise cron **auto-approves** under strict rules (≤$500 by default, active cash partner, balance still available). Auto-approve emails the partner and escalates loudly; **you still send PayPal/Wise/bank**, then mark paid.
4. After transferring funds, use the wizard to record payout (marks commissions paid and closes the request).

Env: `AFFILIATE_AUTO_PAYOUT_WAIT_HOURS` (default 72), `AFFILIATE_AUTO_PAYOUT_MAX_CENTS` (default 50000).

### Add staff member
Create username, role, password for new team member.

### Finance dashboard (admin)
Revenue, estimated margin, affiliate liability, CSV exports, daily morning brief (6:00 New York), monthly summary email.

### Refund a customer (admin)
Stripe refund with policy: blocks if **>50% data used** unless admin override checked.

---

## Notifications hub

Check daily. Urgent items:

- **Paid but not fulfilled** → Fulfill stuck order wizard
- **Support SLA** → tickets open >24h → Support Inbox
- **Security signals** → Operations → External threats (admin)
- **Promo/catalog approval** → admin tables

---

## Finance (admin vs support)

**Admin:** revenue, margin %, affiliate owed, exports, refund link, daily brief + email monthly summary.

**Support (read-only):** revenue, order count, refunds count, stuck fulfillment — use to answer “did you charge me?” without refund access.

---

## Operations hub

- **Stats:** suspended, pending fulfillment, newsletter count, Insider due, catalog SKUs
- **Tool cards:** links to all wizards and ops tools
- **Run background tasks:** full cron (admin) — promos, Insider, Telna sync, reminders, usage
- **Admin scripts:** health check, email probe, Telna probe, expire promos, sync catalog
- **Security panel:** env checklist, staff logins, external threats (24h), audit snippet

---

## Support Inbox

Reply to customers with branded email. Inbound email via Resend webhook creates/updates tickets. Assign unassigned tickets from Notifications.

---

## Weekly Monday routine

1. Notifications — clear urgent items  
2. Finance — revenue & margin (admin)  
3. Operations — threats + run cron if Insider due  
4. Support Inbox — assign & reply to >24h tickets  
5. Help → browse how-tos by area/tag if something is stuck  

---

## Customer-facing site (for staff reference)

- **Order lookup** on website — customer enters email + order ID; can resend QR, top-up, support thread
- **Partner dashboard** — `/partners/dashboard` on noorlink.co — partners see balance with code + email

---

## Security (what staff should know)

- Failed admin logins are logged; **5 failures from one IP in 60 min** emails ops
- Do not share admin passwords; use Cloudflare Access if configured
- Refunds and GDPR actions are audit-logged

---

## When to escalate to admin

- Refunds over usage policy  
- GDPR export/delete  
- Catalog or promo approval  
- Provider API failures after Telna probe  
- Repeated security alerts  

---

## Glossary

| Term | Meaning |
|------|---------|
| Fulfillment | Provisioning eSIM + sending QR email after payment |
| Breakage | Unused data margin strategy; allowances on some orders |
| Insider | NoorLink monthly email newsletter |
| Stuck order | Status `paid` but no `qr_code_url` |
| Suspended | Data cap hit; SIM disabled on provider |

---

*Last updated: Help how-to wiki (areas + tags). Search or browse Help for any dashboard task.*
