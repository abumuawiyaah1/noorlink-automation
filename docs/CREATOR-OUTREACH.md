# Creator outreach (admin dashboard)

Staff CRM for DIY Umrah / Muslim travel creators: contacts, premade pitches, and branded emails.

**Where:** Sidebar → Marketing → **Creator outreach**  
**Who:** Admin and marketing (same as Social media)

## How to use (staff)

1. Open Creator outreach (or Quick start → Creator outreach).
2. First visit loads starter Wave 1–3 creators — edit freely.
3. Select a creator, add their email if missing.
4. Pick a premade template (gifted collab, follow-up, group trip, thank-you).
5. Click **Send branded email** — they get a NoorLink-branded message (same look as order emails).
6. Or **Copy for DM** if you’re messaging on Instagram instead.
7. Update status as you go: **To contact → Messaged → Replied → Gifted → Posted → Closed**.

Tips:
- Keep notes short (what they asked for, code you offered).
- Prefer gifted eSIM + a small affiliate % over cash sponsorships for micro creators.
- Search Help → tag **outreach** for the short how-to.

## Setup (admin / engineering — one time)

1. Run migration: `supabase/migrations/20260905000000_creator_outreach_contacts.sql`
2. Confirm Railway has Resend configured (same as order emails).

Prefer this admin hub over the temporary website page at `/team/outreach`.
