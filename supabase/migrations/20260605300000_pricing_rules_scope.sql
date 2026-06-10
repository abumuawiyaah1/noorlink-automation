-- Hierarchy engine: pricing_rules scoped to COUNTRY, REGION, or GLOBAL.

create type public.pricing_rule_scope as enum ('COUNTRY', 'REGION', 'GLOBAL');

alter table public.pricing_rules
  add column if not exists scope public.pricing_rule_scope not null default 'GLOBAL',
  add column if not exists target_id text;

comment on column public.pricing_rules.scope is
  'Rule precedence tier: COUNTRY → REGION → GLOBAL fallback.';

comment on column public.pricing_rules.target_id is
  'country_id or region_id slug when scope is COUNTRY or REGION; null for GLOBAL.';

create index if not exists pricing_rules_scope_target_idx
  on public.pricing_rules (scope, target_id)
  where is_active = true;

alter table public.mobile_data_plans
  add column if not exists region_id text;

comment on column public.mobile_data_plans.region_id is
  'Region slug used for REGION-scoped pricing_rules lookup (e.g. europe, middle-east).';
