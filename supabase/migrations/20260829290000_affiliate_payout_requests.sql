-- Affiliate payout requests (partner self-serve) + 72h auto-approve queue

create table if not exists public.affiliate_payout_requests (
  id uuid primary key default gen_random_uuid(),
  affiliate_id uuid not null references public.affiliates (id) on delete restrict,
  affiliate_code text not null,
  requested_by_email text not null,
  payout_email text,
  amount_cents integer not null check (amount_cents > 0),
  status text not null default 'pending'
    check (status in ('pending', 'approved_auto', 'paid', 'cancelled', 'rejected')),
  attended_at timestamptz,
  attended_by text,
  auto_approved_at timestamptz,
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists affiliate_payout_requests_status_created_idx
  on public.affiliate_payout_requests (status, created_at);

create index if not exists affiliate_payout_requests_affiliate_idx
  on public.affiliate_payout_requests (affiliate_id, status);

alter table public.affiliate_payout_requests enable row level security;

comment on table public.affiliate_payout_requests is
  'Partner payout requests. After 72h unanswered + strict rules → approved_auto (still requires sending funds).';
