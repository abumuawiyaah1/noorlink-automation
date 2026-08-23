from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from environment (.env locally, Railway Variables in production)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # —— App ——
    app_name: str = "NoorLink Automation"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Absolute URL to logo PNG used in transactional emails
    email_logo_url: str = "https://noorlink.co/images/logo.png"

    # —— Supabase (set in Supabase Dashboard → Project Settings → API) ——
    supabase_url: str = Field(
        ...,
        description="Project URL, e.g. https://xxxx.supabase.co",
    )
    supabase_key: str = Field(
        ...,
        description="anon/public key (client-safe; not used for server writes)",
    )
    supabase_service_key: str = Field(
        ...,
        description="service_role key — backend only, bypasses RLS",
    )

    # —— Stripe (Dashboard → Developers → API keys + Webhooks) ——
    stripe_secret_key: str
    stripe_publishable_key: str
    stripe_webhook_secret: str

    # —— Simbase (eSIM provisioning + usage guard) ——
    simbase_api_key: str = ""
    simbase_api_base_url: str = "https://api.simbase.com/v2"
    simbase_webhook_secret: str = ""

    # —— Citrus Mobile (reseller eSIM API) ——
    # Auth: Authorization: Bearer rsk_...
    citrus_api_key: str = ""
    citrus_api_base_url: str = "https://citrusmobile.com/api/v2/reseller"
    # HMAC signing secret from POST /webhooks (whsec_...) — verify X-Citrus-Signature
    citrus_webhook_secret: str = ""
    # mock | citrus | esimaccess | simbase  (default when no plan_fulfillment_map hit)
    esim_provider: str = "mock"

    # —— eSIM Access (Redtea) ——
    # Partner portal → AccessCode. Used as RT-AccessCode + HMAC key.
    esim_access_access_code: str = ""
    esim_access_api_base_url: str = "https://api.esimaccess.com/api/v1/open"
    # Optional shared secret if Access adds webhook signing later
    esim_access_webhook_secret: str = ""
    # When true, Saudi/Umrah orders must map to esimaccess (Phase A restriction)
    esim_access_enforce_saudi: bool = True

    # —— Resend (email delivery) ——
    # From address must use a domain verified in Resend (prefer noorlink.co).
    resend_api_key: str
    resend_from_email: str = "NoorLink <noreply@noorlink.co>"

    # —— Auth (future JWT sessions) ——
    secret_key: str = "change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # —— URLs ——
    # Next.js frontend (Stripe success/cancel redirects)
    app_url: str = "http://localhost:3000"
    stripe_success_path: str = "/success"
    stripe_cancel_path: str = "/checkout"
    # Comma-separated allowed CORS origins (include your Vercel/frontend URL)
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Railway injects these automatically — optional reference / logging
    railway_public_domain: Optional[str] = None
    railway_static_url: Optional[str] = None
    port: Optional[int] = None

    @property
    def supabase_admin_key(self) -> str:
        """Always use service role for server-side persistence."""
        return self.supabase_service_key

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def stripe_success_url(self) -> str:
        return f"{self.app_url.rstrip('/')}{self.stripe_success_path}"

    @property
    def stripe_cancel_url(self) -> str:
        return f"{self.app_url.rstrip('/')}{self.stripe_cancel_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Backwards-compatible module-level instance
settings = get_settings()
