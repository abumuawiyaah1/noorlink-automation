# NoorLink Breakage-Fulfillment Strategy

**Status:** Strategy + routing data live in repo. WeConnect API integration pending sandbox.  
**Generated:** 2026-08-26 from WeConnect P1 Global per-MB pricelist.

---

## Executive summary

NoorLink sells **fixed data bundles** (same as Airalo, Holafly, Nomad).  
We fulfill on **WeConnect pay-per-MB** where wholesale is cheap.  
We **enforce the bundle ourselves** (allowance + expiry).  
**Profit increases when customers don't use all their data** (breakage).

| Policy | Countries | Fulfillment |
|--------|-----------|-------------|
| `weconnect_breakage` | **86** | Virtual bundle on WeConnect PAYG |
| `telna_fixed` | **37** | Telna regional/country bundles |
| `catalog_cascade` | **55** | Access / Telna / catalog smart cascade |
| `access_fixed` | **1** | Saudi Arabia — eSIM Access only |
| `exclude` | **1** | Block (Satellite Networks) |

**Machine-readable routing:** `data/breakage/country_routing.json`  
**Regenerate after new WeConnect price list:** `python scripts/generate_breakage_strategy.py`

---

## The business model

### What the customer sees

- Standard plans (Starter 3GB/7d, Traveler 10GB/15d, Heavy 20GB/30d)
- Caribbean/LatAm ladder (1/3/5/10 GB) on regional pages
- Optional **Flex Pay-As-You-Go** + top-up checkbox
- Simple dashboard: **GB remaining · days left**

### What we do internally

```
Customer pays retail ($29.99 for 10GB / 15 days)
        ↓
Issue ONE eSIM (WeConnect PAYG profile) — $1.60
        ↓
Internal allowance ledger: 10,240 MB, expires in 15 days
        ↓
User consumes data → WeConnect bills us per MB (country rate)
        ↓
At 100% allowance OR expiry → suspend data
        ↓
We paid wholesale for actual MB used only
        ↓
Unused MB at expiry = breakage profit
```

### Example: Turkey (Traveler 10GB / 15 days @ $29.99)

| Usage | Wholesale | Margin |
|-------|-----------|--------|
| 25% (2.5 GB) | ~$3.18 | **~$26.81** |
| 50% (5 GB) | ~$4.71 | **~$25.28** |
| 100% (10 GB) | ~$7.82 | **~$22.17** |

Even at **full usage**, margin stays strong. Breakage is upside.

### Counter-example: Jamaica (why NOT breakage)

| Usage | Wholesale | vs $54.99 retail (10GB plan) |
|-------|-----------|----------------------------|
| 100% | ~$63.95 | **Loss** |

→ Jamaica routes to **`telna_fixed`**, not WeConnect per-MB.

---

## Routing policy (decision tree)

```
Checkout for country X, plan Y
        │
        ├─ wantsTopUp? ──YES──► PAYG top-up lane (WeConnect → Citrus fallback)
        │
        ├─ Saudi Arabia? ──YES──► access_fixed (eSIM Access)
        │
        ├─ Caribbean island? ──YES──► telna_fixed
        │
        ├─ 10GB @ 100% usage loses money on WeConnect? ──YES──► telna_fixed or catalog_cascade
        │
        ├─ 10GB @ 100% usage margin ≥ 25%? ──YES──► weconnect_breakage ★
        │
        └─ else ──► catalog_cascade (Access/Telna smart cascade)
```

---

## Product rules (non-negotiable)

1. **Hard cap** — never exceed sold allowance  
2. **Expiry** — unused data expires (disclosed in terms)  
3. **No rollover** — keeps breakage model clean  
4. **Low-data alerts** — 80% and 100% (email + install page)  
5. **Never expose provider** — customer sees NoorLink only  

---

## Storefront ladders

### Standard countries (86+ breakage-eligible)

| Plan | Data | Days | Retail anchor |
|------|------|------|---------------|
| Starter | 3 GB | 7 | $19.99 |
| Traveler | 10 GB | 15 | $29.99 |
| Heavy | 20 GB | 30 | $44.99 |
| Flex PAYG | — | — | from $2.99 |

### Caribbean / LatAm regional (Telna bundles)

| Plan | Data | Days | Retail anchor |
|------|------|------|---------------|
| Basic | 1 GB | 5 | $14.99 |
| Standard | 3 GB | 7 | $27.99 |
| Plus | 5 GB | 15 | $34.99 |
| Premium | 10 GB | 30 | $54.99 |

---

## Pilot launch (phase 1)

Top 25 breakage-score countries from generated data:

1. Turkey  
2. Ukraine  
3. Finland  
4. Austria, Bulgaria, Croatia, Czech Republic, Denmark, Estonia, Germany…  
5. France, UK, Spain, Italy, Netherlands  
6. USA, Egypt, Pakistan, Thailand, Vietnam  

**Launch checklist**

- [ ] WeConnect sandbox: provision, usage query, suspend, top-up balance  
- [ ] Allowance ledger table in Supabase (order_id, allowance_mb, used_mb, expires_at)  
- [ ] Cron: sync usage from WeConnect every 15–60 min  
- [ ] Auto-suspend at cap or expiry  
- [ ] 20 test orders across 5 pilot countries  
- [ ] Measure actual usage % after 30 days  
- [ ] Expand country allowlist based on telemetry  

---

## Allowance ledger (phase 2 — to implement)

When WeConnect API is live, each virtual-bundle order gets:

| Column | Purpose |
|--------|---------|
| `order_id` | Stripe / internal order |
| `provider` | `weconnect` |
| `provider_profile_id` | ICCID / eID |
| `allowance_mb` | Sold data cap |
| `used_mb` | Synced from provider |
| `wholesale_cost_usd` | Running cost |
| `retail_usd` | What customer paid |
| `valid_until` | Expiry timestamp |
| `status` | active / exhausted / expired / suspended |

---

## Revenue maximization levers

### 1. Breakage (primary)

Industry typical: **40–60% of allowance unused** on short trips.  
At 50% usage on Traveler 10GB in Turkey: **~$25 margin** vs **~$22** at 100%.

### 2. Expiry

15-day validity on 10GB plan — business traveler uses 3GB, rest expires.

### 3. Top-up upsell

Customer exhausts allowance before expiry → "Add 1 GB for $X" (high margin add-on).

### 4. Country routing

Silently use cheapest rail per country — customer never knows.

### 5. Pricing psychology

Keep `ROUND_TO_95` suffix ($29.99) — already in `pricing_rules`.

---

## API endpoints (debug / admin)

```bash
# Strategy summary + pilot list
GET /api/fulfillment/strategy/summary

# Country policy + recommended mode
GET /api/fulfillment/strategy/country?country=turkey

# Full resolve + breakage margin estimates
GET /api/fulfillment/resolve?country=turkey&dataGb=10&days=15
```

---

## Files in this repo

| File | Purpose |
|------|---------|
| `docs/BREAKAGE-FULFILLMENT-STRATEGY.md` | This document |
| `data/breakage/country_routing.json` | 180-country policy map |
| `data/breakage/country_routing.csv` | Spreadsheet-friendly export |
| `data/breakage/margin_scenarios.csv` | Margin at 25/50/75/100% usage |
| `scripts/generate_breakage_strategy.py` | Regenerate from WeConnect xlsx |
| `app/services/breakage_strategy.py` | Runtime policy module |

---

## Provider roles (final architecture)

```
┌─────────────────────────────────────────────────────────┐
│                    NOORLINK STOREFRONT                   │
│         Fixed bundles · Regional · Flex PAYG             │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   weconnect_breakage  telna_fixed   access_fixed
   (virtual bundle)   (Caribbean,   (Saudi/Umrah)
                       LatAm loss-
                       leader cases)
          │               │               │
          ▼               ▼               ▼
     WeConnect         Telna          eSIM Access
     per-MB PAYG       bundles        bundles
          │
          └── Top-up lane ──► WeConnect (primary) / Citrus (fallback)
```

---

## Commercial terms to confirm with WeConnect

- [ ] Sandbox + production API keys  
- [ ] Real-time usage CDR vs delayed billing  
- [ ] Per-eSIM balance vs master wallet  
- [ ] API: provision, suspend, add funds, query usage  
- [ ] Webhooks: install, threshold, suspend  
- [ ] Minimum spend / credit line  
- [ ] Fair-use / FUP policies  

---

## Regenerate routing data

When WeConnect sends an updated pricelist:

```bash
cd noorlink-automation
python scripts/generate_breakage_strategy.py \
  --xlsx ~/Downloads/"WEC eSIM P1 Global per MB ....xlsx"
git add data/breakage/
git commit -m "Update breakage country routing from WeConnect pricelist"
```

---

## Related docs

- `docs/TELNA-RUNBOOK.md` — Telna fixed bundles (Caribbean/LatAm)  
- `app/services/fulfillment_resolver.py` — Smart cascade at checkout  
- `app/services/breakage_strategy.py` — Policy lookup  
