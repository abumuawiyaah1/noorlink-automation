-- NoorLink affiliate / referral program (influencer, mosque, connector, customer)

create table if not exists public.affiliates (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  type text not null check (type in ('influencer', 'mosque', 'connector', 'customer')),
  display_name text,
  organization_name text,
  contact_email text,
  payout_email text,
  referrer_email text,
  status text not null default 'active'
    check (status in ('pending', 'active', 'paused')),
  customer_discount_percent integer,
  commission_percent integer,
  payout_minimum_cents integer,
  landing_path text default '/destinations',
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint affiliates_customer_discount_check check (
    customer_discount_percent is null
    or (customer_discount_percent >= 0 and customer_discount_percent <= 50)
  ),
  constraint affiliates_commission_check check (
    commission_percent is null
    or (commission_percent >= 0 and commission_percent <= 50)
  )
);

create index if not exists affiliates_type_status_idx
  on public.affiliates (type, status);

create index if not exists affiliates_referrer_email_idx
  on public.affiliates (referrer_email)
  where referrer_email is not null;

create table if not exists public.affiliate_commissions (
  id uuid primary key default gen_random_uuid(),
  affiliate_id uuid not null references public.affiliates (id) on delete restrict,
  order_id uuid not null unique references public.orders (id) on delete restrict,
  order_number text not null,
  order_amount_cents integer not null check (order_amount_cents > 0),
  commission_percent integer not null check (commission_percent >= 0),
  commission_cents integer not null check (commission_cents >= 0),
  status text not null default 'approved'
    check (status in ('pending', 'approved', 'paid', 'clawed_back')),
  payout_id uuid,
  fulfilled_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists affiliate_commissions_affiliate_status_idx
  on public.affiliate_commissions (affiliate_id, status);

create table if not exists public.affiliate_payouts (
  id uuid primary key default gen_random_uuid(),
  affiliate_id uuid not null references public.affiliates (id) on delete restrict,
  amount_cents integer not null check (amount_cents > 0),
  method text default 'manual',
  reference text,
  notes text,
  paid_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

alter table public.affiliate_commissions
  add constraint affiliate_commissions_payout_fk
  foreign key (payout_id) references public.affiliate_payouts (id)
  on delete set null;

create table if not exists public.affiliate_referral_rewards (
  id uuid primary key default gen_random_uuid(),
  affiliate_id uuid not null references public.affiliates (id) on delete restrict,
  recipient_email text not null,
  triggered_by_order_id uuid not null unique references public.orders (id) on delete restrict,
  reward_promo_code text not null references public.promo_codes (code) on update cascade,
  status text not null default 'issued'
    check (status in ('issued', 'redeemed', 'expired')),
  created_at timestamptz not null default now()
);

create index if not exists affiliate_referral_rewards_affiliate_idx
  on public.affiliate_referral_rewards (affiliate_id, created_at desc);

alter table public.affiliates enable row level security;
alter table public.affiliate_commissions enable row level security;
alter table public.affiliate_payouts enable row level security;
alter table public.affiliate_referral_rewards enable row level security;
