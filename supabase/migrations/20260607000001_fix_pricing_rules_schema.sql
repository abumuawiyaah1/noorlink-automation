-- Fix partial schema + seed catalog (run in Supabase SQL Editor if API returns 503)

do $$ begin
  create type public.pricing_rule_scope as enum ('COUNTRY', 'REGION', 'GLOBAL');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.price_suffix_rule as enum ('STANDARD', 'ROUND_TO_77', 'ROUND_TO_95');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.pricing_strategy as enum ('MANUAL', 'AUTOMATED');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.plan_category as enum ('FIXED', 'UNLIMITED', 'FLEXIBLE');
exception when duplicate_object then null;
end $$;

alter table public.pricing_rules
  add column if not exists scope public.pricing_rule_scope not null default 'GLOBAL',
  add column if not exists target_id text,
  add column if not exists price_suffix_rule public.price_suffix_rule not null default 'STANDARD';

alter table public.mobile_data_plans
  add column if not exists pricing_strategy public.pricing_strategy not null default 'MANUAL',
  add column if not exists override_price numeric(10, 2),
  add column if not exists wholesale_cost numeric(10, 2),
  add column if not exists pricing_rule_name text,
  add column if not exists plan_category public.plan_category not null default 'FIXED',
  add column if not exists is_featured boolean not null default false,
  add column if not exists region_id text;

insert into public.pricing_rules (
  rule_name, scope, target_id, multiplier, fixed_buffer, min_margin_amount,
  price_suffix_rule, is_active
) values
  ('global_standard', 'GLOBAL', null, 1.3500, 2.00, 3.00, 'ROUND_TO_95', true),
  ('premium_destination', 'REGION', 'middle-east', 1.5500, 4.00, 5.00, 'ROUND_TO_77', true),
  ('turkey_country_premium', 'COUNTRY', 'turkey', 1.4500, 3.00, 4.00, 'ROUND_TO_95', true)
on conflict (rule_name) do update set
  scope = excluded.scope,
  target_id = excluded.target_id,
  multiplier = excluded.multiplier,
  fixed_buffer = excluded.fixed_buffer,
  min_margin_amount = excluded.min_margin_amount,
  price_suffix_rule = excluded.price_suffix_rule,
  is_active = excluded.is_active;

insert into public.mobile_data_plans (
  country_id, name, data_gb, duration_days, wholesale_cost, pricing_strategy,
  plan_category, is_featured, is_active, sort_order, region_id
)
select v.country_id, v.name, v.data_gb, v.duration_days, v.wholesale_cost,
       v.pricing_strategy::public.pricing_strategy, v.plan_category::public.plan_category,
       v.is_featured, v.is_active, v.sort_order, v.region_id
from (values
  ('usa', 'Starter 3GB', 3::numeric, 7, 4.50, 'AUTOMATED', 'FIXED', false, true, 10, 'americas'),
  ('usa', 'Traveler 10GB', 10::numeric, 15, 5.50, 'AUTOMATED', 'FIXED', true, true, 20, 'americas'),
  ('usa', 'Unlimited 21 Days', null::numeric, 21, 12.00, 'AUTOMATED', 'UNLIMITED', false, true, 30, 'americas'),
  ('usa', 'Flex Pay-As-You-Go', null::numeric, null::integer, 2.99, 'AUTOMATED', 'FLEXIBLE', false, true, 40, 'americas'),
  ('france', 'Traveler 10GB', 10::numeric, 15, 5.50, 'AUTOMATED', 'FIXED', true, true, 10, 'europe'),
  ('saudi-arabia', 'Lite Explorer 5GB', 5::numeric, 10, 6.00, 'AUTOMATED', 'FIXED', false, true, 10, 'middle-east'),
  ('saudi-arabia', 'Connected Pilgrim 15GB', 15::numeric, 15, 8.00, 'AUTOMATED', 'FIXED', true, true, 20, 'middle-east'),
  ('saudi-arabia', 'Unlimited Devotion', null::numeric, 21, 14.00, 'AUTOMATED', 'UNLIMITED', false, true, 30, 'middle-east'),
  ('saudi-arabia', 'Family Share 30GB', 30::numeric, 21, 18.00, 'AUTOMATED', 'FLEXIBLE', false, true, 40, 'middle-east'),
  ('turkey', 'Traveler 10GB', 10::numeric, 15, 5.00, 'AUTOMATED', 'FIXED', true, true, 10, 'middle-east'),
  ('japan', 'Traveler 10GB', 10::numeric, 15, 6.50, 'AUTOMATED', 'FIXED', true, true, 10, 'asia')
) as v(country_id, name, data_gb, duration_days, wholesale_cost, pricing_strategy,
       plan_category, is_featured, is_active, sort_order, region_id)
where not exists (
  select 1 from public.mobile_data_plans existing
  where existing.country_id = v.country_id and existing.name = v.name
);
