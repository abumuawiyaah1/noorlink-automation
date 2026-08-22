-- Support / contact form table (missing on production if initial migration wasn't fully applied)
-- Safe to re-run.

create table if not exists public.support_tickets (
  id uuid primary key default gen_random_uuid(),
  ticket_number text not null unique,
  name text not null,
  email citext not null,
  subject text,
  message text not null,
  status text not null default 'open',
  created_at timestamptz not null default now()
);

create index if not exists support_tickets_email_idx
  on public.support_tickets (email);

create index if not exists support_tickets_created_at_idx
  on public.support_tickets (created_at desc);

alter table public.support_tickets enable row level security;

-- Service role (Railway) bypasses RLS; no public anon policies needed for inserts via API.

comment on table public.support_tickets is
  'Website /support contact form submissions.';

-- Newsletter table often missing alongside support
create table if not exists public.newsletter_subscribers (
  id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  dream_destination text,
  source text default 'website',
  subscribed_at timestamptz not null default now(),
  unsubscribed_at timestamptz
);

alter table public.newsletter_subscribers enable row level security;
