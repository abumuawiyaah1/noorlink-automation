-- Ghana single-country ladder → eSIM Access (sale-safe wholesale).
-- Replaces Telna Africa regional cascade for Ghana storefront packs.
-- Access SKUs (2026-10-06): MB025 / MB035 / MB040 / MB057.

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
    'ghana-1gb-7',
    'GH',
    'ghana',
    1.0,
    7,
    'esimaccess',
    'MB025',
    'GH_1_7',
    175,
    'eSIM Access: Ghana 1GB 7Days — remap off Telna Africa cascade',
    true,
    true
  ),
  (
    'ghana-5gb-30',
    'GH',
    'ghana',
    5.0,
    30,
    'esimaccess',
    'MB035',
    'GH_5_30',
    778,
    'eSIM Access: Ghana 5GB 30Days — remap off Telna Africa cascade',
    true,
    true
  ),
  (
    'ghana-10gb-30',
    'GH',
    'ghana',
    10.0,
    30,
    'esimaccess',
    'MB040',
    'GH_10_30',
    1557,
    'eSIM Access: Ghana 10GB 30Days — remap off Telna Africa cascade',
    true,
    true
  ),
  (
    'ghana-20gb-30',
    'GH',
    'ghana',
    20.0,
    30,
    'esimaccess',
    'MB057',
    'GH_20_30',
    2916,
    'eSIM Access: Ghana 20GB 30Days — remap off Telna Africa cascade',
    true,
    true
  )
on conflict (catalog_key) do update set
  country_code = excluded.country_code,
  country_slug = excluded.country_slug,
  data_gb = excluded.data_gb,
  validity_days = excluded.validity_days,
  provider = excluded.provider,
  provider_sku = excluded.provider_sku,
  provider_slug = excluded.provider_slug,
  wholesale_cents = excluded.wholesale_cents,
  notes = excluded.notes,
  is_active = true,
  admin_approved = true,
  period_num = null,
  updated_at = now();
