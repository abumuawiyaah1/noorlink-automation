-- Lock down legacy public tables flagged by Supabase Security Advisor
-- (RLS not enabled). None of these are used by the live NoorLink API
-- (catalog = mobile_data_plans / esim_packages; fulfillment logs live elsewhere).
-- Service role (backend) still bypasses RLS.

do $$
declare
  t text;
  tables text[] := array[
    'provisioning_logs',
    'countries',
    'promotions',
    'providers'
  ];
begin
  foreach t in array tables
  loop
    if to_regclass(format('public.%I', t)) is null then
      raise notice 'public.% does not exist — skip', t;
      continue;
    end if;

    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_no_public_access', t);
    execute format(
      'create policy %I on public.%I for all to anon, authenticated using (false) with check (false)',
      t || '_no_public_access',
      t
    );
    execute format(
      'comment on table public.%I is %L',
      t,
      'Legacy/unused table. RLS on; no anon/authenticated access. Prefer current catalog & ops tables.'
    );
  end loop;
end
$$;
