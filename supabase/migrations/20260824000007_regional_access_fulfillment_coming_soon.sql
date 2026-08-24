-- Seed Access fulfillment for Access-backed regional catalog keys.

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
  ('eu-1gb-7', null, 'regional-europe', 1, 7, 'esimaccess', 'CKH484', 'EU-42_1_7', 290, 'Europe Access EU-42 1GB 7Days'),
  ('eu-10gb-30', null, 'regional-europe', 10, 30, 'esimaccess', 'CKH486', 'EU-42_10_30', 1900, 'Europe Access EU-42 10GB 30Days'),
  ('eu-20gb-30', null, 'regional-europe', 20, 30, 'esimaccess', 'CKH500', 'EU-42_20_30', 3200, 'Europe Access EU-42 20GB 30Days'),
  ('as20-1gb-7', null, 'regional-asia-pacific', 1, 7, 'esimaccess', 'JC183', 'AS-20_1_7', 360, 'Asia-20 Access 1GB 7Days'),
  ('as20-10gb-30', null, 'regional-asia-pacific', 10, 30, 'esimaccess', 'JC180', 'AS-20_10_30', 2300, 'Asia-20 Access 10GB 30Days'),
  ('as20-20gb-30', null, 'regional-asia-pacific', 20, 30, 'esimaccess', 'PALTQIBLC', 'AS-20_20_30', 4000, 'Asia-20 Access 20GB 30Days'),
  ('me-1gb-7', null, 'regional-middle-east', 1, 7, 'esimaccess', 'PSFQ1VKKN', 'ME-12_1_7', 700, 'MENA Access 1GB 7Days'),
  ('me-3gb-15', null, 'regional-middle-east', 3, 15, 'esimaccess', 'PU9MJXGXW', 'ME-12_3_15', 1750, 'MENA Access 3GB 15Days'),
  ('me-10gb-30', null, 'regional-middle-east', 10, 30, 'esimaccess', 'P12PP39U9', 'ME-12_10_30', 5500, 'MENA Access 10GB 30Days — replaces fake Unlimited $59.99'),
  ('af-1gb-7', null, 'regional-africa', 1, 7, 'esimaccess', 'CKH495', 'AF-29_1_7', 570, 'Africa Access 1GB 7Days'),
  ('af-5gb-30', null, 'regional-africa', 5, 30, 'esimaccess', 'CKH497', 'AF-29_5_30', 2100, 'Africa Access 5GB 30Days'),
  ('na-1gb-7', null, 'regional-north-america', 1, 7, 'esimaccess', 'CKH491', 'NA-3_1_7', 198, 'NA Access 1GB 7Days'),
  ('na-10gb-30', null, 'regional-north-america', 10, 30, 'esimaccess', 'CKH494', 'NA-3_10_30', 1520, 'NA Access 10GB 30Days'),
  ('na-20gb-30', null, 'regional-north-america', 20, 30, 'esimaccess', 'CKH535', 'NA-3_20_30', 2550, 'NA Access 20GB 30Days'),
  ('gl-1gb-7', null, 'regional-global', 1, 7, 'esimaccess', 'PHS30M6EZ', 'GL-120_1_7', 460, 'Global Access 1GB 7Days'),
  ('gl-10gb-30', null, 'regional-global', 10, 30, 'esimaccess', 'P34FHRF8J', 'GL-120_10_30', 3400, 'Global Access 10GB 30Days'),
  ('gl-20gb-30', null, 'regional-global', 20, 30, 'esimaccess', 'PR3JZMC20', 'GL-120_20_30', 6000, 'Global Access 20GB 30Days')
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

-- Pause fictional Unlimited / Flex single-country rows until Access-mapped.
update public.mobile_data_plans
set is_active = false,
    updated_at = now()
where is_active = true
  and country_id in ('usa', 'france', 'turkey', 'japan')
  and (
    plan_category = 'UNLIMITED'
    or plan_category = 'FLEXIBLE'
    or name ilike '%unlimited%'
    or name ilike '%pay-as-you-go%'
    or name ilike '%flex%'
  );
