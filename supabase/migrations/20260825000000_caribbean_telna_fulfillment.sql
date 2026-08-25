-- Seed Telna Connect Flex fulfillment for Caribbean regional catalog keys.
-- provider_sku = Telna product ObjectId from the portal price list.

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
values
  ('cb-1gb-5', null, 'regional-caribbean', 1, 5, 'telna', '690b2b5f7aff111b7539f7c4', 'telna-caribbean-1gb-5d', 650, 'Telna Caribbean Bundle 1GB 5Days'),
  ('cb-3gb-7', null, 'regional-caribbean', 3, 7, 'telna', '690b2b5e7aff111b7539f7bd', 'telna-caribbean-3gb-7d', 1600, 'Telna Caribbean Bundle 3GB 7Days'),
  ('cb-5gb-15', null, 'regional-caribbean', 5, 15, 'telna', '690b2b5e7aff111b7539f7be', 'telna-caribbean-5gb-15d', 2300, 'Telna Caribbean Bundle 5GB 15Days'),
  ('cb-10gb-30', null, 'regional-caribbean', 10, 30, 'telna', '690b2b5f7aff111b7539f7c3', 'telna-caribbean-10gb-30d', 4000, 'Telna Caribbean Bundle 10GB 30Days')
on conflict (catalog_key) do update set
  provider = excluded.provider,
  provider_sku = excluded.provider_sku,
  provider_slug = excluded.provider_slug,
  wholesale_cents = excluded.wholesale_cents,
  country_slug = excluded.country_slug,
  data_gb = excluded.data_gb,
  validity_days = excluded.validity_days,
  notes = excluded.notes,
  is_active = true,
  updated_at = now();

-- Retire earlier Access CB-25 mapping if those keys were seeded.
update public.plan_fulfillment_map
set is_active = false,
    updated_at = now()
where catalog_key in ('cb-1gb-7', 'cb-3gb-30', 'cb-5gb-30', 'cb-10gb-30')
  and provider = 'esimaccess';
