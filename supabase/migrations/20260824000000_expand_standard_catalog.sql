-- Expand single-country catalog to a consistent 5-plan lineup.
-- Safe to re-run: inserts only when (country_id, name) does not exist.
--
-- Standard lineup (Citrus / automated pricing):
--   Starter 3GB · 7 days
--   Traveler 10GB · 15 days (featured)
--   Heavy 20GB · 30 days
--   Unlimited 21 Days
--   Flex Pay-As-You-Go
--
-- Saudi Arabia: keep existing pilgrimage-named catalog; do not replace here.

insert into public.mobile_data_plans (
  country_id, name, data_gb, duration_days, wholesale_cost, pricing_strategy,
  plan_category, is_featured, is_active, sort_order, region_id
)
select v.country_id, v.name, v.data_gb, v.duration_days, v.wholesale_cost,
       v.pricing_strategy::public.pricing_strategy, v.plan_category::public.plan_category,
       v.is_featured, v.is_active, v.sort_order, v.region_id
from (values
  -- USA (already has 4; add Heavy)
  ('usa', 'Heavy 20GB', 20::numeric, 30, 9.50, 'AUTOMATED', 'FIXED', false, true, 25, 'americas'),

  -- France
  ('france', 'Starter 3GB', 3::numeric, 7, 3.40, 'AUTOMATED', 'FIXED', false, true, 10, 'europe'),
  ('france', 'Traveler 10GB', 10::numeric, 15, 7.20, 'AUTOMATED', 'FIXED', true, true, 20, 'europe'),
  ('france', 'Heavy 20GB', 20::numeric, 30, 12.60, 'AUTOMATED', 'FIXED', false, true, 30, 'europe'),
  ('france', 'Unlimited 21 Days', null::numeric, 21, 14.00, 'AUTOMATED', 'UNLIMITED', false, true, 40, 'europe'),
  ('france', 'Flex Pay-As-You-Go', null::numeric, null::integer, 2.99, 'AUTOMATED', 'FLEXIBLE', false, true, 50, 'europe'),

  -- Turkey
  ('turkey', 'Starter 3GB', 3::numeric, 7, 3.70, 'AUTOMATED', 'FIXED', false, true, 10, 'middle-east'),
  ('turkey', 'Traveler 10GB', 10::numeric, 15, 8.20, 'AUTOMATED', 'FIXED', true, true, 20, 'middle-east'),
  ('turkey', 'Heavy 20GB', 20::numeric, 30, 14.50, 'AUTOMATED', 'FIXED', false, true, 30, 'middle-east'),
  ('turkey', 'Unlimited 21 Days', null::numeric, 21, 16.00, 'AUTOMATED', 'UNLIMITED', false, true, 40, 'middle-east'),
  ('turkey', 'Flex Pay-As-You-Go', null::numeric, null::integer, 2.99, 'AUTOMATED', 'FLEXIBLE', false, true, 50, 'middle-east'),

  -- Japan
  ('japan', 'Starter 3GB', 3::numeric, 7, 5.90, 'AUTOMATED', 'FIXED', false, true, 10, 'asia'),
  ('japan', 'Traveler 10GB', 10::numeric, 15, 15.60, 'AUTOMATED', 'FIXED', true, true, 20, 'asia'),
  ('japan', 'Heavy 20GB', 20::numeric, 30, 29.40, 'AUTOMATED', 'FIXED', false, true, 30, 'asia'),
  ('japan', 'Unlimited 21 Days', null::numeric, 21, 32.00, 'AUTOMATED', 'UNLIMITED', false, true, 40, 'asia'),
  ('japan', 'Flex Pay-As-You-Go', null::numeric, null::integer, 2.99, 'AUTOMATED', 'FLEXIBLE', false, true, 50, 'asia')
) as v(country_id, name, data_gb, duration_days, wholesale_cost, pricing_strategy,
       plan_category, is_featured, is_active, sort_order, region_id)
where not exists (
  select 1 from public.mobile_data_plans existing
  where existing.country_id = v.country_id and existing.name = v.name
);
