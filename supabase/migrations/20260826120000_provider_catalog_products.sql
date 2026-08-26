-- Provider fulfillment warehouse (synced catalog). Not the public sellable shop.
-- Used to match our 4-plan ladder to country → region → global SKUs at checkout.

create table if not exists public.provider_catalog_products (
  id uuid primary key default gen_random_uuid(),
  provider text not null check (provider in ('citrus', 'esimaccess', 'telna', 'simbase', 'mock')),
  provider_sku text not null,
  name text not null default '',
  scope text not null check (scope in ('country', 'regional', 'global')),
  country_slugs text[] not null default '{}',
  data_gb numeric(8, 2),
  validity_days integer,
  wholesale_cents integer,
  currency text not null default 'USD',
  is_active boolean not null default true,
  raw jsonb,
  synced_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, provider_sku)
);

create index if not exists provider_catalog_scope_data_idx
  on public.provider_catalog_products (scope, data_gb, validity_days)
  where is_active;

create index if not exists provider_catalog_country_slugs_idx
  on public.provider_catalog_products using gin (country_slugs)
  where is_active;

comment on table public.provider_catalog_products is
  'Cached upstream provider SKUs for silent fulfillment matching. Not listed on the storefront.';
