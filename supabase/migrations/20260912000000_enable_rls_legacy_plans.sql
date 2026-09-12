-- Lock down legacy public.plans (Supabase advisor: RLS not enabled).
-- Live catalog uses mobile_data_plans / esim_packages; orders must not write plan_id
-- that FKs this table. Enabling RLS with no anon/authenticated policies denies
-- direct PostgREST access. Service role (backend) still bypasses RLS.

do $$
begin
  if to_regclass('public.plans') is null then
    raise notice 'public.plans does not exist — nothing to lock down';
    return;
  end if;

  alter table public.plans enable row level security;

  -- Explicit deny for authenticated/anon (optional clarity; no policy = deny).
  drop policy if exists "plans_no_public_access" on public.plans;
  create policy "plans_no_public_access"
    on public.plans
    for all
    to anon, authenticated
    using (false)
    with check (false);

  comment on table public.plans is
    'Legacy catalog table. Prefer mobile_data_plans / esim_packages. RLS on; no public access.';
end
$$;
