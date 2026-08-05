-- =============================================================================
-- Bootstrap / repair checkout commerce tables (users, esim_packages, orders)
-- Safe to re-run. Fixes incomplete tables (e.g. missing stripe_checkout_session_id).
-- In Supabase SQL Editor: choose "Run and enable RLS".
-- =============================================================================

create extension if not exists "pgcrypto";
create extension if not exists "citext";

do $$ begin
  create type public.order_status as enum (
    'pending', 'paid', 'delivered', 'active', 'expired', 'refunded', 'failed'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.region_slug as enum (
    'Americas', 'Europe', 'Asia', 'Middle East', 'Africa'
  );
exception when duplicate_object then null;
end $$;

create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  full_name text,
  phone text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.users add column if not exists full_name text;
alter table public.users add column if not exists phone text;
alter table public.users add column if not exists created_at timestamptz not null default now();
alter table public.users add column if not exists updated_at timestamptz not null default now();

create table if not exists public.esim_packages (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  country text not null,
  country_code char(2),
  region public.region_slug not null default 'Americas',
  flag_emoji text,
  description text,
  data_label text not null default '10GB',
  data_total_gb numeric(8, 2),
  validity_days integer not null default 15,
  price_cents integer not null check (price_cents >= 0),
  currency char(3) not null default 'USD',
  stripe_product_id text,
  stripe_price_id text,
  provider_sku text,
  network_label text,
  image_url text,
  is_active boolean not null default true,
  is_featured boolean not null default false,
  is_managed boolean not null default false,
  tier text,
  sort_order integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.esim_packages add column if not exists country_code char(2);
alter table public.esim_packages add column if not exists flag_emoji text;
alter table public.esim_packages add column if not exists description text;
alter table public.esim_packages add column if not exists data_label text not null default '10GB';
alter table public.esim_packages add column if not exists data_total_gb numeric(8, 2);
alter table public.esim_packages add column if not exists validity_days integer not null default 15;
alter table public.esim_packages add column if not exists price_cents integer;
alter table public.esim_packages add column if not exists currency char(3) not null default 'USD';
alter table public.esim_packages add column if not exists stripe_product_id text;
alter table public.esim_packages add column if not exists stripe_price_id text;
alter table public.esim_packages add column if not exists provider_sku text;
alter table public.esim_packages add column if not exists network_label text;
alter table public.esim_packages add column if not exists image_url text;
alter table public.esim_packages add column if not exists is_active boolean not null default true;
alter table public.esim_packages add column if not exists is_featured boolean not null default false;
alter table public.esim_packages add column if not exists is_managed boolean not null default false;
alter table public.esim_packages add column if not exists tier text;
alter table public.esim_packages add column if not exists sort_order integer not null default 0;
alter table public.esim_packages add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.esim_packages add column if not exists created_at timestamptz not null default now();
alter table public.esim_packages add column if not exists updated_at timestamptz not null default now();

create index if not exists esim_packages_country_idx on public.esim_packages (country);
create index if not exists esim_packages_active_idx on public.esim_packages (is_active) where is_active = true;

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  order_number text not null unique,
  user_id uuid references public.users (id) on delete set null,
  package_id uuid references public.esim_packages (id) on delete set null,
  email citext not null,
  country text not null,
  flag_emoji text,
  package_name text not null,
  amount_cents integer not null check (amount_cents >= 0),
  currency char(3) not null default 'USD',
  status public.order_status not null default 'pending',
  travel_date date,
  stripe_checkout_session_id text,
  stripe_payment_intent_id text,
  stripe_customer_id text,
  qr_code_url text,
  activation_code text,
  data_used_gb numeric(8, 2) default 0,
  data_total_gb numeric(8, 2),
  paid_at timestamptz,
  fulfilled_at timestamptz,
  refunded_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Repair existing orders table (common cause of the 42703 error)
alter table public.orders add column if not exists user_id uuid references public.users (id) on delete set null;
alter table public.orders add column if not exists package_id uuid references public.esim_packages (id) on delete set null;
alter table public.orders add column if not exists flag_emoji text;
alter table public.orders add column if not exists package_name text;
alter table public.orders add column if not exists amount_cents integer;
alter table public.orders add column if not exists currency char(3) not null default 'USD';
alter table public.orders add column if not exists status public.order_status not null default 'pending';
alter table public.orders add column if not exists travel_date date;
alter table public.orders add column if not exists stripe_checkout_session_id text;
alter table public.orders add column if not exists stripe_payment_intent_id text;
alter table public.orders add column if not exists stripe_customer_id text;
alter table public.orders add column if not exists qr_code_url text;
alter table public.orders add column if not exists activation_code text;
alter table public.orders add column if not exists data_used_gb numeric(8, 2) default 0;
alter table public.orders add column if not exists data_total_gb numeric(8, 2);
alter table public.orders add column if not exists paid_at timestamptz;
alter table public.orders add column if not exists fulfilled_at timestamptz;
alter table public.orders add column if not exists refunded_at timestamptz;
alter table public.orders add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.orders add column if not exists created_at timestamptz not null default now();
alter table public.orders add column if not exists updated_at timestamptz not null default now();

do $$ begin
  alter table public.orders add constraint orders_stripe_checkout_session_id_key unique (stripe_checkout_session_id);
exception when duplicate_object then null;
when others then null;
end $$;

do $$ begin
  alter table public.orders add constraint orders_stripe_payment_intent_id_key unique (stripe_payment_intent_id);
exception when duplicate_object then null;
when others then null;
end $$;

create index if not exists orders_email_idx on public.orders (email);
create index if not exists orders_status_idx on public.orders (status);
create index if not exists orders_stripe_session_idx on public.orders (stripe_checkout_session_id);

-- Sample USA package so checkout can resolve a catalog SKU
insert into public.esim_packages (
  slug, name, country, country_code, region, flag_emoji,
  data_label, data_total_gb, validity_days, price_cents, currency,
  is_active, is_managed, tier, sort_order
)
select
  'usa-3gb-7d', 'Starter 3GB', 'USA', 'US', 'Americas', '🇺🇸',
  '3GB', 3, 7, 895, 'USD',
  true, false, 'regional', 10
where not exists (
  select 1 from public.esim_packages where slug = 'usa-3gb-7d'
);
