-- Return Saudi pilgrimage plans to AUTOMATED retail from wholesale + pricing_rules.
-- Saudi uses REGION middle-east: multiplier 1.55, fixed_buffer 4, min_margin 5, ROUND_TO_77.

update public.mobile_data_plans
set
  pricing_strategy = 'AUTOMATED'::public.pricing_strategy,
  override_price = null,
  updated_at = now()
where country_id = 'saudi-arabia'
  and is_active = true
  and name in (
    'Lite Explorer 5GB',
    'Connected Pilgrim 10GB',
    'Connected Pilgrim 20GB',
    'Unlimited Devotion 50GB',
    'Family Share 50GB'
  );
