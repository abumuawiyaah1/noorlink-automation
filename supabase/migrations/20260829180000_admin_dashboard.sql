-- NoorLink admin dashboard: staff users + audit trail
-- Safe to re-run.

create extension if not exists "pgcrypto";
create extension if not exists "citext";

create table if not exists public.admin_users (
  id uuid primary key default gen_random_uuid(),
  username citext not null unique,
  password_hash text not null,
  display_name text,
  role text not null default 'admin'
    check (role in ('admin', 'support', 'catalog')),
  is_active boolean not null default true,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists admin_users_role_active_idx
  on public.admin_users (role, is_active);

create table if not exists public.admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  admin_user_id uuid references public.admin_users (id) on delete set null,
  admin_username text not null,
  action text not null,
  table_name text not null,
  record_id text,
  old_values jsonb,
  new_values jsonb,
  ip_address text,
  created_at timestamptz not null default now()
);

create index if not exists admin_audit_log_created_at_idx
  on public.admin_audit_log (created_at desc);

create index if not exists admin_audit_log_table_action_idx
  on public.admin_audit_log (table_name, action);

alter table public.admin_users enable row level security;
alter table public.admin_audit_log enable row level security;

comment on table public.admin_users is
  'NoorLink staff accounts for /admin SQLAdmin dashboard (session auth).';
comment on table public.admin_audit_log is
  'Immutable audit trail for admin dashboard mutations and sensitive actions.';
