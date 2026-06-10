-- Seed browsable plan tiers (run after 20260605000000_esim_plans.sql)

insert into public.esim_plans (
  destination_slug, destination_name, flag_emoji, plan_name,
  data_label, data_total_gb, duration_days, price_cents,
  is_pay_as_you_go, sort_order
) values
  -- Turkey
  ('turkey', 'Turkey', '🇹🇷', 'Starter', '3GB', 3, 7, 450, false, 10),
  ('turkey', 'Turkey', '🇹🇷', 'Traveler', '10GB', 10, 15, 650, false, 20),
  ('turkey', 'Turkey', '🇹🇷', 'Explorer', '20GB', 20, 30, 950, false, 30),
  ('turkey', 'Turkey', '🇹🇷', 'Flex Data', 'Pay-As-You-Go', null, null, 299, true, 40),

  -- United States
  ('usa', 'United States', '🇺🇸', 'Starter', '3GB', 3, 7, 450, false, 10),
  ('usa', 'United States', '🇺🇸', 'Traveler', '10GB', 10, 15, 550, false, 20),
  ('usa', 'United States', '🇺🇸', 'Explorer', '20GB', 20, 30, 850, false, 30),
  ('usa', 'United States', '🇺🇸', 'Flex Data', 'Pay-As-You-Go', null, null, 299, true, 40),

  -- Europe (regional)
  ('europe', 'Europe', '🇪🇺', 'Starter', '5GB', 5, 10, 500, false, 10),
  ('europe', 'Europe', '🇪🇺', 'Traveler', '10GB', 10, 15, 650, false, 20),
  ('europe', 'Europe', '🇪🇺', 'Explorer', '20GB', 20, 30, 950, false, 30),
  ('europe', 'Europe', '🇪🇺', 'Flex Data', 'Pay-As-You-Go', null, null, 349, true, 40),

  -- Japan
  ('japan', 'Japan', '🇯🇵', 'Starter', '3GB', 3, 7, 550, false, 10),
  ('japan', 'Japan', '🇯🇵', 'Traveler', '10GB', 10, 15, 750, false, 20),
  ('japan', 'Japan', '🇯🇵', 'Explorer', '20GB', 20, 30, 1050, false, 30),
  ('japan', 'Japan', '🇯🇵', 'Flex Data', 'Pay-As-You-Go', null, null, 399, true, 40),

  -- Saudi Arabia / Umrah
  ('saudi-arabia', 'Saudi Arabia', '🇸🇦', 'Starter', '5GB', 5, 10, 650, false, 10),
  ('saudi-arabia', 'Saudi Arabia', '🇸🇦', 'Traveler', '10GB', 10, 15, 850, false, 20),
  ('saudi-arabia', 'Saudi Arabia', '🇸🇦', 'Explorer', '20GB', 20, 30, 1150, false, 30),
  ('saudi-arabia', 'Saudi Arabia', '🇸🇦', 'Flex Data', 'Pay-As-You-Go', null, null, 399, true, 40)
on conflict do nothing;
