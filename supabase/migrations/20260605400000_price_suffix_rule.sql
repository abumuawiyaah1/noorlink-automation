-- Psychological price suffix rules (e.g. $12.95, $9.77).

create type public.price_suffix_rule as enum (
  'STANDARD',
  'ROUND_TO_77',
  'ROUND_TO_95'
);

alter table public.pricing_rules
  add column if not exists price_suffix_rule public.price_suffix_rule
    not null default 'STANDARD';

comment on column public.pricing_rules.price_suffix_rule is
  'Retail price charm suffix applied after margin floor (ROUND_TO_95 → .95, etc.).';
