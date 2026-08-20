-- Simbase provisioning + usage-guard fields on orders
-- Safe to re-run (IF NOT EXISTS / DO blocks).

-- Allow suspended status for margin-guard auto-disable
do $$
begin
  if not exists (
    select 1
    from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    where t.typname = 'order_status'
      and e.enumlabel = 'suspended'
  ) then
    alter type public.order_status add value 'suspended';
  end if;
end
$$;

alter table public.orders
  add column if not exists iccid text,
  add column if not exists smdp_address text,
  add column if not exists lpa_string text,
  add column if not exists data_limit_bytes bigint;

create unique index if not exists orders_iccid_unique_idx
  on public.orders (iccid)
  where iccid is not null;

comment on column public.orders.iccid is
  'Simbase ICCID for the provisioned eSIM profile.';
comment on column public.orders.smdp_address is
  'SM-DP+ address used in the GSMA LPA string.';
comment on column public.orders.lpa_string is
  'Full LPA:1$... activation string for QR / device install.';
comment on column public.orders.data_limit_bytes is
  'Hard data cap in bytes for pay-as-you-go margin protection.';
