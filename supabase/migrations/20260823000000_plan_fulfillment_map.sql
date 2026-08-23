-- Virtual catalog → provider fulfillment map (Citrus | eSIM Access | mock)
-- Phase A: route Saudi fixed packs to eSIM Access; other destinations keep default provider.

create table if not exists public.plan_fulfillment_map (
  id uuid primary key default gen_random_uuid(),
  catalog_key text not null unique,
  package_id uuid references public.esim_packages (id) on delete set null,
  country_code char(2),
  country_slug text,
  data_gb numeric(8, 2),
  validity_days integer,
  provider text not null check (provider in ('citrus', 'esimaccess', 'mock', 'simbase')),
  provider_sku text not null,
  provider_slug text,
  wholesale_cents integer,
  period_num integer,
  is_active boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists plan_fulfillment_map_package_id_idx
  on public.plan_fulfillment_map (package_id)
  where package_id is not null and is_active;

create index if not exists plan_fulfillment_map_country_data_idx
  on public.plan_fulfillment_map (country_code, data_gb, validity_days)
  where is_active;

comment on table public.plan_fulfillment_map is
  'Maps NoorLink sellable plans to upstream provider SKUs (virtual catalog).';
comment on column public.plan_fulfillment_map.catalog_key is
  'Stable NoorLink plan key, e.g. sa-5gb-30.';
comment on column public.plan_fulfillment_map.provider_sku is
  'Upstream package code / PlanId (e.g. eSIM Access CKH279).';
comment on column public.plan_fulfillment_map.provider_slug is
  'Optional upstream slug alias (e.g. SA_5_30).';
comment on column public.plan_fulfillment_map.wholesale_cents is
  'Expected wholesale cost in USD cents for margin checks.';
comment on column public.plan_fulfillment_map.period_num is
  'Day-pass length for Access daily/FUP plans; null for fixed packs.';

-- Seed Saudi Arabia fixed packs → eSIM Access (Aug 2026 Standard list)
insert into public.plan_fulfillment_map (
  catalog_key,
  country_code,
  country_slug,
  data_gb,
  validity_days,
  provider,
  provider_sku,
  provider_slug,
  wholesale_cents,
  notes
)
values
  (
    'sa-5gb-30',
    'SA',
    'saudi-arabia',
    5,
    30,
    'esimaccess',
    'CKH279',
    'SA_5_30',
    722,
    'eSIM Access Saudi Arabia 5GB 30Days'
  ),
  (
    'sa-10gb-30',
    'SA',
    'saudi-arabia',
    10,
    30,
    'esimaccess',
    'CKH280',
    'SA_10_30',
    1150,
    'eSIM Access Saudi Arabia 10GB 30Days'
  ),
  (
    'sa-20gb-30',
    'SA',
    'saudi-arabia',
    20,
    30,
    'esimaccess',
    'CKH800',
    'SA_20_30',
    1950,
    'eSIM Access Saudi Arabia 20GB 30Days'
  )
on conflict (catalog_key) do update set
  provider = excluded.provider,
  provider_sku = excluded.provider_sku,
  provider_slug = excluded.provider_slug,
  wholesale_cents = excluded.wholesale_cents,
  country_code = excluded.country_code,
  country_slug = excluded.country_slug,
  data_gb = excluded.data_gb,
  validity_days = excluded.validity_days,
  notes = excluded.notes,
  is_active = true,
  updated_at = now();
