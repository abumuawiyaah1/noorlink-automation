-- Support ticket categories, assignment, and staff notification emails

alter table public.support_tickets
  add column if not exists category text,
  add column if not exists assigned_to text,
  add column if not exists assigned_at timestamptz;

create index if not exists support_tickets_category_idx
  on public.support_tickets (category)
  where category is not null;

create index if not exists support_tickets_assigned_to_idx
  on public.support_tickets (assigned_to)
  where assigned_to is not null;

alter table public.admin_users
  add column if not exists notify_email text;

comment on column public.support_tickets.category is
  'Normalized problem type: order_help, install_qr, checkout_payment, refund, other';

comment on column public.admin_users.notify_email is
  'Optional email for support ticket assignment alerts';
