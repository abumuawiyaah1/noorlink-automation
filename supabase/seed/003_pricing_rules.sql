-- Hierarchy pricing rules (run after 20260605300000_pricing_rules_scope.sql)

insert into public.pricing_rules (
  rule_name, scope, target_id, multiplier, fixed_buffer, min_margin_amount,
  price_suffix_rule, is_active
) values
  ('global_standard', 'GLOBAL', null, 1.3500, 2.00, 3.00, 'ROUND_TO_95', true),
  ('premium_destination', 'REGION', 'middle-east', 1.5500, 4.00, 5.00, 'ROUND_TO_77', true),
  ('turkey_country_premium', 'COUNTRY', 'turkey', 1.4500, 3.00, 4.00, 'ROUND_TO_95', true)
on conflict (rule_name) do update set
  scope = excluded.scope,
  target_id = excluded.target_id,
  multiplier = excluded.multiplier,
  fixed_buffer = excluded.fixed_buffer,
  min_margin_amount = excluded.min_margin_amount,
  price_suffix_rule = excluded.price_suffix_rule,
  is_active = excluded.is_active;
