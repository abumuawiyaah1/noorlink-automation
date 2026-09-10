-- Saudi Umrah Unlimited day-pass lengths: 3d + 5d (Access SA_3_Daily_1Mbps).
-- Lets travelers pick trip length alongside existing 1/7/10 day options.

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
values
  (
    'sa-unlimited-3gb-3d',
    'SA',
    'saudi-arabia',
    3.0,
    3,
    'esimaccess',
    'PVEXXS543',
    'SA_3_Daily_1Mbps',
    1458,
    3,
    'Access Saudi 3GB/Day FUP 3 days',
    true,
    true
  ),
  (
    'sa-unlimited-3gb-5d',
    'SA',
    'saudi-arabia',
    3.0,
    5,
    'esimaccess',
    'PVEXXS543',
    'SA_3_Daily_1Mbps',
    2430,
    5,
    'Access Saudi 3GB/Day FUP 5 days',
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
    'Umrah Unlimited 3 Days',
    3::numeric,
    3,
    14.58,
    'MANUAL',
    'UNLIMITED',
    false,
    true,
    34,
    'middle-east',
    24.99
  ),
  (
    'saudi-arabia',
    'Umrah Unlimited 5 Days',
    3::numeric,
    5,
    24.30,
    'MANUAL',
    'UNLIMITED',
    false,
    true,
    35,
    'middle-east',
    29.99
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
  duration_days = case name
    when 'Umrah Unlimited 3 Days' then 3
    when 'Umrah Unlimited 5 Days' then 5
    else duration_days
  end,
  wholesale_cost = case name
    when 'Umrah Unlimited 3 Days' then 14.58
    when 'Umrah Unlimited 5 Days' then 24.30
    else wholesale_cost
  end,
  override_price = case name
    when 'Umrah Unlimited 3 Days' then 24.99
    when 'Umrah Unlimited 5 Days' then 29.99
    else override_price
  end,
  pricing_strategy = 'MANUAL'::public.pricing_strategy,
  plan_category = 'UNLIMITED'::public.plan_category,
  is_active = true,
  is_featured = false,
  sort_order = case name
    when 'Umrah Unlimited 3 Days' then 34
    when 'Umrah Unlimited 5 Days' then 35
    else sort_order
  end,
  region_id = coalesce(region_id, 'middle-east'),
  updated_at = now()
where country_id = 'saudi-arabia'
  and name in ('Umrah Unlimited 3 Days', 'Umrah Unlimited 5 Days');

-- Keep 1d before 3d/5d in sort order.
update public.mobile_data_plans
set sort_order = 33, updated_at = now()
where country_id = 'saudi-arabia'
  and name = 'Umrah Unlimited 1 Day';

update public.mobile_data_plans
set sort_order = 36, updated_at = now()
where country_id = 'saudi-arabia'
  and name = 'Umrah Unlimited 7 Days';

update public.mobile_data_plans
set sort_order = 37, updated_at = now()
where country_id = 'saudi-arabia'
  and name = 'Umrah Unlimited 10 Days';
