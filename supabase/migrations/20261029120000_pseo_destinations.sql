-- Programmatic SEO destination hubs (NoorLink).
-- Next.js v1 reads a mirrored seed; this table is the editorial source of truth
-- for staged is_indexed releases and future admin tooling.

CREATE TABLE IF NOT EXISTS public.pseo_destinations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(100) UNIQUE NOT NULL,
  country_name_en VARCHAR(100) NOT NULL,
  country_name_es VARCHAR(100),
  country_name_ar VARCHAR(100),
  plans_path TEXT NOT NULL DEFAULT '',
  wave CHAR(1) NOT NULL DEFAULT 'C' CHECK (wave IN ('A', 'B', 'C')),
  primary_carrier VARCHAR(100) NOT NULL,
  secondary_carrier VARCHAR(100),
  apn_name VARCHAR(100) NOT NULL DEFAULT 'internet',
  apn_notes TEXT NOT NULL DEFAULT '',
  supported_frequencies VARCHAR(200) NOT NULL DEFAULT '5G / 4G LTE',
  popular_cities TEXT[] NOT NULL DEFAULT '{}',
  intro_en TEXT NOT NULL,
  intro_es TEXT,
  intro_ar TEXT,
  roaming_tips_en TEXT NOT NULL,
  roaming_tips_es TEXT,
  roaming_tips_ar TEXT,
  is_indexed BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pseo_slug ON public.pseo_destinations (slug);
CREATE INDEX IF NOT EXISTS idx_pseo_indexed ON public.pseo_destinations (is_indexed);

COMMENT ON TABLE public.pseo_destinations IS
  'pSEO travel eSIM hubs. Sitemap/static generation must use is_indexed = true only.';

COMMENT ON COLUMN public.pseo_destinations.is_indexed IS
  'Crawl release flag — false keeps the row out of sitemap batches.';
