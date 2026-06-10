-- Reference schema for the existing Supabase table "Mobile Data Plans".
-- PostgreSQL identifier: public.mobile_data_plans
-- Skip if your project already has this table configured in the dashboard.

create table if not exists public.mobile_data_plans (
  id uuid primary key default gen_random_uuid(),
  country_id text not null,
  name text not null,
  data_gb numeric(8, 2),
  duration_days integer,
  price numeric(10, 2),
  price_cents integer,
  currency char(3) not null default 'USD',
  rechargeable boolean not null default false,
  is_active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists mobile_data_plans_country_id_idx
  on public.mobile_data_plans (country_id);

alter table public.mobile_data_plans enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'mobile_data_plans'
      and policyname = 'mobile_data_plans_public_read'
  ) then
    create policy "mobile_data_plans_public_read"
      on public.mobile_data_plans for select
      using (is_active = true);
  end if;
end $$;
