-- Company document vault (legal + accounting) + finance/legal staff roles
-- Apply in Supabase SQL editor or via supabase db push.
-- Also create a PRIVATE Storage bucket named `company-documents` (see docs/DOCUMENT-VAULT.md).

-- Expand staff roles for document vault growth
alter table public.admin_users
  drop constraint if exists admin_users_role_check;

alter table public.admin_users
  add constraint admin_users_role_check
  check (role in ('admin', 'support', 'catalog', 'marketing', 'finance', 'legal'));

create table if not exists public.company_documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  category text not null
    check (category in ('legal', 'accounting', 'tax', 'contracts', 'compliance', 'other')),
  access_level text not null default 'vault'
    check (access_level in ('vault', 'admin_only')),
  description text,
  document_year int,
  original_filename text not null,
  content_type text not null,
  file_size_bytes bigint not null check (file_size_bytes > 0),
  storage_path text not null unique,
  uploaded_by text not null,
  deleted_at timestamptz,
  deleted_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists company_documents_category_idx
  on public.company_documents (category)
  where deleted_at is null;

create index if not exists company_documents_created_at_idx
  on public.company_documents (created_at desc);

create index if not exists company_documents_year_idx
  on public.company_documents (document_year)
  where deleted_at is null;

alter table public.company_documents enable row level security;

comment on table public.company_documents is
  'Internal legal/accounting document catalog. Files live in Storage bucket company-documents.';

-- Private storage bucket (safe to re-run)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'company-documents',
  'company-documents',
  false,
  20971520,
  array[
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/webp',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/csv',
    'text/plain'
  ]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Deny anon/authenticated direct access; service_role used by API bypasses RLS
drop policy if exists "company_documents_no_public_select" on storage.objects;
create policy "company_documents_no_public_select"
  on storage.objects for select
  using (bucket_id = 'company-documents' and false);

drop policy if exists "company_documents_no_public_insert" on storage.objects;
create policy "company_documents_no_public_insert"
  on storage.objects for insert
  with check (bucket_id = 'company-documents' and false);

drop policy if exists "company_documents_no_public_update" on storage.objects;
create policy "company_documents_no_public_update"
  on storage.objects for update
  using (bucket_id = 'company-documents' and false);

drop policy if exists "company_documents_no_public_delete" on storage.objects;
create policy "company_documents_no_public_delete"
  on storage.objects for delete
  using (bucket_id = 'company-documents' and false);
