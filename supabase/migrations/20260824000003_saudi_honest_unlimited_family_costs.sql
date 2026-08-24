-- Honest Saudi Unlimited + Family costs from live eSIM Access SA_50_30 (CKH801, $59.90).
-- Access has no true unlimited / 30GB SA SKU; 50GB/30d is the heavy fixed pack.
-- Saudi fulfillment is Access-enforced, so Citrus PAYG is not the fulfillment path.

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
  notes
)
values (
  'sa-50gb-30',
  'SA',
  'saudi-arabia',
  50,
  30,
  'esimaccess',
  'CKH801',
  'SA_50_30',
  5990,
  'eSIM Access Saudi Arabia 50GB 30Days — soft-unlimited / family heavy pack'
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
  updated_at = now();

-- Unlimited Devotion → Access 50GB (honest cost + retail above cost)
update public.mobile_data_plans
set
  name = 'Unlimited Devotion 50GB',
  data_gb = 50,
  duration_days = 30,
  wholesale_cost = 59.90,
  pricing_strategy = 'MANUAL'::public.pricing_strategy,
  override_price = 69.95,
  updated_at = now()
where country_id = 'saudi-arabia'
  and name in ('Unlimited Devotion', 'Unlimited Devotion 50GB')
  and is_active = true;

-- Family Share → Access 50GB shared pool (slightly above Unlimited for group value)
update public.mobile_data_plans
set
  name = 'Family Share 50GB',
  data_gb = 50,
  duration_days = 30,
  wholesale_cost = 59.90,
  pricing_strategy = 'MANUAL'::public.pricing_strategy,
  override_price = 74.95,
  updated_at = now()
where country_id = 'saudi-arabia'
  and name in ('Family Share 30GB', 'Family Share 50GB')
  and is_active = true;
