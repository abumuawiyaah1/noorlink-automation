# Social media hub (admin dashboard)

Staff tool for partner photos/videos, posting captions, and Meta quick links.

**URL:** https://api.noorlink.co/admin/social-media  
**Roles:** `admin`, `marketing` (and `catalog` for promo-related marketing tools)

## Setup (one time)

1. Apply migration `supabase/migrations/20260830200000_social_media_assets.sql` in Supabase SQL editor (or `supabase db push`).
2. Confirm Storage bucket **`social-media-assets`** exists and is **private** (migration creates it; create manually if the insert fails).
3. Railway already needs `DATABASE_URL` and `SUPABASE_SERVICE_KEY` for the admin dashboard.

## Usage

1. Sign in at https://api.noorlink.co/admin
2. Sidebar → **Marketing** → **Social media** (or Quick start → Social media toolkit)
3. Upload partner images/videos (max 100 MB each)
4. Set status: **New** → **Ready to post** → **Posted**
5. Download when posting in Meta Business Suite / Instagram app
6. Delete posted files to stay under your ~10 GB storage budget

## Storage

Files live in Supabase Storage bucket `social-media-assets`. Metadata in Postgres table `social_media_assets`. The hub shows library usage against a **10 GB planning cap** — delete old videos when full.

## Customer website

The old `/social` page on noorlink.co is deprecated; use this admin tool instead.
