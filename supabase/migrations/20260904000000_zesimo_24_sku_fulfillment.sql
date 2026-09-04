-- Zesimo 24-SKU cutover (phases 1–3).
-- Keep Access SA fixed GB + SA unlimited 14d; Caribbean stays Telna; PAYG stays Citrus.

alter table public.plan_fulfillment_map
  drop constraint if exists plan_fulfillment_map_provider_check;

alter table public.plan_fulfillment_map
  add constraint plan_fulfillment_map_provider_check
  check (provider in ('citrus', 'esimaccess', 'mock', 'simbase', 'telna', 'zesimo', 'weconnect'));

alter table public.provider_catalog_products
  drop constraint if exists provider_catalog_products_provider_check;

-- Inline column CHECK may be unnamed differently on older DBs; recreate safely.
do $$
begin
  if exists (
    select 1 from information_schema.table_constraints
    where table_schema = 'public'
      and table_name = 'provider_catalog_products'
      and constraint_type = 'CHECK'
      and constraint_name like '%provider%'
  ) then
    null; -- already dropped by name above when present
  end if;
exception when others then
  null;
end $$;

alter table public.provider_catalog_products
  add constraint provider_catalog_products_provider_check
  check (provider in ('citrus', 'esimaccess', 'telna', 'simbase', 'mock', 'zesimo', 'weconnect'));

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
  ('sa-unlimited-3gb-7d', 'SA', 'saudi-arabia', 3.0, 7, 'zesimo', '10903', 'zesimo-sa-unlimited-7d', 2142, 'Zesimo phase 1: Saudi Arabia Unlimited 7 Days', true, true),
  ('sa-unlimited-3gb-10d', 'SA', 'saudi-arabia', 3.0, 10, 'zesimo', '10905', 'zesimo-sa-unlimited-10d', 2786, 'Zesimo phase 1: Saudi Arabia Unlimited 10 Days', true, true),
  ('me-5gb-15', null, 'regional-middle-east', 5.0, 15, 'zesimo', '1085', 'zesimo-me-5gb-15d', 991, 'Zesimo phase 1: MIDDLE EAST 5GB 15 Days', true, true),
  ('me-10gb-30', null, 'regional-middle-east', 10.0, 30, 'zesimo', '1086', 'zesimo-me-10gb-30d', 1784, 'Zesimo phase 1: MIDDLE EAST 10GB 30 Days', true, true),
  ('eu-5gb-30', null, 'regional-europe', 5.0, 30, 'zesimo', '11707', 'zesimo-eu-5gb-30d', 602, 'Zesimo phase 2: Europe 5GB 30 Days', true, true),
  ('eu-10gb-30', null, 'regional-europe', 10.0, 30, 'zesimo', '583', 'zesimo-eu-10gb-30d', 798, 'Zesimo phase 2: Europe 10GB 30 Days', true, true),
  ('la-5gb-30', null, 'regional-south-america', 5.0, 30, 'zesimo', '12121', 'zesimo-la-5gb-30d', 1050, 'Zesimo phase 2: Latin America 5GB 30 Days', true, true),
  ('la-10gb-30', null, 'regional-south-america', 10.0, 30, 'zesimo', '12122', 'zesimo-la-10gb-30d', 1764, 'Zesimo phase 2: Latin America 10GB 30 Days', true, true),
  ('mx-5gb-30', 'MX', 'mexico', 5.0, 30, 'zesimo', '8186', 'zesimo-mx-5gb-30d', 812, 'Zesimo phase 2: Mexico 5GB 30 Days', true, true),
  ('mx-10gb-30', 'MX', 'mexico', 10.0, 30, 'zesimo', '8188', 'zesimo-mx-10gb-30d', 1400, 'Zesimo phase 2: Mexico 10GB 30 Days', true, true),
  ('us-5gb-30', 'US', 'united-states', 5.0, 30, 'zesimo', '3363', 'zesimo-us-5gb-30d', 463, 'Zesimo phase 2: United States 5GB 30 Days', true, true),
  ('us-10gb-30', 'US', 'united-states', 10.0, 30, 'zesimo', '7673', 'zesimo-us-10gb-30d', 809, 'Zesimo phase 2: United States 10GB 30 Days', true, true),
  ('na-10gb-30', null, 'regional-north-america', 10.0, 30, 'zesimo', '587', 'zesimo-na-10gb-30d', 1398, 'Zesimo phase 2: North America 10GB 30 Days', true, true),
  ('as-5gb-30', null, 'regional-asia-pacific', 5.0, 30, 'zesimo', '11733', 'zesimo-as-5gb-30d', 434, 'Zesimo phase 2: Asia 5GB 30 Days', true, true),
  ('as-10gb-30', null, 'regional-asia-pacific', 10.0, 30, 'zesimo', '11736', 'zesimo-as-10gb-30d', 714, 'Zesimo phase 2: Asia 10GB 30 Days', true, true),
  ('eu-20gb-30', null, 'regional-europe', 20.0, 30, 'zesimo', '586', 'zesimo-eu-20gb-30d', 1409, 'Zesimo phase 3: Europe 20GB 30 Days', true, true),
  ('as-20gb-30', null, 'regional-asia-pacific', 20.0, 30, 'zesimo', '11738', 'zesimo-as-20gb-30d', 1092, 'Zesimo phase 3: Asia 20GB 30 Days', true, true),
  ('us-20gb-30', 'US', 'united-states', 20.0, 30, 'zesimo', '7677', 'zesimo-us-20gb-30d', 1450, 'Zesimo phase 3: United States 20GB 30 Days', true, true),
  ('la-20gb-30', null, 'regional-south-america', 20.0, 30, 'zesimo', '12123', 'zesimo-la-20gb-30d', 2814, 'Zesimo phase 3: Latin America 20GB 30 Days', true, true),
  ('mx-20gb-30', 'MX', 'mexico', 20.0, 30, 'zesimo', '8190', 'zesimo-mx-20gb-30d', 2226, 'Zesimo phase 3: Mexico 20GB 30 Days', true, true),
  ('eu-1gb-7', null, 'regional-europe', 1.0, 7, 'zesimo', '11701', 'zesimo-eu-1gb-7d', 252, 'Zesimo phase 3: Europe 1GB 7 Days', true, true),
  ('na-1gb-7', null, 'regional-north-america', 1.0, 7, 'zesimo', '580', 'zesimo-na-1gb-7d', 182, 'Zesimo phase 3: North America 1GB 7 Days', true, true),
  ('gulf-5gb-30', null, 'regional-gulf', 5.0, 30, 'zesimo', '2544', 'zesimo-gulf-5gb-30d', 1512, 'Zesimo phase 3: Gulf Region 5GB 30 Days', true, true),
  ('la-3gb-30', null, 'regional-south-america', 3.0, 30, 'zesimo', '12094', 'zesimo-la-3gb-30d', 700, 'Zesimo phase 3: Latin America 3GB 30 Days', true, true)
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

-- Silent ME country storefronts that shared Telna ME 5/10 → same Zesimo ME packages
update public.plan_fulfillment_map
set
  provider = 'zesimo',
  provider_sku = '1085',
  provider_slug = 'zesimo-me-5gb-15d',
  wholesale_cents = 991,
  notes = coalesce(notes, '') || ' → Zesimo ME 5GB/15d',
  admin_approved = true,
  is_active = true,
  updated_at = now()
where catalog_key like '%-5gb-15'
  and provider = 'telna'
  and provider_slug like 'telna-me-%';

update public.plan_fulfillment_map
set
  provider = 'zesimo',
  provider_sku = '1086',
  provider_slug = 'zesimo-me-10gb-30d',
  wholesale_cents = 1784,
  notes = coalesce(notes, '') || ' → Zesimo ME 10GB/30d',
  admin_approved = true,
  is_active = true,
  updated_at = now()
where catalog_key like '%-10gb-30'
  and provider = 'telna'
  and provider_slug like 'telna-me-%';

-- Superseded Telna keys replaced by longer/cheaper Zesimo ladders (keep row for history)
update public.plan_fulfillment_map
set
  is_active = false,
  notes = coalesce(notes, '') || ' [superseded by Zesimo cutover]',
  updated_at = now()
where catalog_key in (
  'eu-1gb-5',
  'eu-5gb-15',
  'as-5gb-15',
  'la-5gb-15',
  'la-3gb-7',
  'mx-5gb-15',
  'na-1gb-5'
)
and provider = 'telna';
