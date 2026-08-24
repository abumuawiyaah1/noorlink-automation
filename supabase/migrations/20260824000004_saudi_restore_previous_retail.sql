-- Restore previous intentional Saudi retail ladder (before Access-50GB cost hike).
-- Keep Access SA_50_30 wholesale ($59.90) so Unlimited/Family margins stay honest.

update public.mobile_data_plans
set
  pricing_strategy = 'MANUAL'::public.pricing_strategy,
  override_price = v.override_price,
  updated_at = now()
from (values
  ('Lite Explorer 5GB', 12.95::numeric),
  ('Connected Pilgrim 10GB', 18.95::numeric),
  ('Connected Pilgrim 20GB', 27.95::numeric),
  ('Unlimited Devotion 50GB', 34.95::numeric),
  ('Family Share 50GB', 39.95::numeric)
) as v(name, override_price)
where mobile_data_plans.country_id = 'saudi-arabia'
  and mobile_data_plans.name = v.name
  and mobile_data_plans.is_active = true;
