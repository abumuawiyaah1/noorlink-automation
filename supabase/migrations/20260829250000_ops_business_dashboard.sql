-- Ops event log, email delivery tracking, GDPR request log

create table if not exists public.ops_event_log (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  source text not null,
  severity text not null default 'info',
  order_number text,
  message text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ops_event_log_created_at_idx
  on public.ops_event_log (created_at desc);

create index if not exists ops_event_log_order_number_idx
  on public.ops_event_log (order_number)
  where order_number is not null;

create index if not exists ops_event_log_event_type_idx
  on public.ops_event_log (event_type);

create table if not exists public.email_delivery_events (
  id uuid primary key default gen_random_uuid(),
  message_id text,
  email_type text,
  recipient text,
  event_type text not null default 'sent',
  subject text,
  insider_slug text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists email_delivery_events_created_at_idx
  on public.email_delivery_events (created_at desc);

create index if not exists email_delivery_events_type_idx
  on public.email_delivery_events (email_type);

create table if not exists public.gdpr_requests (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  request_type text not null check (request_type in ('export', 'delete')),
  status text not null default 'completed',
  admin_username text,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists gdpr_requests_email_idx on public.gdpr_requests (email);
