-- Insider Year 2 (Sep 2027–Aug 2028) + Ramadan/Hajj specials
-- Specials: audience = pilgrimage (buyers / Umrah-Hajj interest only)

alter table public.insider_issues
  add column if not exists audience text not null default 'all';

alter table public.insider_issues
  drop constraint if exists insider_issues_audience_check;

alter table public.insider_issues
  add constraint insider_issues_audience_check
  check (audience in ('all', 'pilgrimage'));

alter table public.insider_issues
  add column if not exists email_highlight text;

alter table public.insider_issues
  add column if not exists email_highlight_ref text;

alter table public.insider_issues
  add column if not exists email_note text;

alter table public.insider_issues
  add column if not exists email_giving_note text;

insert into public.promo_codes (
  code, label, percent_off, starts_at, ends_at, insider_issue_slug
) values
  ('INSIDER-RAMADAN27', 'Insider Ramadan Special 2027', 10, '2027-01-08T00:00:00Z', '2027-02-28T23:59:59Z', '2027-01-ramadan-special'),
  ('INSIDER-HAJJ27', 'Insider Hajj Special 2027', 10, '2027-04-16T00:00:00Z', '2027-05-31T23:59:59Z', '2027-04-hajj-special'),
  ('INSIDER-SEP27', 'Insider Sep 2027', 10, '2027-09-01T00:00:00Z', '2027-09-30T23:59:59Z', '2027-09-morocco-maghreb'),
  ('INSIDER-OCT27', 'Insider Oct 2027', 10, '2027-10-01T00:00:00Z', '2027-10-31T23:59:59Z', '2027-10-balkans'),
  ('INSIDER-NOV27', 'Insider Nov 2027', 10, '2027-11-01T00:00:00Z', '2027-11-30T23:59:59Z', '2027-11-egypt-nile'),
  ('INSIDER-DEC27', 'Insider Dec 2027', 10, '2027-12-01T00:00:00Z', '2027-12-31T23:59:59Z', '2027-12-southeast-asia'),
  ('INSIDER-JAN28', 'Insider Jan 2028', 10, '2028-01-01T00:00:00Z', '2028-01-31T23:59:59Z', '2028-01-gulf-leisure'),
  ('INSIDER-FEB28', 'Insider Feb 2028', 10, '2028-02-01T00:00:00Z', '2028-02-29T23:59:59Z', '2028-02-umrah-window'),
  ('INSIDER-MAR28', 'Insider Mar 2028', 10, '2028-03-01T00:00:00Z', '2028-03-31T23:59:59Z', '2028-03-uk-spring'),
  ('INSIDER-APR28', 'Insider Apr 2028', 10, '2028-04-01T00:00:00Z', '2028-04-30T23:59:59Z', '2028-04-turkey-spring'),
  ('INSIDER-MAY28', 'Insider May 2028', 10, '2028-05-01T00:00:00Z', '2028-05-31T23:59:59Z', '2028-05-iberia'),
  ('INSIDER-JUN28', 'Insider Jun 2028', 10, '2028-06-01T00:00:00Z', '2028-06-30T23:59:59Z', '2028-06-alps-north'),
  ('INSIDER-JUL28', 'Insider Jul 2028', 10, '2028-07-01T00:00:00Z', '2028-07-31T23:59:59Z', '2028-07-caribbean'),
  ('INSIDER-AUG28', 'Insider Aug 2028', 10, '2028-08-01T00:00:00Z', '2028-08-31T23:59:59Z', '2028-08-pilgrimage-prep')
on conflict (code) do update set
  label = excluded.label,
  percent_off = excluded.percent_off,
  starts_at = excluded.starts_at,
  ends_at = excluded.ends_at,
  insider_issue_slug = excluded.insider_issue_slug,
  is_active = true;

insert into public.insider_issues (
  slug, subject, preview, hero_image_url, web_path, promo_code, send_at, status, audience,
  email_highlight, email_highlight_ref, email_note, email_giving_note
) values
  (
    '2027-01-ramadan-special',
    'Umrah in Ramadan — a reward like Hajj, with calm connection',
    'A short Ramadan reminder for pilgrimage travelers — Umrah in Ramadan, calm connectivity, and our giving pledge.',
    'https://noorlink.co/images/insider/insider-2027-01-ramadan-special.jpg',
    '/newsletter/2027-01-ramadan-special',
    'INSIDER-RAMADAN27',
    '2027-01-08T14:00:00Z',
    'scheduled',
    'pilgrimage',
    'When Ramadan comes, go for Umrah — for Umrah in Ramadan is equivalent to Hajj.',
    'Bukhari 1782 · Muslim 1256',
    'A short reminder, a few du‘ā’s for Makkah and Madinah, and calm connectivity habits — full version on the site.',
    'With INSIDER-RAMADAN27 you receive 10% off. NoorLink also pledges 10% of our profit from eligible purchases to charity.'
  ),
  (
    '2027-04-hajj-special',
    'Hajj season reminder — sacred journey, clear intention, steady signal',
    'A respectful pause before Hajj — Qur’an, Sunnah, and calm install-before-you-fly guidance.',
    'https://noorlink.co/images/insider/insider-2027-04-hajj-special.jpg',
    '/newsletter/2027-04-hajj-special',
    'INSIDER-HAJJ27',
    '2027-04-16T14:00:00Z',
    'scheduled',
    'pilgrimage',
    'Whoever performs Hajj for Allah’s sake and does not commit any obscenity or wrongdoing will return as free of sin as the day his mother gave birth to him.',
    'Bukhari & Muslim',
    'A respectful pause before the season — full reminder, du‘ā’s, and connectivity notes on the site.',
    null
  ),
  (
    '2027-09-morocco-maghreb',
    'Maghreb autumn — Morocco, calm cities, clear data habits',
    'Morocco corridors, install-before-fly, and early pilgrimage planning.',
    'https://noorlink.co/images/insider/insider-2027-09-morocco.jpg',
    '/newsletter/2027-09-morocco-maghreb',
    'INSIDER-SEP27',
    '2027-09-07T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2027-10-balkans',
    'Balkans city breaks — light bags, reliable signal',
    'Short European hops, regional data, and a light Umrah note.',
    'https://noorlink.co/images/insider/insider-2027-10-balkans.jpg',
    '/newsletter/2027-10-balkans',
    'INSIDER-OCT27',
    '2027-10-05T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2027-11-egypt-nile',
    'Egypt & winter sun — Nile trips with steady data',
    'Egypt corridors, winter-sun habits, and pre-winter Umrah tips.',
    'https://noorlink.co/images/insider/insider-2027-11-egypt.jpg',
    '/newsletter/2027-11-egypt-nile',
    'INSIDER-NOV27',
    '2027-11-02T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2027-12-southeast-asia',
    'Year-end Asia — holidays, islands, data that behaves',
    'Southeast Asia holiday habits and a quiet Makkah checklist.',
    'https://noorlink.co/images/insider/insider-2027-12-sea.jpg',
    '/newsletter/2027-12-southeast-asia',
    'INSIDER-DEC27',
    '2027-12-07T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-01-gulf-leisure',
    'Gulf leisure month — cities, family visits, clear signal',
    'Gulf travel habits and post-holiday Umrah notes.',
    'https://noorlink.co/images/insider/insider-2028-01-gulf.jpg',
    '/newsletter/2028-01-gulf-leisure',
    'INSIDER-JAN28',
    '2028-01-04T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-02-umrah-window',
    'Umrah window — connectivity that stays in the background',
    'Pilgrimage checklist, hotspot for family, Hajj & Umrah Connect.',
    'https://noorlink.co/images/insider/insider-2028-02-umrah.jpg',
    '/newsletter/2028-02-umrah-window',
    'INSIDER-FEB28',
    '2028-02-01T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-03-uk-spring',
    'UK spring city days — pack light, stay online',
    'United Kingdom weekends, Europe habits, light pilgrimage note.',
    'https://noorlink.co/images/insider/insider-2028-03-uk.jpg',
    '/newsletter/2028-03-uk-spring',
    'INSIDER-MAR28',
    '2028-03-07T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-04-turkey-spring',
    'Turkey in spring — cities, coast, ready data',
    'Turkey shoulder season, multi-city tips, post-Umrah rest trips.',
    'https://noorlink.co/images/insider/insider-2028-04-turkey.jpg',
    '/newsletter/2028-04-turkey-spring',
    'INSIDER-APR28',
    '2028-04-04T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-05-iberia',
    'Iberia in late spring — Spain, Portugal, one Europe eSIM',
    'Iberian city breaks, family hotspot, summer corridor prep.',
    'https://noorlink.co/images/insider/insider-2028-05-iberia.jpg',
    '/newsletter/2028-05-iberia',
    'INSIDER-MAY28',
    '2028-05-02T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-06-alps-north',
    'Alpine & northern summer — groups, hotspot, clear signal',
    'Central Europe summer tips and a short Hajj-season glance.',
    'https://noorlink.co/images/insider/insider-2028-06-alps.jpg',
    '/newsletter/2028-06-alps-north',
    'INSIDER-JUN28',
    '2028-06-06T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-07-caribbean',
    'Caribbean & Americas summer — road trips, reliable hotspot',
    'Island and Americas habits, summer data tips, light Umrah note.',
    'https://noorlink.co/images/insider/insider-2028-07-caribbean.jpg',
    '/newsletter/2028-07-caribbean',
    'INSIDER-JUL28',
    '2028-07-04T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  ),
  (
    '2028-08-pilgrimage-prep',
    'Late summer + pilgrimage prep — connectivity done honestly',
    'Pilgrimage timing, install-before-fly, and a Year 2 wrap.',
    'https://noorlink.co/images/insider/insider-2028-08-pilgrimage.jpg',
    '/newsletter/2028-08-pilgrimage-prep',
    'INSIDER-AUG28',
    '2028-08-01T14:00:00Z',
    'scheduled',
    'all', null, null, null, null
  )
on conflict (slug) do update set
  subject = excluded.subject,
  preview = excluded.preview,
  hero_image_url = excluded.hero_image_url,
  web_path = excluded.web_path,
  promo_code = excluded.promo_code,
  send_at = excluded.send_at,
  audience = excluded.audience,
  email_highlight = excluded.email_highlight,
  email_highlight_ref = excluded.email_highlight_ref,
  email_note = excluded.email_note,
  email_giving_note = excluded.email_giving_note;
