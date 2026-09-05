# Creator outreach (admin dashboard)

Staff CRM for DIY Umrah / Muslim travel creators: contacts, premade pitches, and branded emails.

**URL:** https://api.noorlink.co/admin/creator-outreach  
**Roles:** `admin`, `marketing` (same as Social media / promos)

## Setup (one time)

1. Run migration in Supabase SQL editor (or `supabase db push`):

   `supabase/migrations/20260905000000_creator_outreach_contacts.sql`

2. Confirm Railway already has `RESEND_API_KEY` and `RESEND_FROM_EMAIL` (same as order emails). No extra Cloudflare secrets needed for this tool.

## Usage

1. Sign in at https://api.noorlink.co/admin  
2. Sidebar → **Marketing** → **Creator outreach** (or Quick start card)  
3. First open seeds Wave 1–3 starter creators (edit freely)  
4. Add email + pick a premade template → **Send branded email**  
5. Or **Copy for DM** for Instagram outreach  

Statuses: To contact → Messaged → Replied → Gifted → Posted → Closed

## Branding

Emails use `wrap_branded_email` from `app/services/email_brand.py` (teal header, orange CTA, light body) — same chrome as transactional mail.

## Note

The temporary website tool at `https://noorlink.co/team/outreach` can stay as a backup or be retired later. Prefer this admin hub going forward.
