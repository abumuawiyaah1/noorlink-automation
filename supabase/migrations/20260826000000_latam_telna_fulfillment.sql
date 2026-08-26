-- Seed Telna Connect Flex fulfillment for Latin America / South America regional catalog.
-- provider_sku = Telna Latin America Bundle product ObjectIds (17-country ladder).

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
  ('la-1gb-5', null, 'regional-south-america', 1, 5, 'telna', '67f6c112d07af55d502bef74', 'telna-latam-1gb-5d', 330, 'Telna Latin America Bundle 1GB 5Days'),
  ('la-3gb-7', null, 'regional-south-america', 3, 7, 'telna', '67f6c112d07af55d502bef76', 'telna-latam-3gb-7d', 850, 'Telna Latin America Bundle 3GB 7Days'),
  ('la-5gb-15', null, 'regional-south-america', 5, 15, 'telna', '67f6c112d07af55d502bef77', 'telna-latam-5gb-15d', 1400, 'Telna Latin America Bundle 5GB 15Days'),
  ('la-10gb-30', null, 'regional-south-america', 10, 30, 'telna', '67f6c112d07af55d502bef75', 'telna-latam-10gb-30d', 2500, 'Telna Latin America Bundle 10GB 30Days')
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
