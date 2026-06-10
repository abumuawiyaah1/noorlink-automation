-- Seed featured packages (matches static site starter set)
-- Run after 20260602000000_initial_schema.sql and 20260602100000_esim_packages_managed_tier.sql

insert into public.esim_packages (
  slug, name, country, country_code, region, flag_emoji,
  data_label, data_total_gb, validity_days, price_cents, is_featured, sort_order,
  is_managed, tier
) values
  ('usa-5gb-7d', 'United States 5GB · 7 Days', 'United States', 'US', 'Americas', '🇺🇸', '5GB', 5, 7, 450, true, 10, true, 'core'),
  ('europe-regional-10gb-15d', 'Europe 10GB · 15 Days', 'Europe', null, 'Europe', '🇪🇺', '10GB', 10, 15, 500, true, 20, true, 'core'),
  ('japan-10gb-15d', 'Japan 10GB · 15 Days', 'Japan', 'JP', 'Asia', '🇯🇵', '10GB', 10, 15, 600, true, 30, true, 'core'),
  ('turkey-10gb-15d', 'Turkey 10GB · 15 Days', 'Turkey', 'TR', 'Middle East', '🇹🇷', '10GB', 10, 15, 450, true, 40, true, 'core'),
  ('uk-10gb-15d', 'United Kingdom 10GB · 15 Days', 'United Kingdom', 'GB', 'Europe', '🇬🇧', '10GB', 10, 15, 500, true, 50, true, 'core'),
  ('saudi-arabia-10gb-15d', 'Saudi Arabia 10GB · 15 Days', 'Saudi Arabia', 'SA', 'Middle East', '🇸🇦', '10GB', 10, 15, 700, true, 60, true, 'core')
on conflict (slug) do update set
  is_managed = excluded.is_managed,
  tier = excluded.tier,
  price_cents = excluded.price_cents,
  is_featured = excluded.is_featured,
  sort_order = excluded.sort_order;
