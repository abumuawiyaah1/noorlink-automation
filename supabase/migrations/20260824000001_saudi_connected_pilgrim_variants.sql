-- Connected Pilgrim: replace 15GB/15d with Access-aligned 10GB/30d and 20GB/30d options.

update public.mobile_data_plans
set is_active = false,
    updated_at = now()
where country_id = 'saudi-arabia'
  and name = 'Connected Pilgrim 15GB';

insert into public.mobile_data_plans (
  country_id,
  name,
  data_gb,
  duration_days,
  wholesale_cost,
  pricing_strategy,
  plan_category,
  is_featured,
  is_active,
  sort_order,
  region_id
)
select
  v.country_id,
  v.name,
  v.data_gb,
  v.duration_days,
  v.wholesale_cost,
  v.pricing_strategy::public.pricing_strategy,
  v.plan_category::public.plan_category,
  v.is_featured,
  v.is_active,
  v.sort_order,
  v.region_id
from (values
  ('saudi-arabia', 'Connected Pilgrim 10GB', 10::numeric, 30, 11.50, 'AUTOMATED', 'FIXED', true, true, 20, 'middle-east'),
  ('saudi-arabia', 'Connected Pilgrim 20GB', 20::numeric, 30, 19.50, 'AUTOMATED', 'FIXED', false, true, 25, 'middle-east')
) as v(
  country_id,
  name,
  data_gb,
  duration_days,
  wholesale_cost,
  pricing_strategy,
  plan_category,
  is_featured,
  is_active,
  sort_order,
  region_id
)
where not exists (
  select 1
  from public.mobile_data_plans existing
  where existing.country_id = v.country_id
    and existing.name = v.name
);

-- Align Lite Explorer with Access 5GB/30d wholesale for fulfillment matching.
update public.mobile_data_plans
set duration_days = 30,
    wholesale_cost = 7.22,
    updated_at = now()
where country_id = 'saudi-arabia'
  and name = 'Lite Explorer 5GB'
  and (duration_days is distinct from 30 or wholesale_cost is distinct from 7.22);
