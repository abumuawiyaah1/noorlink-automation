-- WhatsApp campaign: 10% off for Umrah / Hajj travelers messaged on WhatsApp
insert into public.promo_codes (
  code,
  label,
  percent_off,
  starts_at,
  ends_at,
  is_active,
  admin_approved,
  min_order_cents
) values (
  'UMRAH10',
  'WhatsApp Umrah 10% off',
  10,
  '2026-09-22T00:00:00Z',
  '2027-08-31T23:59:59Z',
  true,
  true,
  0
)
on conflict (code) do update set
  label = excluded.label,
  percent_off = excluded.percent_off,
  starts_at = excluded.starts_at,
  ends_at = excluded.ends_at,
  is_active = true,
  admin_approved = true,
  min_order_cents = excluded.min_order_cents;
