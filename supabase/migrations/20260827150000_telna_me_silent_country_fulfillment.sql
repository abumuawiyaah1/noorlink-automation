-- Silent Telna Middle East fulfillment for Gulf / Turkey / Egypt-style country pages.
-- Storefront stays country-branded (e.g. "UAE 10GB"); wholesale uses Telna ME Bundle.
-- Saudi / Umrah is intentionally excluded (Access remains cheaper + policy).

insert into public.plan_fulfillment_map (
  catalog_key, country_code, country_slug, data_gb, validity_days,
  provider, provider_sku, provider_slug, wholesale_cents, notes, is_active
)
values
  -- UAE
  ('uae-1gb-5', null, 'uae', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for UAE storefront', true),
  ('uae-3gb-7', null, 'uae', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for UAE storefront', true),
  ('uae-5gb-15', null, 'uae', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for UAE storefront', true),
  ('uae-10gb-30', null, 'uae', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for UAE storefront', true),
  -- Turkey
  ('turkey-1gb-5', null, 'turkey', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Turkey storefront', true),
  ('turkey-3gb-7', null, 'turkey', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Turkey storefront', true),
  ('turkey-5gb-15', null, 'turkey', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Turkey storefront', true),
  ('turkey-10gb-30', null, 'turkey', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Turkey storefront', true),
  -- Egypt
  ('egypt-1gb-5', null, 'egypt', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Egypt storefront', true),
  ('egypt-3gb-7', null, 'egypt', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Egypt storefront', true),
  ('egypt-5gb-15', null, 'egypt', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Egypt storefront', true),
  ('egypt-10gb-30', null, 'egypt', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Egypt storefront', true),
  -- Qatar
  ('qatar-1gb-5', null, 'qatar', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Qatar storefront', true),
  ('qatar-3gb-7', null, 'qatar', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Qatar storefront', true),
  ('qatar-5gb-15', null, 'qatar', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Qatar storefront', true),
  ('qatar-10gb-30', null, 'qatar', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Qatar storefront', true),
  -- Kuwait
  ('kuwait-1gb-5', null, 'kuwait', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Kuwait storefront', true),
  ('kuwait-3gb-7', null, 'kuwait', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Kuwait storefront', true),
  ('kuwait-5gb-15', null, 'kuwait', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Kuwait storefront', true),
  ('kuwait-10gb-30', null, 'kuwait', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Kuwait storefront', true),
  -- Bahrain
  ('bahrain-1gb-5', null, 'bahrain', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Bahrain storefront', true),
  ('bahrain-3gb-7', null, 'bahrain', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Bahrain storefront', true),
  ('bahrain-5gb-15', null, 'bahrain', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Bahrain storefront', true),
  ('bahrain-10gb-30', null, 'bahrain', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Bahrain storefront', true),
  -- Oman
  ('oman-1gb-5', null, 'oman', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Oman storefront', true),
  ('oman-3gb-7', null, 'oman', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Oman storefront', true),
  ('oman-5gb-15', null, 'oman', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Oman storefront', true),
  ('oman-10gb-30', null, 'oman', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Oman storefront', true),
  -- Jordan
  ('jordan-1gb-5', null, 'jordan', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Jordan storefront', true),
  ('jordan-3gb-7', null, 'jordan', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Jordan storefront', true),
  ('jordan-5gb-15', null, 'jordan', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Jordan storefront', true),
  ('jordan-10gb-30', null, 'jordan', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Jordan storefront', true),
  -- Israel
  ('israel-1gb-5', null, 'israel', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Israel storefront', true),
  ('israel-3gb-7', null, 'israel', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Israel storefront', true),
  ('israel-5gb-15', null, 'israel', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Israel storefront', true),
  ('israel-10gb-30', null, 'israel', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Israel storefront', true),
  -- Morocco
  ('morocco-1gb-5', null, 'morocco', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Morocco storefront', true),
  ('morocco-3gb-7', null, 'morocco', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Morocco storefront', true),
  ('morocco-5gb-15', null, 'morocco', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Morocco storefront', true),
  ('morocco-10gb-30', null, 'morocco', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Morocco storefront', true),
  -- Tunisia
  ('tunisia-1gb-5', null, 'tunisia', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Tunisia storefront', true),
  ('tunisia-3gb-7', null, 'tunisia', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Tunisia storefront', true),
  ('tunisia-5gb-15', null, 'tunisia', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Tunisia storefront', true),
  ('tunisia-10gb-30', null, 'tunisia', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Tunisia storefront', true),
  -- Cyprus
  ('cyprus-1gb-5', null, 'cyprus', 1, 5, 'telna', '67f6c112d07af55d502bef7a', 'telna-me-1gb-5d', 370, 'Silent Telna ME Bundle for Cyprus storefront', true),
  ('cyprus-3gb-7', null, 'cyprus', 3, 7, 'telna', '67f6c112d07af55d502bef79', 'telna-me-3gb-7d', 1000, 'Silent Telna ME Bundle for Cyprus storefront', true),
  ('cyprus-5gb-15', null, 'cyprus', 5, 15, 'telna', '67f6c112d07af55d502bef7b', 'telna-me-5gb-15d', 1620, 'Silent Telna ME Bundle for Cyprus storefront', true),
  ('cyprus-10gb-30', null, 'cyprus', 10, 30, 'telna', '67f6c112d07af55d502bef78', 'telna-me-10gb-30d', 2800, 'Silent Telna ME Bundle for Cyprus storefront', true)
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
