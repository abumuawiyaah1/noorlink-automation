-- Support email threads: tickets linked to orders + message history

alter table public.support_tickets
  add column if not exists order_number text,
  add column if not exists last_message_at timestamptz,
  add column if not exists updated_at timestamptz not null default now();

create index if not exists support_tickets_order_number_idx
  on public.support_tickets (order_number)
  where order_number is not null;

create index if not exists support_tickets_last_message_idx
  on public.support_tickets (last_message_at desc nulls last);

create table if not exists public.support_messages (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references public.support_tickets (id) on delete cascade,
  order_number text,
  direction text not null check (direction in ('inbound', 'outbound')),
  from_email text not null,
  to_email text not null,
  subject text,
  body_text text,
  body_html text,
  resend_email_id text,
  admin_username text,
  message_id_header text,
  in_reply_to text,
  created_at timestamptz not null default now()
);

create index if not exists support_messages_ticket_created_idx
  on public.support_messages (ticket_id, created_at);

create index if not exists support_messages_order_number_idx
  on public.support_messages (order_number)
  where order_number is not null;

comment on table public.support_messages is
  'Inbound/outbound email thread for support tickets (admin inbox + customer history).';
