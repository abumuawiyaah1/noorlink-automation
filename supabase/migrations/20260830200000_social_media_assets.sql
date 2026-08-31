-- Social media asset library for admin dashboard (partner photos/videos for FB/IG)
-- Private Storage bucket `social-media-assets` — see docs/SOCIAL-MEDIA-HUB.md

create table if not exists public.social_media_assets (
  id uuid primary key default gen_random_uuid(),
  partner text not null default '',
  caption text not null default '',
  notes text not null default '',
  status text not null default 'new'
    check (status in ('new', 'ready', 'posted')),
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

create index if not exists social_media_assets_status_idx
  on public.social_media_assets (status)
  where deleted_at is null;

create index if not exists social_media_assets_created_at_idx
  on public.social_media_assets (created_at desc);

alter table public.social_media_assets enable row level security;

comment on table public.social_media_assets is
  'Partner/marketing media for social posts. Files in Storage bucket social-media-assets.';

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'social-media-assets',
  'social-media-assets',
  false,
  104857600,
  array[
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/gif',
    'video/mp4',
    'video/quicktime',
    'video/webm'
  ]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "social_media_assets_no_public_select" on storage.objects;
create policy "social_media_assets_no_public_select"
  on storage.objects for select
  using (bucket_id = 'social-media-assets' and false);

drop policy if exists "social_media_assets_no_public_insert" on storage.objects;
create policy "social_media_assets_no_public_insert"
  on storage.objects for insert
  with check (bucket_id = 'social-media-assets' and false);

drop policy if exists "social_media_assets_no_public_update" on storage.objects;
create policy "social_media_assets_no_public_update"
  on storage.objects for update
  using (bucket_id = 'social-media-assets' and false);

drop policy if exists "social_media_assets_no_public_delete" on storage.objects;
create policy "social_media_assets_no_public_delete"
  on storage.objects for delete
  using (bucket_id = 'social-media-assets' and false);
