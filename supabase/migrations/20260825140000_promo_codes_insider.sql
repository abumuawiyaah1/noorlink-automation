-- Promo codes + Insider auto-release schedule

create table if not exists public.promo_codes (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  label text,
  percent_off integer,
  amount_off_cents integer,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  is_active boolean not null default true,
  max_redemptions integer,
  redemption_count integer not null default 0,
  min_order_cents integer not null default 0,
  insider_issue_slug text,
  created_at timestamptz not null default now(),
  constraint promo_codes_discount_check check (
    (percent_off is not null and percent_off > 0 and percent_off <= 90)
    or (amount_off_cents is not null and amount_off_cents > 0)
  )
);

create index if not exists promo_codes_active_ends_idx
  on public.promo_codes (is_active, ends_at);

create table if not exists public.insider_issues (
  slug text primary key,
  subject text not null,
  preview text,
  hero_image_url text,
  web_path text,
  promo_code text references public.promo_codes (code) on update cascade,
  send_at timestamptz not null,
  status text not null default 'scheduled'
    check (status in ('draft', 'scheduled', 'sending', 'sent', 'failed')),
  sent_at timestamptz,
  send_error text,
  created_at timestamptz not null default now()
);

create index if not exists insider_issues_due_idx
  on public.insider_issues (status, send_at);

alter table public.promo_codes enable row level security;
alter table public.insider_issues enable row level security;

insert into public.promo_codes (
  code, label, percent_off, starts_at, ends_at, insider_issue_slug
) values
  ('INSIDER-SEP26', 'Insider Sep 2026', 10, '2026-09-01T00:00:00Z', '2026-09-30T23:59:59Z', '2026-09-fall-turkey'),
  ('INSIDER-OCT26', 'Insider Oct 2026', 10, '2026-10-01T00:00:00Z', '2026-10-31T23:59:59Z', '2026-10-france-uk'),
  ('INSIDER-NOV26', 'Insider Nov 2026', 10, '2026-11-01T00:00:00Z', '2026-11-30T23:59:59Z', '2026-11-winter-sun'),
  ('INSIDER-DEC26', 'Insider Dec 2026', 10, '2026-12-01T00:00:00Z', '2026-12-31T23:59:59Z', '2026-12-japan-holiday'),
  ('INSIDER-JAN27', 'Insider Jan 2027', 10, '2027-01-01T00:00:00Z', '2027-01-31T23:59:59Z', '2027-01-north-america'),
  ('INSIDER-FEB27', 'Insider Feb 2027', 10, '2027-02-01T00:00:00Z', '2027-02-28T23:59:59Z', '2027-02-umrah-prep'),
  ('INSIDER-MAR27', 'Insider Mar 2027', 10, '2027-03-01T00:00:00Z', '2027-03-31T23:59:59Z', '2027-03-europe-spring'),
  ('INSIDER-APR27', 'Insider Apr 2027', 10, '2027-04-01T00:00:00Z', '2027-04-30T23:59:59Z', '2027-04-asia-shoulder'),
  ('INSIDER-MAY27', 'Insider May 2027', 10, '2027-05-01T00:00:00Z', '2027-05-31T23:59:59Z', '2027-05-summer-planning'),
  ('INSIDER-JUN27', 'Insider Jun 2027', 10, '2027-06-01T00:00:00Z', '2027-06-30T23:59:59Z', '2027-06-peak-summer'),
  ('INSIDER-JUL27', 'Insider Jul 2027', 10, '2027-07-01T00:00:00Z', '2027-07-31T23:59:59Z', '2027-07-americas'),
  ('INSIDER-AUG27', 'Insider Aug 2027', 10, '2027-08-01T00:00:00Z', '2027-08-31T23:59:59Z', '2027-08-hajj-season')
on conflict (code) do update set
  label = excluded.label,
  percent_off = excluded.percent_off,
  starts_at = excluded.starts_at,
  ends_at = excluded.ends_at,
  insider_issue_slug = excluded.insider_issue_slug,
  is_active = true;

insert into public.insider_issues (
  slug, subject, preview, hero_image_url, web_path, promo_code, send_at, status
) values
  ('2026-09-fall-turkey', 'Fall trips, Turkey, and a calmer way to stay online', 'Destination tips, a simple eSIM habit, and early Umrah planning.', 'https://noorlink.co/images/insider/insider-2026-09-turkey.jpg', '/newsletter/2026-09-fall-turkey', 'INSIDER-SEP26', '2026-09-01T14:00:00Z', 'scheduled'),
  ('2026-10-france-uk', 'City weekends in France & the UK — pack light, stay online', 'Short-trip connectivity, regional Europe, and a light Umrah note.', 'https://noorlink.co/images/insider/insider-2026-10-france.jpg', '/newsletter/2026-10-france-uk', 'INSIDER-OCT26', '2026-10-06T14:00:00Z', 'scheduled'),
  ('2026-11-winter-sun', 'Winter-sun prep — UAE, islands, and reliable data', 'Warm-weather corridors, hotspot habits, and pre-winter Umrah tips.', 'https://noorlink.co/images/insider/insider-2026-11-uae.jpg', '/newsletter/2026-11-winter-sun', 'INSIDER-NOV26', '2026-11-03T14:00:00Z', 'scheduled'),
  ('2026-12-japan-holiday', 'Year-end trips — Japan, holidays, and data that behaves', 'Japan connectivity habits, holiday travel tips, and a quiet Makkah checklist.', 'https://noorlink.co/images/insider/insider-2026-12-japan.jpg', '/newsletter/2026-12-japan-holiday', 'INSIDER-DEC26', '2026-12-01T14:00:00Z', 'scheduled'),
  ('2027-01-north-america', 'New year trips — USA, Canada, and clear signal', 'North America plans, January travel habits, and post-holiday Umrah notes.', 'https://noorlink.co/images/insider/insider-2027-01-usa.jpg', '/newsletter/2027-01-north-america', 'INSIDER-JAN27', '2027-01-05T14:00:00Z', 'scheduled'),
  ('2027-02-umrah-prep', 'Umrah prep month — connectivity that stays in the background', 'Pilgrimage checklist, hotspot for family, and Hajj & Umrah Connect.', 'https://noorlink.co/images/insider/insider-2027-02-umrah.jpg', '/newsletter/2027-02-umrah-prep', 'INSIDER-FEB27', '2027-02-02T14:00:00Z', 'scheduled'),
  ('2027-03-europe-spring', 'Spring city breaks — Italy, Spain, and one Europe eSIM', 'Multi-country Europe tip, spring travel habits, final Umrah install reminders.', 'https://noorlink.co/images/insider/insider-2027-03-europe.jpg', '/newsletter/2027-03-europe-spring', 'INSIDER-MAR27', '2027-03-02T14:00:00Z', 'scheduled'),
  ('2027-04-asia-shoulder', 'Shoulder-season Asia — value trips and smart data', 'Thailand / Asia-Pacific tips, post-Umrah rest trips, Asia starting prices.', 'https://noorlink.co/images/insider/insider-2027-04-asia.jpg', '/newsletter/2027-04-asia-shoulder', 'INSIDER-APR27', '2027-04-06T14:00:00Z', 'scheduled'),
  ('2027-05-summer-planning', 'Summer planning — Central Europe and family hotspot', 'Germany / Central Europe, family travel tips, summer corridor prep.', 'https://noorlink.co/images/insider/insider-2027-05-germany.jpg', '/newsletter/2027-05-summer-planning', 'INSIDER-MAY27', '2027-05-04T14:00:00Z', 'scheduled'),
  ('2027-06-peak-summer', 'Peak summer in Europe — groups, hotspot, clear signal', 'Mediterranean tips, sharing data with your group, Hajj timing glance.', 'https://noorlink.co/images/insider/insider-2027-06-med.jpg', '/newsletter/2027-06-peak-summer', 'INSIDER-JUN27', '2027-06-01T14:00:00Z', 'scheduled'),
  ('2027-07-americas', 'Americas summer — Mexico, road trips, reliable hotspot', 'Mexico / Americas guide, summer data habits, light Umrah note.', 'https://noorlink.co/images/insider/insider-2027-07-mexico.jpg', '/newsletter/2027-07-americas', 'INSIDER-JUL27', '2027-07-06T14:00:00Z', 'scheduled'),
  ('2027-08-hajj-season', 'Late summer + Hajj-season connectivity, done honestly', 'Pilgrimage timing, install-before-fly, and a summer wrap.', 'https://noorlink.co/images/insider/insider-2027-08-hajj.jpg', '/newsletter/2027-08-hajj-season', 'INSIDER-AUG27', '2027-08-03T14:00:00Z', 'scheduled')
on conflict (slug) do update set
  subject = excluded.subject,
  preview = excluded.preview,
  hero_image_url = excluded.hero_image_url,
  web_path = excluded.web_path,
  promo_code = excluded.promo_code,
  send_at = excluded.send_at;
