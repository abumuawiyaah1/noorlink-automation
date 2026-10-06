# Gap fix — Access/Zesimo off Telna regionals

## Paste into Supabase SQL Editor

1. (If not already) `telna_weconnect_replacement.sql` — country cutover (170 Access / 5 Zesimo)
2. **`gap_fix.sql`** — regionals + Aruba / Cayman / Taiwan / Puerto Rico

Migration mirror: `supabase/migrations/20261006140000_gap_fix_access_regionals.sql`

## What changed in code

- `regional_inventory.py`: Africa + Caribbean off Telna → Access ladders; Asia 1GB; LatAm 1GB; ME 5/20; NA 20GB; Global 1/20
- `fulfillment_map.py`: `STATIC_GAP_FIX_MAP` for Aruba/Cayman/Taiwan/PR; map-lock those slugs

## Intentionally unfixed

| Gap | Why |
| --- | --- |
| **Lebanon** | No Access/Zesimo country or regional pack includes `LB`. Citrus ~$29/GB — not saleable as fixed GB. |
| **Caribbean 20GB** | No Access Caribbean 20GB. Global Access excludes AW/KY/JM/BS — do not substitute. Template `premium` = `coming_soon`. |

## Margin warnings

- **Aruba** wholesale is steep (20GB ≈ $139). Maps exist so checkout can provision; retail must cover cost or hide large packs.
- **Taiwan** fulfills silently on **Asia-14** (TW confirmed in Access location list).
