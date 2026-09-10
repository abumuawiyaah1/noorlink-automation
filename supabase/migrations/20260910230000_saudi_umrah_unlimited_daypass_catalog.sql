-- Restore Saudi Umrah Unlimited day-pass catalog (3GB/day high-speed, then ~1 Mbps).
-- Fulfillment: Zesimo 7d/10d. Browse catalog was missing these rows, so planGroups.unlimited stayed empty.

alter table public.plan_fulfillment_map
  drop constraint if exists plan_fulfillment_map_provider_check;

alter table public.plan_fulfillment_map
  add constraint plan_fulfillment_map_provider_check
  check (provider in ('citrus', 'esimaccess', 'mock', 'simbase', 'telna', 'zesimo', 'weconnect'));

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
  notes,
  is_active,
  admin_approved
)
values
  (
    'sa-unlimited-3gb-7d',
    'SA',
    'saudi-arabia',
    3.0,
    7,
    'zesimo',
    '10903',
    'zesimo-sa-unlimited-7d',
    2142,
    'Zesimo Saudi Arabia Unlimited 7 Days — 3GB/day then throttle',
    true,
    true
  ),
  (
    'sa-unlimited-3gb-10d',
    'SA',
    'saudi-arabia',
    3.0,
    10,
    'zesimo',
    '10905',
    'zesimo-sa-unlimited-10d',
    2786,
    'Zesimo Saudi Arabia Unlimited 10 Days — 3GB/day then throttle',
    true,
    true
  )
on conflict (catalog_key) do update set
  provider = excluded.provider,
  provider_sku = excluded.provider_sku,
  provider_slug = excluded.provider_slug,
  wholesale_cents = excluded.wholesale_cents,
  country_code = excluded.country_code,
  country_slug = excluded.country_slug,
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
    'Umrah Unlimited 7 Days',
    3::numeric,
    7,
    21.42,
    'MANUAL',
    'UNLIMITED',
    false,
    true,
    35,
    'middle-east',
    34.99
  ),
  (
    'saudi-arabia',
    'Umrah Unlimited 10 Days',
    3::numeric,
    10,
    27.86,
    'MANUAL',
    'UNLIMITED',
    true,
    true,
    36,
    'middle-east',
    42.99
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

-- If rows already exist (inactive / wrong category), bring them back on sale.
update public.mobile_data_plans
set
  data_gb = 3,
  duration_days = case name
    when 'Umrah Unlimited 7 Days' then 7
    when 'Umrah Unlimited 10 Days' then 10
    else duration_days
  end,
  wholesale_cost = case name
    when 'Umrah Unlimited 7 Days' then 21.42
    when 'Umrah Unlimited 10 Days' then 27.86
    else wholesale_cost
  end,
  override_price = case name
    when 'Umrah Unlimited 7 Days' then 34.99
    when 'Umrah Unlimited 10 Days' then 42.99
    else override_price
  end,
  pricing_strategy = 'MANUAL'::public.pricing_strategy,
  plan_category = 'UNLIMITED'::public.plan_category,
  is_active = true,
  is_featured = (name = 'Umrah Unlimited 10 Days'),
  sort_order = case name
    when 'Umrah Unlimited 7 Days' then 35
    when 'Umrah Unlimited 10 Days' then 36
    else sort_order
  end,
  region_id = coalesce(region_id, 'middle-east'),
  updated_at = now()
where country_id = 'saudi-arabia'
  and name in ('Umrah Unlimited 7 Days', 'Umrah Unlimited 10 Days');
