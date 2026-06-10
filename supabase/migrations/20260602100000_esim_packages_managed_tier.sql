-- Wave 1: managed inventory flags for pricing validation
-- Adds is_managed (server-enforced catalog pricing) and tier (core vs regional baseline)

alter table public.esim_packages
  add column if not exists is_managed boolean not null default false,
  add column if not exists tier text;

comment on column public.esim_packages.is_managed is
  'When true, checkout must match price_cents exactly; client-supplied prices are rejected.';

comment on column public.esim_packages.tier is
  'Inventory class: core (NoorLink-managed SKUs) or regional (template baselines).';

create index if not exists esim_packages_managed_idx
  on public.esim_packages (is_managed)
  where is_managed = true;

-- Backfill seeded core SKUs (idempotent if seed already ran without flags)
update public.esim_packages
set
  is_managed = true,
  tier = 'core'
where slug in (
  'usa-5gb-7d',
  'europe-regional-10gb-15d',
  'japan-10gb-15d',
  'turkey-10gb-15d',
  'uk-10gb-15d',
  'saudi-arabia-10gb-15d'
);
