-- Retire ALL active Telna + WeConnect fulfillment + cascade catalog rows.
-- Historical orders keep provider on the order row; clients stay for usage sync.
-- Paste into Supabase SQL Editor.

-- 1) Fulfillment maps
update public.plan_fulfillment_map
set is_active = false,
    notes = coalesce(notes, '') || ' | retired Telna/WeConnect cutover',
    updated_at = now()
where is_active = true
  and lower(provider) in ('telna', 'weconnect');

-- 2) Cascade warehouse (so resolve_cascade cannot pick them)
update public.provider_catalog_products
set is_active = false,
    updated_at = now()
where is_active = true
  and lower(provider) in ('telna', 'weconnect');

-- Verify (expect 0)
select 'fulfillment_map' as src, count(*) as active
from public.plan_fulfillment_map
where is_active and lower(provider) in ('telna','weconnect')
union all
select 'provider_catalog_products', count(*)
from public.provider_catalog_products
where is_active and lower(provider) in ('telna','weconnect');
