-- Destination-scoped plan catalog for the dynamic /plans storefront page.
-- Distinct from esim_packages (checkout SKUs); esim_plans powers plan browsing UI.

create table if not exists public.esim_plans (
  id uuid primary key default gen_random_uuid(),
  destination_slug text not null,
  destination_name text not null,
  flag_emoji text,
  plan_name text not null,
  data_label text not null,
  data_total_gb numeric(8, 2),
  duration_days integer,
  price_cents integer not null check (price_cents >= 0),
  currency char(3) not null default 'USD',
  is_pay_as_you_go boolean not null default false,
  is_active boolean not null default true,
  sort_order integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists esim_plans_destination_slug_idx
  on public.esim_plans (destination_slug);

create index if not exists esim_plans_active_idx
  on public.esim_plans (is_active)
  where is_active = true;

comment on table public.esim_plans is
  'Browsable plan tiers per destination for the Next.js /plans page.';

alter table public.esim_plans enable row level security;

create policy "esim_plans_public_read"
  on public.esim_plans for select
  using (is_active = true);

create trigger esim_plans_set_updated_at
  before update on public.esim_plans
  for each row execute function public.set_updated_at();
