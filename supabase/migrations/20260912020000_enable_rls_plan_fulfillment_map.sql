-- Lock down plan_fulfillment_map (Supabase advisor: RLS not enabled).
-- Used only by backend (service role) and admin SQLAlchemy (DATABASE_URL).
-- Contains provider SKUs + wholesale costs — must not be anon-readable.

do $$
begin
  if to_regclass('public.plan_fulfillment_map') is null then
    raise notice 'public.plan_fulfillment_map does not exist — skip';
    return;
  end if;

  alter table public.plan_fulfillment_map enable row level security;

  drop policy if exists "plan_fulfillment_map_no_public_access" on public.plan_fulfillment_map;
  create policy "plan_fulfillment_map_no_public_access"
    on public.plan_fulfillment_map
    for all
    to anon, authenticated
    using (false)
    with check (false);

  comment on table public.plan_fulfillment_map is
    'Maps sellable plans to upstream provider SKUs. RLS on; backend/admin only (no public PostgREST access).';
end
$$;
