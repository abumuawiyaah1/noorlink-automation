# Social media hub (admin dashboard)

Staff tool for partner photos/videos, posting captions, and Meta quick links.

**Where:** Sidebar → Marketing → **Social media**  
**Who:** Admin and marketing

## How to use (staff)

1. Open Social media toolkit.
2. Upload partner images/videos (keep each file under ~100 MB).
3. Set status: **New → Ready to post → Posted**.
4. Copy the caption, then open Meta Business Suite / Instagram to publish.
5. Mark Posted when done. Delete old posted files when the library gets full (~10 GB planning cap).

Search Help → tag **social** for the short how-to.

## Setup (admin / engineering — one time)

1. Apply migration `supabase/migrations/20260830200000_social_media_assets.sql`.
2. Confirm Storage bucket **`social-media-assets`** exists and is **private**.
3. Railway needs database access (same as the rest of admin).

The old `/social` page on noorlink.co is deprecated; use this admin tool instead.
