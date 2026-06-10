-- Hybrid pricing architecture: pricing_rules + mobile_data_plans strategy columns.

create type public.pricing_strategy as enum ('MANUAL', 'AUTOMATED');

create type public.plan_category as enum ('FIXED', 'UNLIMITED', 'FLEXIBLE');

create table if not exists public.pricing_rules (
  id uuid primary key default gen_random_uuid(),
  rule_name text not null unique,
  multiplier numeric(10, 4) not null default 1.0000
    check (multiplier > 0),
  fixed_buffer numeric(10, 2) not null default 0.00
    check (fixed_buffer >= 0),
  min_margin_amount numeric(10, 2) not null default 3.00
    check (min_margin_amount >= 0),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.pricing_rules is
  'Automated retail pricing coefficients. Referenced by mobile_data_plans.pricing_rule_name.';

comment on column public.pricing_rules.min_margin_amount is
  'Minimum USD margin above wholesale_cost (margin floor).';

create index if not exists pricing_rules_active_idx
  on public.pricing_rules (is_active)
  where is_active = true;

alter table public.mobile_data_plans
  add column if not exists pricing_strategy public.pricing_strategy not null default 'MANUAL',
  add column if not exists override_price numeric(10, 2)
    check (override_price is null or override_price >= 0),
  add column if not exists wholesale_cost numeric(10, 2)
    check (wholesale_cost is null or wholesale_cost >= 0),
  add column if not exists pricing_rule_name text
    references public.pricing_rules (rule_name) on update cascade,
  add column if not exists plan_category public.plan_category not null default 'FIXED',
  add column if not exists is_featured boolean not null default false;

create index if not exists mobile_data_plans_pricing_rule_idx
  on public.mobile_data_plans (pricing_rule_name);

alter table public.pricing_rules enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'pricing_rules'
      and policyname = 'pricing_rules_public_read'
  ) then
    create policy "pricing_rules_public_read"
      on public.pricing_rules for select
      using (is_active = true);
  end if;
end $$;

create trigger pricing_rules_set_updated_at
  before update on public.pricing_rules
  for each row execute function public.set_updated_at();
