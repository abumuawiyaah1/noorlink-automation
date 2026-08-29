-- Catalog admin approval: new plans, price changes, and provider maps

alter table public.esim_packages
  add column if not exists admin_approved boolean not null default true,
  add column if not exists admin_approved_by text,
  add column if not exists admin_approved_at timestamptz,
  add column if not exists pending_price_cents integer;

alter table public.plan_fulfillment_map
  add column if not exists admin_approved boolean not null default true,
  add column if not exists admin_approved_by text,
  add column if not exists admin_approved_at timestamptz;

comment on column public.esim_packages.pending_price_cents is
  'Proposed retail price (cents) awaiting admin approval before going live.';

comment on column public.plan_fulfillment_map.admin_approved is
  'New or changed provider routes require admin approval before checkout fulfillment.';

update public.esim_packages set admin_approved = true where admin_approved is distinct from true;
update public.plan_fulfillment_map set admin_approved = true where admin_approved is distinct from true;
