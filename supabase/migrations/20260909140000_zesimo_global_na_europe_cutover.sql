-- Zesimo Phase 4: Global 193 + NA mid rungs + Europe 10/20 on 41-country ladder.
-- Source: ZSM-CAT-20260909-2053 full catalogue (NoorLink account).

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
  ('gl-1gb-5', null, 'regional-global', 1.0, 5, 'zesimo', '11818', 'zesimo-global-1gb-5d', 350, 'Zesimo phase 4: Global 1GB 5 Days (193 countries)', true, true),
  ('gl-3gb-30', null, 'regional-global', 3.0, 30, 'zesimo', '11804', 'zesimo-global-3gb-30d', 938, 'Zesimo phase 4: Global 3GB 30 Days (193 countries)', true, true),
  ('gl-5gb-30', null, 'regional-global', 5.0, 30, 'zesimo', '11806', 'zesimo-global-5gb-30d', 1470, 'Zesimo phase 4: Global 5GB 30 Days (193 countries)', true, true),
  ('gl-10gb-30', null, 'regional-global', 10.0, 30, 'zesimo', '11808', 'zesimo-global-10gb-30d', 2520, 'Zesimo phase 4: Global 10GB 30 Days (193 countries)', true, true),
  ('na-3gb-30', null, 'regional-north-america', 3.0, 30, 'zesimo', '2290', 'zesimo-na-3gb-30d', 785, 'Zesimo phase 4: North America 3GB 30 Days (CA/MX/US)', true, true),
  ('na-5gb-30', null, 'regional-north-america', 5.0, 30, 'zesimo', '7063', 'zesimo-na-5gb-30d', 1175, 'Zesimo phase 4: North America 5GB 30 Days (CA/MX/US)', true, true)
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

-- Keep NA 10GB / Europe 10+20 on the coverage-matching cheap twins.
update public.plan_fulfillment_map
set
  provider = 'zesimo',
  provider_sku = '587',
  provider_slug = 'zesimo-na-10gb-30d',
  wholesale_cents = 1403,
  notes = coalesce(notes, '') || ' → Zesimo NA 10GB/30d CA/MX/US live price',
  admin_approved = true,
  is_active = true,
  updated_at = now()
where catalog_key = 'na-10gb-30';

update public.plan_fulfillment_map
set
  provider = 'zesimo',
  provider_sku = '11709',
  provider_slug = 'zesimo-eu-10gb-30d',
  wholesale_cents = 966,
  notes = coalesce(notes, '') || ' → Zesimo Europe 10GB/30d 41-country twin',
  admin_approved = true,
  is_active = true,
  updated_at = now()
where catalog_key = 'eu-10gb-30';

update public.plan_fulfillment_map
set
  provider = 'zesimo',
  provider_sku = '11711',
  provider_slug = 'zesimo-eu-20gb-30d',
  wholesale_cents = 1526,
  notes = coalesce(notes, '') || ' → Zesimo Europe 20GB/30d 41-country twin',
  admin_approved = true,
  is_active = true,
  updated_at = now()
where catalog_key = 'eu-20gb-30';

-- Retire Telna Global rungs we no longer sell.
update public.plan_fulfillment_map
set
  is_active = false,
  notes = coalesce(notes, '') || ' [superseded by Zesimo Global 193]',
  updated_at = now()
where catalog_key in ('gl-3gb-7', 'gl-5gb-15')
  and provider = 'telna';
