-- Promo codes over 20% off require explicit admin approval before checkout use.

alter table public.promo_codes
  add column if not exists admin_approved boolean not null default true,
  add column if not exists admin_approved_by text,
  add column if not exists admin_approved_at timestamptz;

comment on column public.promo_codes.admin_approved is
  'Codes with percent_off > 20 require admin approval before they work at checkout.';

-- Existing rows stay usable (Insider 10%, etc.)
update public.promo_codes
set admin_approved = true
where admin_approved is distinct from true;
