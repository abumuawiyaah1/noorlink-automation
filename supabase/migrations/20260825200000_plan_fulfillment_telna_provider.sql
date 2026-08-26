-- Allow Telna as a fulfillment provider (Caribbean + future Telna SKUs)

alter table public.plan_fulfillment_map
  drop constraint if exists plan_fulfillment_map_provider_check;

alter table public.plan_fulfillment_map
  add constraint plan_fulfillment_map_provider_check
  check (provider in ('citrus', 'esimaccess', 'mock', 'simbase', 'telna'));
