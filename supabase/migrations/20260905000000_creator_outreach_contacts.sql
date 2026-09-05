-- Creator outreach contacts for admin marketing dashboard
-- Staff CRM: handles, emails, DM/email copy, promo codes, send status

create table if not exists public.creator_outreach_contacts (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  handle text not null default '',
  email text not null default '',
  platform text not null default 'instagram'
    check (platform in ('instagram', 'tiktok', 'youtube', 'email', 'other')),
  profile_url text not null default '',
  content_url text not null default '',
  wave text not null default 'search'
    check (wave in ('1', '2', '3', 'search')),
  status text not null default 'to_contact'
    check (status in ('to_contact', 'messaged', 'replied', 'gifted', 'posted', 'closed')),
  message_sent text not null default '',
  promo_code text not null default '',
  notes text not null default '',
  contacted_at date,
  replied_at date,
  last_email_at timestamptz,
  last_email_subject text not null default '',
  created_by text not null default '',
  updated_by text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists creator_outreach_contacts_status_idx
  on public.creator_outreach_contacts (status);

create index if not exists creator_outreach_contacts_updated_at_idx
  on public.creator_outreach_contacts (updated_at desc);

create index if not exists creator_outreach_contacts_email_idx
  on public.creator_outreach_contacts (email)
  where email <> '';

alter table public.creator_outreach_contacts enable row level security;

comment on table public.creator_outreach_contacts is
  'Marketing creator outreach CRM — handles, emails, templates, and send log.';
