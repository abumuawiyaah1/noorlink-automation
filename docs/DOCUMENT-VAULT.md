# Legal & accounting document vault

Private staff vault for company paperwork (contracts, tax, accounting, compliance).  
Lives in admin under **Finance → Documents**.

## Roles (built for growth)

| Role | View / download | Upload | Soft-delete (archive) |
|------|-----------------|--------|------------------------|
| **admin** | Yes (including admin-only files) | Yes | Yes |
| **finance** | Vault files | Yes | No |
| **legal** | Vault files | Yes | No |
| support / marketing / catalog | No | No | No |

To grant access later: create a staff user with role `finance` or `legal` (Staff wizard or `create_admin_user.py`).

**Access levels per file**

- `vault` — visible to admin + finance + legal  
- `admin_only` — admin only (highly sensitive originals)

## Apply migration

Run `supabase/migrations/20260829270000_company_documents_vault.sql` in Supabase.  
It creates:

- `company_documents` table  
- `finance` / `legal` roles on `admin_users`  
- private Storage bucket `company-documents` (20 MB limit)

Requires `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` on Railway (service role bypasses Storage RLS).

## Manual bucket check

Supabase Dashboard → **Storage** → confirm bucket **company-documents** exists and is **private**.  
If the SQL insert into `storage.buckets` failed on your plan, create the bucket manually with the same name and privacy.

## Security notes

- Files are never public URLs; download goes through authenticated `/admin/documents/.../download`
- Uploads / downloads / archives are written to `admin_audit_log`
- Soft-delete hides files from the list; storage objects stay until a future hard-purge tool
- Keep Cloudflare Access / `ADMIN_ALLOWED_IPS` on `/admin`

## Allowed file types

PDF, PNG, JPEG, WebP, DOC/DOCX, XLS/XLSX, CSV, TXT — max **20 MB**.
