# Telna Connect Flex — NoorLink runbook

## Status (Aug 27, 2026)

**Ordering API is working** with the current account token:

```text
GET /v1/ordering/products → HTTP 200 (786 products)
```

### Cloudflare Error 1010 pitfall

Requests **without a `User-Agent` header** are blocked by Cloudflare in front of
`ppo-api.telna.com` with Error 1010 / “Access denied”. That can look like a Telna
auth failure. Our client always sends `User-Agent: NoorLink/1.0 (+https://noorlink.co)`.

Docs hub (same API): https://ppov10.readme.io/reference  
(= https://flex-developer.telna.com)

## Auth format (confirmed)

Telna accepts **either**:

```http
Authorization: <raw-token>
```

or

```http
Authorization: Bearer <token>
```

Hamly noted their examples use the raw token. Our client sends the raw token.

## Environment variables

Local `.env` / Railway production:

```env
TELNA_API_TOKEN=...
TELNA_ACCOUNT_ID=6A8BF313C5A7F047663C48F8
TELNA_ORDERING_BASE_URL=https://ppo-api.telna.com/v1/ordering
TELNA_DIAGNOSTIC_BASE_URL=https://ppo-api.telna.com/v1/diagnostic
```

Ensure `TELNA_API_TOKEN` and `TELNA_ACCOUNT_ID` are set on **Railway** (not only local `.env`).

## Diagnostic commands

```bash
cd noorlink-automation
python scripts/telna_probe.py
python scripts/telna_catalog.py
python scripts/telna_catalog.py --json > /tmp/telna-catalog.json
python scripts/telna_catalog.py --filter "Caribbean|Middle East|Saudi|Global"
```

## Email Telna (copy/paste)

**To:** support@telna.com  
**From:** your Connect Flex portal login email  
**Subject:** Enable Connect Flex Ordering API — Account 6A8BF313C5A7F047663C48F8

Hello,

We are integrating NoorLink (travel eSIM) with Connect Flex Ordering API.

- Account ID: `6A8BF313C5A7F047663C48F8`
- We corrected Authorization to send the raw token (no Bearer prefix), per your guidance.
- We still receive HTTP 403 on `GET /v1/ordering/products` with body:
  `"Access to this API has been disallowed"`

Please enable API access for:
1. `GET /v1/ordering/products` (full catalog)
2. `POST /v1/ordering/work-orders` (eSIM provisioning)
3. `GET /v1/diagnostic/euicc-profiles/{iccid}` (profile refresh)

Once enabled, we will pull the catalog, map SKUs to our virtual catalog, and begin Caribbean regional fulfillment.

Thank you,  
[Your name]  
NoorLink — https://noorlink.co

## After API is enabled

1. Run `python scripts/telna_catalog.py` — confirm product count > 0
2. Apply Supabase migrations:
   - `20260825200000_plan_fulfillment_telna_provider.sql`
   - `20260825000000_caribbean_telna_fulfillment.sql`
3. Map Telna product IDs → `plan_fulfillment_map` + retail pricing
4. Set Railway `TELNA_API_TOKEN` if not already live
5. Test one paid Caribbean order end-to-end (small SKU first)

## Code already in repo

| Piece | Path |
|-------|------|
| API client | `app/services/telna.py` |
| Catalog CLI | `scripts/telna_catalog.py` |
| Probe CLI | `scripts/telna_probe.py` |
| Provision path | `app/services/esim_provision.py` |
| Caribbean map (draft SKUs) | `supabase/migrations/20260825000000_caribbean_telna_fulfillment.sql` |
