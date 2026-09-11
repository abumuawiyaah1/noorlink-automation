-- Zesimo China single-country ladder (asia-pacific storefront 5/10/20 + 1GB/7d).

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
  ('china-1gb-7', 'CN', 'china', 1.0, 7, 'zesimo', '1766', 'zesimo-china-1gb-7', 98, 'Zesimo phase 5: China 1GB 7 Days', true, true),
  ('china-5gb-30', 'CN', 'china', 5.0, 30, 'zesimo', '1768', 'zesimo-china-5gb-30', 414, 'Zesimo phase 5: China 5GB 30 Days', true, true),
  ('china-10gb-30', 'CN', 'china', 10.0, 30, 'zesimo', '1769', 'zesimo-china-10gb-30', 819, 'Zesimo phase 5: China 10GB 30 Days', true, true),
  ('china-20gb-30', 'CN', 'china', 20.0, 30, 'zesimo', '1998', 'zesimo-china-20gb-30', 1435, 'Zesimo phase 5: China 20GB 30 Days', true, true)
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
