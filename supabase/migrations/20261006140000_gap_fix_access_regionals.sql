-- Gap fix: regionals + Aruba/Cayman/Taiwan/PR (+ legacy af/cb/me Telna keys)
-- Lebanon: NO Access/Zesimo pack and Citrus ~$29/GB — leave unmapped / coming_soon
-- Caribbean 20GB: no Access regional 20GB; Global excludes AW/KY/JM — leave coming_soon
-- Paste into Supabase SQL Editor.

insert into public.plan_fulfillment_map (
  catalog_key, country_code, country_slug, data_gb, validity_days,
  provider, provider_sku, provider_slug, wholesale_cents, notes,
  is_active, admin_approved
) values
  ('regional-africa-1gb-7', NULL, 'regional-africa', 1.0, 7, 'esimaccess', 'P62JQDSN9', 'AF-21_1_7', 368, 'Africa Access 1GB 7Days; gap-fix off Telna', true, true),
  ('regional-africa-5gb-30', NULL, 'regional-africa', 5.0, 30, 'esimaccess', 'P9XH83PKC', 'AF-21_5_30', 1636, 'Africa Access 5GB 30Days; gap-fix off Telna', true, true),
  ('regional-africa-10gb-30', NULL, 'regional-africa', 10.0, 30, 'esimaccess', 'PH39WU6ZR', 'AF-21_10_30', 2986, 'Africa Access 10GB 30Days; gap-fix off Telna', true, true),
  ('regional-africa-20gb-30', NULL, 'regional-africa', 20.0, 30, 'esimaccess', 'PY5HHXU38', 'AF-21_20_30', 6136, 'Africa Access 20GB 30Days; gap-fix off Telna', true, true),
  ('af-1gb-5', NULL, 'regional-africa', 1.0, 5, 'esimaccess', 'P62JQDSN9', 'AF-21_1_7', 368, 'covers Telna af-1gb-5 with Africa 1GB 7Days; gap-fix off Telna', true, true),
  ('af-3gb-7', NULL, 'regional-africa', 3.0, 7, 'esimaccess', 'PWNJQ374C', 'AF-21_3_15', 982, 'covers Telna af-3gb-7 with Africa 3GB 15Days; gap-fix off Telna', true, true),
  ('af-5gb-15', NULL, 'regional-africa', 5.0, 15, 'esimaccess', 'P9XH83PKC', 'AF-21_5_30', 1636, 'covers Telna af-5gb-15 with Africa 5GB 30Days; gap-fix off Telna', true, true),
  ('af-10gb-30', NULL, 'regional-africa', 10.0, 30, 'esimaccess', 'PH39WU6ZR', 'AF-21_10_30', 2986, 'Africa Access 10GB 30Days; gap-fix off Telna', true, true),
  ('regional-caribbean-1gb-7', NULL, 'regional-caribbean', 1.0, 7, 'esimaccess', 'P8N4TBFDC', 'CB_1_7', 590, 'Caribbean Access 1GB 7Days; gap-fix off Telna', true, true),
  ('regional-caribbean-5gb-30', NULL, 'regional-caribbean', 5.0, 30, 'esimaccess', 'PCFAGC825', 'CB_5_30', 2690, 'Caribbean Access 5GB 30Days; gap-fix off Telna', true, true),
  ('regional-caribbean-10gb-30', NULL, 'regional-caribbean', 10.0, 30, 'esimaccess', 'PDWMZ77EO', 'CB_10_30', 4490, 'Caribbean Access 10GB 30Days; gap-fix off Telna', true, true),
  ('cb-1gb-5', NULL, 'regional-caribbean', 1.0, 5, 'esimaccess', 'P8N4TBFDC', 'CB_1_7', 590, 'covers Telna cb-1gb-5; gap-fix off Telna', true, true),
  ('cb-3gb-7', NULL, 'regional-caribbean', 3.0, 7, 'esimaccess', 'PRHU7ZYL7', 'CB_3_30', 1490, 'covers Telna cb-3gb-7 with Caribbean 3GB 30Days; gap-fix off Telna', true, true),
  ('cb-5gb-15', NULL, 'regional-caribbean', 5.0, 15, 'esimaccess', 'PCFAGC825', 'CB_5_30', 2690, 'covers Telna cb-5gb-15; gap-fix off Telna', true, true),
  ('cb-10gb-30', NULL, 'regional-caribbean', 10.0, 30, 'esimaccess', 'PDWMZ77EO', 'CB_10_30', 4490, 'Caribbean Access 10GB 30Days; gap-fix off Telna', true, true),
  ('regional-south-america-1gb-7', NULL, 'regional-south-america', 1.0, 7, 'esimaccess', 'P0AU9B5BX', 'SA-6_1_7', 264, 'South America Access 1GB 7Days; gap-fix off Telna', true, true),
  ('la-1gb-7', NULL, 'regional-south-america', 1.0, 7, 'esimaccess', 'P0AU9B5BX', 'SA-6_1_7', 264, 'South America Access 1GB 7Days; gap-fix off Telna', true, true),
  ('regional-asia-pacific-1gb-7', NULL, 'regional-asia-pacific', 1.0, 7, 'esimaccess', 'PLF72QJG4', 'AS-14_1_7', 94, 'Asia-14 Access 1GB 7Days; gap-fix off Telna', true, true),
  ('as-1gb-7', NULL, 'regional-asia-pacific', 1.0, 7, 'esimaccess', 'PLF72QJG4', 'AS-14_1_7', 94, 'Asia-14 Access 1GB 7Days; gap-fix off Telna', true, true),
  ('regional-middle-east-5gb-30', NULL, 'regional-middle-east', 5.0, 30, 'esimaccess', 'PHS28HNA0', 'ME-5_5_30', 826, 'Middle East Access 5GB 30Days; gap-fix off Telna', true, true),
  ('regional-middle-east-20gb-30', NULL, 'regional-middle-east', 20.0, 30, 'esimaccess', 'PV5V1E2QH', 'ME-5_20_30', 3098, 'Middle East Access 20GB 30Days; gap-fix off Telna', true, true),
  ('me-5gb-30', NULL, 'regional-middle-east', 5.0, 30, 'esimaccess', 'PHS28HNA0', 'ME-5_5_30', 826, 'Middle East Access 5GB 30Days; gap-fix off Telna', true, true),
  ('me-20gb-30', NULL, 'regional-middle-east', 20.0, 30, 'esimaccess', 'PV5V1E2QH', 'ME-5_20_30', 3098, 'Middle East Access 20GB 30Days; gap-fix off Telna', true, true),
  ('me-3gb-7', NULL, 'regional-middle-east', 3.0, 7, 'esimaccess', 'PR13GBNE9', 'ME-5_3_15', 496, 'covers Telna me-3gb-7 with ME 3GB 15Days; gap-fix off Telna', true, true),
  ('regional-north-america-20gb-30', NULL, 'regional-north-america', 20.0, 30, 'zesimo', '588', 'zesimo-na-20gb-30', 2476, 'Zesimo NA 20GB 30Days; gap-fix off Telna', true, true),
  ('na-20gb-30', NULL, 'regional-north-america', 20.0, 30, 'zesimo', '588', 'zesimo-na-20gb-30', 2476, 'Zesimo NA 20GB 30Days; gap-fix off Telna', true, true),
  ('regional-global-1gb-7', NULL, 'regional-global', 1.0, 7, 'esimaccess', 'PHS30M6EZ', 'GL_1_7', 460, 'Global Access 1GB 7Days; gap-fix off Telna', true, true),
  ('regional-global-20gb-30', NULL, 'regional-global', 20.0, 30, 'esimaccess', 'PR3JZMC20', 'GL_20_30', 6000, 'Global Access 20GB 30Days; gap-fix off Telna', true, true),
  ('gl-1gb-7', NULL, 'regional-global', 1.0, 7, 'esimaccess', 'PHS30M6EZ', 'GL_1_7', 460, 'Global Access 1GB 7Days; gap-fix off Telna', true, true),
  ('gl-20gb-30', NULL, 'regional-global', 20.0, 30, 'esimaccess', 'PR3JZMC20', 'GL_20_30', 6000, 'Global Access 20GB 30Days; gap-fix off Telna', true, true),
  ('aruba-1gb-7', 'AW', 'aruba', 1.0, 7, 'esimaccess', 'P6ZPW9SU5', 'AW_1_7', 836, 'Aruba Access 1GB 7Days; gap-fix off Telna', true, true),
  ('aruba-5gb-30', 'AW', 'aruba', 5.0, 30, 'esimaccess', 'PQMJF478J', 'AW_5_30', 3715, 'Aruba Access 5GB 30Days — high wholesale; gap-fix off Telna', true, true),
  ('aruba-10gb-30', 'AW', 'aruba', 10.0, 30, 'esimaccess', 'P2ALZ6B4P', 'AW_10_30', 6779, 'Aruba Access 10GB 30Days — high wholesale; gap-fix off Telna', true, true),
  ('aruba-20gb-30', 'AW', 'aruba', 20.0, 30, 'esimaccess', 'P9LT8LCF5', 'AW_20_30', 13929, 'Aruba Access 20GB 30Days — high wholesale; gap-fix off Telna', true, true),
  ('cayman-islands-1gb-7', 'KY', 'cayman-islands', 1.0, 7, 'esimaccess', 'PK93SBDBR', 'KY_1_7', 565, 'Cayman Access 1GB 7Days; gap-fix off Telna', true, true),
  ('cayman-islands-5gb-30', 'KY', 'cayman-islands', 5.0, 30, 'esimaccess', 'P7SKZOMJ1', 'KY_5_30', 2512, 'Cayman Access 5GB 30Days; gap-fix off Telna', true, true),
  ('cayman-islands-10gb-30', 'KY', 'cayman-islands', 10.0, 30, 'esimaccess', 'PCE87XXRF', 'KY_10_30', 4584, 'Cayman Access 10GB 30Days; gap-fix off Telna', true, true),
  ('cayman-islands-20gb-30', 'KY', 'cayman-islands', 20.0, 30, 'esimaccess', 'PXR6X2UVA', 'KY_20_30', 8414, 'Cayman Access 20GB 30Days; gap-fix off Telna', true, true),
  ('taiwan-1gb-7', 'TW', 'taiwan', 1.0, 7, 'esimaccess', 'PLF72QJG4', 'AS-14_1_7', 94, 'Silent Asia-14 Access for Taiwan storefront; gap-fix off Telna', true, true),
  ('taiwan-5gb-30', 'TW', 'taiwan', 5.0, 30, 'esimaccess', 'P81GHARZ9', 'AS-14_5_30', 416, 'Silent Asia-14 Access for Taiwan storefront; gap-fix off Telna', true, true),
  ('taiwan-10gb-30', 'TW', 'taiwan', 10.0, 30, 'esimaccess', 'P7MMYE69X', 'AS-14_10_30', 759, 'Silent Asia-14 Access for Taiwan storefront; gap-fix off Telna', true, true),
  ('taiwan-20gb-30', 'TW', 'taiwan', 20.0, 30, 'esimaccess', 'PJ9W0NTK3', 'AS-14_20_30', 1560, 'Silent Asia-14 Access for Taiwan storefront; gap-fix off Telna', true, true),
  ('puerto-rico-1gb-7', 'PR', 'puerto-rico', 1.0, 7, 'esimaccess', 'CKH315', 'PR_1_7', 169, 'Puerto Rico Access 1GB 7Days; gap-fix off Telna', true, true),
  ('puerto-rico-5gb-30', 'PR', 'puerto-rico', 5.0, 30, 'esimaccess', 'CKH347', 'PR_5_30', 752, 'Puerto Rico Access 5GB 30Days; gap-fix off Telna', true, true),
  ('puerto-rico-10gb-30', 'PR', 'puerto-rico', 10.0, 30, 'esimaccess', 'PDWMZ77EO', 'CB_10_30', 4490, 'PR 10GB via Caribbean Access; gap-fix off Telna', true, true),
  ('puerto-rico-20gb-30', 'PR', 'puerto-rico', 20.0, 30, 'esimaccess', 'PY1G7FDKC', 'US_20_30', 1159, 'PR 20GB via USA Access; gap-fix off Telna', true, true),
  ('af-1gb-7', NULL, 'regional-africa', 1.0, 7, 'esimaccess', 'P62JQDSN9', 'AF-21_1_7', 368, 'Africa Access 1GB 7Days; gap-fix off Telna', true, true),
  ('af-5gb-30', NULL, 'regional-africa', 5.0, 30, 'esimaccess', 'P9XH83PKC', 'AF-21_5_30', 1636, 'Africa Access 5GB 30Days; gap-fix off Telna', true, true),
  ('af-20gb-30', NULL, 'regional-africa', 20.0, 30, 'esimaccess', 'PY5HHXU38', 'AF-21_20_30', 6136, 'Africa Access 20GB 30Days; gap-fix off Telna', true, true),
  ('cb-1gb-7', NULL, 'regional-caribbean', 1.0, 7, 'esimaccess', 'P8N4TBFDC', 'CB_1_7', 590, 'Caribbean Access 1GB 7Days; gap-fix off Telna', true, true),
  ('cb-5gb-30', NULL, 'regional-caribbean', 5.0, 30, 'esimaccess', 'PCFAGC825', 'CB_5_30', 2690, 'Caribbean Access 5GB 30Days; gap-fix off Telna', true, true)
on conflict (catalog_key) do update set
  country_code=excluded.country_code,
  country_slug=excluded.country_slug,
  data_gb=excluded.data_gb,
  validity_days=excluded.validity_days,
  provider=excluded.provider,
  provider_sku=excluded.provider_sku,
  provider_slug=excluded.provider_slug,
  wholesale_cents=excluded.wholesale_cents,
  notes=excluded.notes,
  is_active=true,
  admin_approved=true,
  updated_at=now();

-- Retire leftover Telna regional rows for Africa/Caribbean/LatAm/ME keys we replaced.
update public.plan_fulfillment_map
set is_active=false, updated_at=now()
where provider='telna'
  and is_active=true
  and (
    catalog_key in (
      'af-1gb-5','af-3gb-7','af-5gb-15','af-10gb-30',
      'cb-1gb-5','cb-3gb-7','cb-5gb-15','cb-10gb-30',
      'me-3gb-7','la-1gb-5','la-3gb-7','la-5gb-15','la-10gb-30'
    )
    or (
      country_slug in ('regional-africa','regional-caribbean')
      and provider_slug like 'telna-%'
    )
  );
