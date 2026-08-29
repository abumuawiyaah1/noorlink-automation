# Owner protection & break-glass recovery

Protects you if a full **admin** tries to lock you out of `/admin`.

## Roles

| Role | Meaning |
|------|---------|
| **owner** | Business owner (you). Full access. Protected from demote/deactivate by others. |
| **admin** | Day-to-day full ops. **Cannot** create admin/owner, or change owner/admin accounts. |
| support / finance / legal / … | Limited scopes (preferred for most staff) |

## What a rogue admin cannot do

- Demote, deactivate, or edit your **owner** account from the UI  
- Create another **admin** or **owner**  
- Deactivate the last active owner  
- Touch Stripe / domain / Railway / Supabase (keep those accounts yours only)

## First-time setup

1. Apply migration `20260829280000_admin_owner_protection.sql`
2. Set on Railway: `OWNER_RECOVERY_SECRET` = long random string (≥16 chars)
3. Promote yourself to owner:

```bash
OWNER_RECOVERY_SECRET='your-secret' \
ADMIN_USERNAME='you' \
ADMIN_PASSWORD='...' \
ADMIN_ROLE=owner \
railway run python3 scripts/create_admin_user.py
```

4. Give day-to-day people **support / finance / legal / marketing / catalog** — not owner  
5. If you must share ops power, give **admin** (not owner)

## If you are locked out

```bash
OWNER_RECOVERY_SECRET='your-secret' \
OWNER_USERNAME='you' \
OWNER_PASSWORD='new-strong-password' \
DEACTIVATE_USERNAME='rogue' \
railway run python3 scripts/recover_owner.py
```

Then optionally rotate `SECRET_KEY` on Railway to kill all sessions.

## Alerts

Set `OPS_ALERT_EMAIL` and/or `SLACK_WEBHOOK_URL`. You get notified when:

- A staff login is created  
- A staff role / active flag changes  
- Break-glass recovery runs  

## Still keep outside the app

Domain registrar, Cloudflare, Railway, Supabase, Stripe — **only you** (or a sealed co-owner).
