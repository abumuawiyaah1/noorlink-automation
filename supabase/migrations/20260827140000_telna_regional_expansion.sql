-- Expand Telna Connect Flex fulfillment across regional + gap-fill country ladders.
-- Verified against live catalog 2026-08-27 (ppo-api.telna.com).

insert into public.plan_fulfillment_map (
  catalog_key, country_code, country_slug, data_gb, validity_days,
  provider, provider_sku, provider_slug, wholesale_cents, notes, is_active
)
values
  -- Europe Bundle
  ('eu-1gb-5', null, 'regional-europe', 1, 5, 'telna', '66b5db0b899f794eccc7fee7', 'telna-europe-1gb-5d', 150, 'Telna Europe Bundle 1GB 5Days', true),
  ('eu-3gb-7', null, 'regional-europe', 3, 7, 'telna', '66b5db0b899f794eccc7fefc', 'telna-europe-3gb-7d', 325, 'Telna Europe Bundle 3GB 7Days', true),
  ('eu-5gb-15', null, 'regional-europe', 5, 15, 'telna', '66b5db0b899f794eccc7fedf', 'telna-europe-5gb-15d', 500, 'Telna Europe Bundle 5GB 15Days', true),
  ('eu-10gb-30', null, 'regional-europe', 10, 30, 'telna', '66b5db0b899f794eccc7fed8', 'telna-europe-10gb-30d', 900, 'Telna Europe Bundle 10GB 30Days', true),
  -- Asia Bundle 2
  ('as-1gb-5', null, 'regional-asia-pacific', 1, 5, 'telna', '690b2b5f7aff111b7539f7c2', 'telna-asia2-1gb-5d', 275, 'Telna Asia Bundle 2 1GB 5Days', true),
  ('as-3gb-7', null, 'regional-asia-pacific', 3, 7, 'telna', '690b2b5f7aff111b7539f7c1', 'telna-asia2-3gb-7d', 725, 'Telna Asia Bundle 2 3GB 7Days', true),
  ('as-5gb-15', null, 'regional-asia-pacific', 5, 15, 'telna', '690b2b5e7aff111b7539f7c0', 'telna-asia2-5gb-15d', 1175, 'Telna Asia Bundle 2 5GB 15Days', true),
  ('as-10gb-30', null, 'regional-asia-pacific', 10, 30, 'telna', '690b2b5e7aff111b7539f7bf', 'telna-asia2-10gb-30d', 2125, 'Telna Asia Bundle 2 10GB 30Days', true),
  -- Middle East Bundle
  ('me-1gb-5', null, 'regional-middle-east', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Telna Middle East Bundle 1GB 5Days', true),
  ('me-3gb-7', null, 'regional-middle-east', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Telna Middle East Bundle 3GB 7Days', true),
  ('me-5gb-15', null, 'regional-middle-east', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Telna Middle East Bundle 5GB 15Days', true),
  ('me-10gb-30', null, 'regional-middle-east', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Telna Middle East Bundle 10GB 30Days', true),
  -- Africa Bundle
  ('af-1gb-5', null, 'regional-africa', 1, 5, 'telna', '690b2b5f7aff111b7539f7c9', 'telna-africa-1gb-5d', 675, 'Telna Africa Bundle 1GB 5Days', true),
  ('af-3gb-7', null, 'regional-africa', 3, 7, 'telna', '690b2b5f7aff111b7539f7cd', 'telna-africa-3gb-7d', 1825, 'Telna Africa Bundle 3GB 7Days', true),
  ('af-5gb-15', null, 'regional-africa', 5, 15, 'telna', '690b2b5f7aff111b7539f7d6', 'telna-africa-5gb-15d', 3025, 'Telna Africa Bundle 5GB 15Days', true),
  ('af-10gb-30', null, 'regional-africa', 10, 30, 'telna', '690b2b5f7aff111b7539f7d8', 'telna-africa-10gb-30d', 5525, 'Telna Africa Bundle 10GB 30Days', true),
  -- North America Bundle (USA + Canada)
  ('na-1gb-5', null, 'regional-north-america', 1, 5, 'telna', '66b5db0b899f794eccc7fff2', 'telna-na-1gb-5d', 250, 'Telna North America Bundle 1GB 5Days', true),
  ('na-3gb-7', null, 'regional-north-america', 3, 7, 'telna', '66b5db0b899f794eccc80043', 'telna-na-3gb-7d', 660, 'Telna North America Bundle 3GB 7Days', true),
  ('na-5gb-15', null, 'regional-north-america', 5, 15, 'telna', '66b5db0b899f794eccc7fffa', 'telna-na-5gb-15d', 1000, 'Telna North America Bundle 5GB 15Days', true),
  ('na-10gb-30', null, 'regional-north-america', 10, 30, 'telna', '66b5db0b899f794eccc80016', 'telna-na-10gb-30d', 1800, 'Telna North America Bundle 10GB 30Days', true),
  -- Global Bundle
  ('gl-1gb-5', null, 'regional-global', 1, 5, 'telna', '690b2b5f7aff111b7539f7d7', 'telna-global-1gb-5d', 775, 'Telna Global Bundle 1GB 5Days', true),
  ('gl-3gb-7', null, 'regional-global', 3, 7, 'telna', '690b2b5f7aff111b7539f7d2', 'telna-global-3gb-7d', 2150, 'Telna Global Bundle 3GB 7Days', true),
  ('gl-5gb-15', null, 'regional-global', 5, 15, 'telna', '690b2b5f7aff111b7539f7c6', 'telna-global-5gb-15d', 3500, 'Telna Global Bundle 5GB 15Days', true),
  ('gl-10gb-30', null, 'regional-global', 10, 30, 'telna', '690b2b5f7aff111b7539f7cc', 'telna-global-10gb-30d', 6000, 'Telna Global Bundle 10GB 30Days', true),
  -- Gap-fill: Australia (not in Asia Bundle 2)
  ('au-1gb-5', null, 'australia', 1, 5, 'telna', '66b5db0b899f794eccc7fe26', 'telna-australia-1gb-5d', 150, 'Telna Australia 1GB 5Days', true),
  ('au-3gb-7', null, 'australia', 3, 7, 'telna', '66b5db0b899f794eccc7fe3d', 'telna-australia-3gb-7d', 400, 'Telna Australia 3GB 7Days', true),
  ('au-5gb-15', null, 'australia', 5, 15, 'telna', '66b5db0b899f794eccc7fe54', 'telna-australia-5gb-15d', 600, 'Telna Australia 5GB 15Days', true),
  ('au-10gb-30', null, 'australia', 10, 30, 'telna', '66b5db0b899f794eccc7fe25', 'telna-australia-10gb-30d', 1100, 'Telna Australia 10GB 30Days', true),
  -- Gap-fill: Mexico (not in North America Bundle)
  ('mx-1gb-5', null, 'mexico', 1, 5, 'telna', '66b5db0b899f794eccc7ffaa', 'telna-mexico-1gb-5d', 300, 'Telna Mexico 1GB 5Days', true),
  ('mx-3gb-7', null, 'mexico', 3, 7, 'telna', '66b5db0b899f794eccc7ffcc', 'telna-mexico-3gb-7d', 750, 'Telna Mexico 3GB 7Days', true),
  ('mx-5gb-15', null, 'mexico', 5, 15, 'telna', '66b5db0b899f794eccc7fff5', 'telna-mexico-5gb-15d', 1100, 'Telna Mexico 5GB 15Days', true),
  ('mx-10gb-30', null, 'mexico', 10, 30, 'telna', '66b5db0b899f794eccc7ffb4', 'telna-mexico-10gb-30d', 2000, 'Telna Mexico 10GB 30Days', true)
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

-- Retire prior Access regional keys superseded by Telna ladders.
update public.plan_fulfillment_map
set is_active = false,
    updated_at = now()
where provider = 'esimaccess'
  and catalog_key in (
    'eu-1gb-7', 'eu-10gb-30', 'eu-20gb-30',
    'as20-1gb-7', 'as20-10gb-30', 'as20-20gb-30',
    'me-1gb-7', 'me-3gb-15', 'me-10gb-30',
    'af-1gb-7', 'af-5gb-30',
    'na-1gb-7', 'na-10gb-30', 'na-20gb-30',
    'gl-1gb-7', 'gl-10gb-30', 'gl-20gb-30'
  );
