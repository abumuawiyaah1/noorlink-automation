-- Virtual bundle allowance ledger for WeConnect breakage-fulfillment.
-- Tracks sold allowance vs actual usage; unused MB at expiry = breakage profit.
-- Safe to re-run (IF NOT EXISTS / DO blocks).

do $$ begin
  create type public.breakage_allowance_status as enum (
    'pending',
    'active',
    'exhausted',
    'expired',
    'suspended',
    'cancelled'
  );
exception when duplicate_object then null;
end $$;

create table if not exists public.breakage_allowances (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders (id) on delete cascade,
  order_number text not null,
  country_slug text not null,
  plan_key text,
  fulfillment_mode text not null default 'virtual_bundle'
    check (fulfillment_mode in ('virtual_bundle', 'payg_topup')),
  provider text not null default 'weconnect'
    check (provider in ('weconnect', 'citrus', 'mock')),
  provider_profile_id text,
  allowance_mb integer not null check (allowance_mb > 0),
  used_mb integer not null default 0 check (used_mb >= 0),
  wholesale_cost_usd numeric(12, 4) not null default 0 check (wholesale_cost_usd >= 0),
  retail_usd numeric(10, 2) not null check (retail_usd >= 0),
  valid_from timestamptz not null default now(),
  valid_until timestamptz not null,
  status public.breakage_allowance_status not null default 'pending',
  last_synced_at timestamptz,
  suspended_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint breakage_allowances_used_lte_allowance check (used_mb <= allowance_mb + 512)
);

create unique index if not exists breakage_allowances_order_id_unique_idx
  on public.breakage_allowances (order_id);

create index if not exists breakage_allowances_order_number_idx
  on public.breakage_allowances (order_number);

create index if not exists breakage_allowances_status_valid_until_idx
  on public.breakage_allowances (status, valid_until)
  where status in ('pending', 'active');

create index if not exists breakage_allowances_provider_profile_idx
  on public.breakage_allowances (provider, provider_profile_id)
  where provider_profile_id is not null;

comment on table public.breakage_allowances is
  'NoorLink virtual bundle ledger: sold GB cap + expiry enforced on WeConnect PAYG rails.';

comment on column public.breakage_allowances.allowance_mb is
  'Retail allowance sold to customer (hard cap).';
comment on column public.breakage_allowances.used_mb is
  'Provider-reported consumption; updated by sync job.';
comment on column public.breakage_allowances.wholesale_cost_usd is
  'Running WeConnect per-MB cost for this order.';
comment on column public.breakage_allowances.valid_until is
  'When unused allowance expires (breakage revenue after this timestamp).';

-- Usage sync audit trail (optional granularity for finance / disputes)
create table if not exists public.breakage_usage_events (
  id uuid primary key default gen_random_uuid(),
  allowance_id uuid not null references public.breakage_allowances (id) on delete cascade,
  order_number text not null,
  used_mb integer not null check (used_mb >= 0),
  wholesale_cost_usd numeric(12, 4) not null default 0,
  source text not null default 'provider_sync',
  recorded_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists breakage_usage_events_allowance_id_idx
  on public.breakage_usage_events (allowance_id, recorded_at desc);

alter table public.breakage_allowances enable row level security;
alter table public.breakage_usage_events enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_trigger where tgname = 'breakage_allowances_set_updated_at'
  ) then
    create trigger breakage_allowances_set_updated_at
      before update on public.breakage_allowances
      for each row execute function public.set_updated_at();
  end if;
exception when undefined_function then
  null;
end $$;
