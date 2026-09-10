-- Temporary test: Saudi Umrah Unlimited 1 Day (Access SA_3_Daily_1Mbps, period_num=1).
-- 3GB high-speed then ~1 Mbps for a single day. Remove or deactivate after testing.

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
  period_num,
  notes,
  is_active,
  admin_approved
)
values (
  'sa-unlimited-3gb-1d',
  'SA',
  'saudi-arabia',
  3.0,
  1,
  'esimaccess',
  'PVEXXS543',
  'SA_3_Daily_1Mbps',
  486,
  1,
  'TEST: Access Saudi 3GB/Day FUP 1 day',
  true,
  true
)
on conflict (catalog_key) do update set
  provider = excluded.provider,
  provider_sku = excluded.provider_sku,
  provider_slug = excluded.provider_slug,
  wholesale_cents = excluded.wholesale_cents,
  period_num = excluded.period_num,
  data_gb = excluded.data_gb,
  validity_days = excluded.validity_days,
  notes = excluded.notes,
  is_active = true,
  admin_approved = true,
  updated_at = now();

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
  region_id,
  override_price
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
  v.region_id,
  v.override_price
from (values
  (
    'saudi-arabia',
    'Umrah Unlimited 1 Day',
    3::numeric,
    1,
    4.86,
    'MANUAL',
    'UNLIMITED',
    false,
    true,
    34,
    'middle-east',
    9.99
  )
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
  region_id,
  override_price
)
where not exists (
  select 1
  from public.mobile_data_plans existing
  where existing.country_id = v.country_id
    and existing.name = v.name
);

update public.mobile_data_plans
set
  data_gb = 3,
  duration_days = 1,
  wholesale_cost = 4.86,
  override_price = 9.99,
  pricing_strategy = 'MANUAL'::public.pricing_strategy,
  plan_category = 'UNLIMITED'::public.plan_category,
  is_active = true,
  is_featured = false,
  sort_order = 34,
  region_id = coalesce(region_id, 'middle-east'),
  updated_at = now()
where country_id = 'saudi-arabia'
  and name = 'Umrah Unlimited 1 Day';
