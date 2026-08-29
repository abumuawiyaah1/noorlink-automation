-- Owner / break-glass protection for admin dashboard
-- Prevents a normal admin from locking out the business owner.

alter table public.admin_users
  drop constraint if exists admin_users_role_check;

alter table public.admin_users
  add constraint admin_users_role_check
  check (role in (
    'owner',
    'admin',
    'support',
    'catalog',
    'marketing',
    'finance',
    'legal'
  ));

-- Soft flag: protected accounts refuse UI demote/deactivate (owners are always protected)
alter table public.admin_users
  add column if not exists is_protected boolean not null default false;

update public.admin_users
set is_protected = true
where role = 'owner';

create index if not exists admin_users_role_protected_idx
  on public.admin_users (role, is_protected);

comment on column public.admin_users.is_protected is
  'When true (always for owner), UI cannot demote/deactivate without owner/break-glass.';
