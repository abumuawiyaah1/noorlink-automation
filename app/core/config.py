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

    # —— Resend (email delivery) ——
    resend_api_key: str
    resend_from_email: str = "noreply@noorlink.com"

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
