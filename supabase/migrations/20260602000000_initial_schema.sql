-- NoorLink initial schema (Supabase / PostgreSQL)
-- Run in Supabase SQL Editor or via: supabase db push
-- Maps to: src/api/schemas.py, src/api/store.py, types/api.ts

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists "pgcrypto";
create extension if not exists "citext";

-- ---------------------------------------------------------------------------
-- Enums (aligned with OrderStatus in FastAPI / TypeScript)
-- ---------------------------------------------------------------------------
create type public.order_status as enum (
  'pending',
  'paid',
  'delivered',
  'active',
  'expired',
  'refunded',
  'failed'
);

create type public.region_slug as enum (
  'Americas',
  'Europe',
  'Asia',
  'Middle East',
  'Africa'
);

-- ---------------------------------------------------------------------------
-- users / profiles
-- Guest checkout uses email on orders; registered users link via auth.users.
-- ---------------------------------------------------------------------------
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email citext not null,
  full_name text,
  phone text,
  stripe_customer_id text unique,
  default_country text,
  marketing_opt_in boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_email_unique unique (email)
);

comment on table public.profiles is
  'App profile per Supabase Auth user. Service role creates/updates; users read own row via RLS.';

-- Optional: lightweight user record for pre-auth / CRM (no auth.users yet)
create table public.users (
  id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  full_name text,
  stripe_customer_id text unique,
  supabase_auth_id uuid unique references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.users is
  'Email-keyed customer identity for guest checkout + later account linking.';

-- ---------------------------------------------------------------------------
-- esim_packages — sellable catalog (country/region SKUs)
-- Replaces hard-coded destination cards + esim-database.js tiers.
-- ---------------------------------------------------------------------------
create table public.esim_packages (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  country text not null,
  country_code char(2),
  region public.region_slug not null,
  flag_emoji text,
  description text,
  data_label text not null default '10GB',
  data_total_gb numeric(8, 2),
  validity_days integer not null default 15,
  price_cents integer not null check (price_cents >= 0),
  currency char(3) not null default 'USD',
  stripe_product_id text,
  stripe_price_id text unique,
  provider_sku text,
  network_label text,
  image_url text,
  is_active boolean not null default true,
  is_featured boolean not null default false,
  sort_order integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index esim_packages_region_idx on public.esim_packages (region);
create index esim_packages_country_idx on public.esim_packages (country);
create index esim_packages_active_idx on public.esim_packages (is_active) where is_active = true;

comment on table public.esim_packages is
  'Canonical eSIM product catalog. Checkout references package_id + snapshots price on order.';

-- ---------------------------------------------------------------------------
-- orders — purchases & fulfillment (replaces in-memory store)
-- ---------------------------------------------------------------------------
create table public.orders (
  id uuid primary key default gen_random_uuid(),
  order_number text not null unique,
  user_id uuid references public.users (id) on delete set null,
  profile_id uuid references public.profiles (id) on delete set null,
  package_id uuid references public.esim_packages (id) on delete set null,
  email citext not null,
  country text not null,
  flag_emoji text,
  package_name text not null,
  amount_cents integer not null check (amount_cents >= 0),
  currency char(3) not null default 'USD',
  status public.order_status not null default 'pending',
  travel_date date,
  stripe_checkout_session_id text unique,
  stripe_payment_intent_id text unique,
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
  updated_at timestamptz not null default now(),
  constraint orders_lookup_email_order_number unique (order_number, email)
);

create index orders_email_idx on public.orders (email);
create index orders_status_idx on public.orders (status);
create index orders_stripe_session_idx on public.orders (stripe_checkout_session_id);
create index orders_created_at_idx on public.orders (created_at desc);

comment on table public.orders is
  'One row per checkout. Guest lookup: order_number + email (dashboard).';

-- ---------------------------------------------------------------------------
-- Supporting tables (newsletter + support — currently in-memory on API)
-- ---------------------------------------------------------------------------
create table public.newsletter_subscribers (
  id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  dream_destination text,
  source text default 'website',
  subscribed_at timestamptz not null default now(),
  unsubscribed_at timestamptz
);

create table public.support_tickets (
  id uuid primary key default gen_random_uuid(),
  ticket_number text not null unique,
  name text not null,
  email citext not null,
  subject text,
  message text not null,
  status text not null default 'open',
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

create trigger users_set_updated_at
  before update on public.users
  for each row execute function public.set_updated_at();

create trigger esim_packages_set_updated_at
  before update on public.esim_packages
  for each row execute function public.set_updated_at();

create trigger orders_set_updated_at
  before update on public.orders
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- order_number generator (NL-XXXXXXXX)
-- ---------------------------------------------------------------------------
create or replace function public.generate_order_number()
returns text
language plpgsql
as $$
declare
  suffix text;
begin
  suffix := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8));
  return 'NL-' || suffix;
end;
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security (baseline — tighten per environment)
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.users enable row level security;
alter table public.esim_packages enable row level security;
alter table public.orders enable row level security;
alter table public.newsletter_subscribers enable row level security;
alter table public.support_tickets enable row level security;

-- Public read catalog
create policy "esim_packages_public_read"
  on public.esim_packages for select
  using (is_active = true);

-- Profiles: owner read/update
create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id);

-- Orders: no direct client access; FastAPI uses service_role key
-- (Optional) allow select when order_number+email verified via Edge Function later

-- Service role bypasses RLS — use SUPABASE_SERVICE_KEY only on backend.
