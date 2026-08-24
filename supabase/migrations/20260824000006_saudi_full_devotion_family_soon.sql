-- Full Devotion 50GB at wholesale=retail; Family Share coming soon (inactive).

update public.mobile_data_plans
set
  name = 'Full Devotion 50GB',
  plan_category = 'FIXED'::public.plan_category,
  pricing_strategy = 'MANUAL'::public.pricing_strategy,
  override_price = wholesale_cost,
  updated_at = now()
where country_id = 'saudi-arabia'
  and is_active = true
  and name in ('Unlimited Devotion 50GB', 'Full Devotion 50GB', 'Unlimited Devotion');

update public.mobile_data_plans
set
  is_active = false,
  updated_at = now()
where country_id = 'saudi-arabia'
  and name in ('Family Share 50GB', 'Family Share 30GB', 'Family Share')
  and is_active = true;
